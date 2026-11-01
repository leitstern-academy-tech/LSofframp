"""Scan ZIP archives and plain directories without extracting anything.

Problems found in an entry are recorded as issues and the entry is skipped;
only an unreadable package as a whole raises PackageError.
"""

import hashlib
import os
import stat
import zipfile
import zlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from lsofframp.core.manifest import (
    ChecksumError,
    ManifestError,
    PackageKind,
    PackagePart,
    SourcePackage,
    UnsafePathError,
    directory_digest,
    sha256_file,
    validate_package_path,
)

_CHUNK_SIZE = 1024 * 1024
_ZIP_ENCRYPTED_FLAG = 0x1
_ZIP_READ_ERRORS = (
    zipfile.BadZipFile,
    NotImplementedError,
    zlib.error,
    EOFError,
    OSError,
    RuntimeError,
)


class PackageError(ManifestError):
    """The package as a whole cannot be read."""


@dataclass(frozen=True)
class Limits:
    max_entries: int = 200_000
    max_entry_bytes: int = 4 * 1024**3
    max_total_bytes: int = 100 * 1024**3
    max_ratio: int = 1000
    ratio_min_bytes: int = 1024**2


DEFAULT_LIMITS = Limits()


class IssueCode(str, Enum):
    UNSAFE_PATH = "unsafe_path"
    DUPLICATE_PATH = "duplicate_path"
    CASE_COLLISION = "case_collision"
    SYMLINK = "symlink"
    ENCRYPTED = "encrypted"
    CORRUPT_ENTRY = "corrupt_entry"
    UNREADABLE = "unreadable"
    SUSPICIOUS_RATIO = "suspicious_ratio"
    ENTRY_TOO_LARGE = "entry_too_large"
    LIMIT_ENTRIES = "limit_entries"
    LIMIT_TOTAL = "limit_total"


@dataclass(frozen=True)
class ReadIssue:
    code: IssueCode
    part: str
    path: str | None
    detail: str


@dataclass(frozen=True)
class Entry:
    part: str
    path: str
    size: int
    hash: str | None
    is_dir: bool = False


@dataclass
class PartScan:
    part: PackagePart
    entries: list[Entry] = field(default_factory=list)
    issues: list[ReadIssue] = field(default_factory=list)


@dataclass
class PackageReading:
    scans: list[PartScan]

    def source_package(self) -> SourcePackage:
        return SourcePackage(parts=[scan.part for scan in self.scans])

    @property
    def entries(self) -> list[Entry]:
        return [entry for scan in self.scans for entry in scan.entries]

    @property
    def issues(self) -> list[ReadIssue]:
        return [issue for scan in self.scans for issue in scan.issues]


class _Collector:
    """Accumulates entries and issues and enforces path, duplicate and total-size rules."""

    def __init__(self, part: str, limits: Limits) -> None:
        self.part = part
        self.limits = limits
        self.entries: list[Entry] = []
        self.issues: list[ReadIssue] = []
        self.total_bytes = 0
        self._paths: set[str] = set()
        self._folded: dict[str, str] = {}

    def issue(self, code: IssueCode, path: str | None, detail: str) -> None:
        self.issues.append(ReadIssue(code, self.part, path, detail))

    def accept_path(self, raw: str) -> str | None:
        """Return the safe path, or None after recording why it was refused."""
        try:
            path = validate_package_path(raw)
        except UnsafePathError as exc:
            self.issue(IssueCode.UNSAFE_PATH, None, f"{raw!r}: {exc}")
            return None
        if path in self._paths:
            self.issue(IssueCode.DUPLICATE_PATH, path, "path appears more than once")
            return None
        self._paths.add(path)
        folded = path.casefold()
        other = self._folded.setdefault(folded, path)
        if other != path:
            self.issue(IssueCode.CASE_COLLISION, path, f"differs from {other!r} only by case")
        return path

    def add_size(self, path: str, size: int) -> bool:
        """Count ``size`` against the limits; False means the entry must be skipped."""
        if size > self.limits.max_entry_bytes:
            self.issue(IssueCode.ENTRY_TOO_LARGE, path, f"{size} bytes exceeds the entry limit")
            return False
        self.total_bytes += size
        return True

    def over_total(self) -> bool:
        return self.total_bytes > self.limits.max_total_bytes

    def finish(self, part: PackagePart) -> PartScan:
        self.entries.sort(key=lambda entry: entry.path)
        return PartScan(part=part, entries=self.entries, issues=self.issues)


def _hash_zip_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int) -> str | None:
    """Stream one entry through SHA-256; the CRC is verified by zipfile at end of stream."""
    digest = hashlib.sha256()
    seen = 0
    with archive.open(info) as handle:
        while chunk := handle.read(_CHUNK_SIZE):
            seen += len(chunk)
            if seen > limit:
                return None
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def scan_zip(path: Path, limits: Limits = DEFAULT_LIMITS) -> PartScan:
    name = path.name
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise PackageError(f"cannot open {name} as a ZIP archive: {exc}") from exc
    try:
        file_hash = sha256_file(path)
        file_bytes = path.stat().st_size
    except (ChecksumError, OSError) as exc:
        archive.close()
        raise PackageError(f"cannot read {name}: {exc}") from exc

    collector = _Collector(name, limits)
    with archive:
        infos = archive.infolist()
        if len(infos) > limits.max_entries:
            collector.issue(
                IssueCode.LIMIT_ENTRIES,
                None,
                f"{len(infos)} entries; only the first {limits.max_entries} were scanned",
            )
            infos = infos[: limits.max_entries]
        for info in infos:
            _scan_zip_entry(archive, info, collector)
            if collector.over_total():
                collector.issue(
                    IssueCode.LIMIT_TOTAL,
                    None,
                    f"uncompressed size exceeds {limits.max_total_bytes} bytes; scan stopped",
                )
                break

    part = PackagePart(
        name=name,
        kind=PackageKind.ZIP,
        hash=file_hash,
        bytes=file_bytes,
        entry_count=len(collector.entries),
    )
    return collector.finish(part)


def _scan_zip_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo, collector: _Collector) -> None:
    is_dir = info.is_dir()
    path = collector.accept_path(info.filename.rstrip("/") if is_dir else info.filename)
    if path is None:
        return
    if is_dir:
        collector.entries.append(Entry(collector.part, path, 0, None, is_dir=True))
        return
    mode = info.external_attr >> 16
    if mode and stat.S_ISLNK(mode):
        collector.issue(IssueCode.SYMLINK, path, "symbolic link entries are not followed")
        return
    if info.flag_bits & _ZIP_ENCRYPTED_FLAG:
        collector.issue(IssueCode.ENCRYPTED, path, "entry is password-protected")
        return
    limits = collector.limits
    compressible = info.file_size >= limits.ratio_min_bytes and info.compress_size > 0
    if compressible and info.file_size / info.compress_size > limits.max_ratio:
        collector.issue(
            IssueCode.SUSPICIOUS_RATIO,
            path,
            f"compression ratio above {limits.max_ratio}:1; entry not read",
        )
        return
    if not collector.add_size(path, info.file_size):
        return
    try:
        digest = _hash_zip_entry(archive, info, limits.max_entry_bytes)
    except _ZIP_READ_ERRORS as exc:
        collector.issue(IssueCode.CORRUPT_ENTRY, path, f"entry could not be read: {exc}")
        return
    if digest is None:
        collector.issue(IssueCode.ENTRY_TOO_LARGE, path, "entry is larger than it declares")
        return
    collector.entries.append(Entry(collector.part, path, info.file_size, digest))


def scan_directory(root: Path, limits: Limits = DEFAULT_LIMITS) -> PartScan:
    name = root.name or str(root)
    collector = _Collector(name, limits)
    walk_errors: list[OSError] = []
    stop = False
    for current, dirnames, filenames in os.walk(root, followlinks=False, onerror=walk_errors.append):
        dirnames.sort()
        base = Path(current)
        for entry_name in sorted(dirnames) + sorted(filenames):
            if len(collector.entries) >= limits.max_entries:
                collector.issue(
                    IssueCode.LIMIT_ENTRIES,
                    None,
                    f"more than {limits.max_entries} entries; scan stopped",
                )
                stop = True
                break
            _scan_directory_entry(root, base / entry_name, collector)
            if collector.over_total():
                collector.issue(
                    IssueCode.LIMIT_TOTAL,
                    None,
                    f"size exceeds {limits.max_total_bytes} bytes; scan stopped",
                )
                stop = True
                break
        if stop:
            break
    for error in walk_errors:
        collector.issue(IssueCode.UNREADABLE, None, f"directory could not be listed: {error}")

    hashed = [(entry.path, entry.hash) for entry in collector.entries if entry.hash is not None]
    part = PackagePart(
        name=name,
        kind=PackageKind.DIRECTORY,
        hash=directory_digest(hashed),
        bytes=collector.total_bytes,
        entry_count=len(collector.entries),
    )
    return collector.finish(part)


def _scan_directory_entry(root: Path, full: Path, collector: _Collector) -> None:
    relative = full.relative_to(root).as_posix()
    path = collector.accept_path(relative)
    if path is None:
        return
    try:
        info = full.lstat()
    except OSError as exc:
        collector.issue(IssueCode.UNREADABLE, path, f"cannot stat entry: {exc}")
        return
    if stat.S_ISLNK(info.st_mode):
        collector.issue(IssueCode.SYMLINK, path, "symbolic links are not followed")
        return
    if stat.S_ISDIR(info.st_mode):
        collector.entries.append(Entry(collector.part, path, 0, None, is_dir=True))
        return
    if not stat.S_ISREG(info.st_mode):
        collector.issue(IssueCode.UNREADABLE, path, "not a regular file")
        return
    if not collector.add_size(path, info.st_size):
        return
    try:
        digest = sha256_file(full)
    except ChecksumError as exc:
        collector.issue(IssueCode.UNREADABLE, path, str(exc))
        return
    collector.entries.append(Entry(collector.part, path, info.st_size, digest))


def scan_package(path: Path, limits: Limits = DEFAULT_LIMITS) -> PartScan:
    path = Path(path)
    if path.is_dir():
        return scan_directory(path, limits)
    if path.is_file():
        return scan_zip(path, limits)
    raise PackageError(f"{path} does not exist or is not a file or directory")


def read_packages(paths: Iterable[Path], limits: Limits = DEFAULT_LIMITS) -> PackageReading:
    scans = [scan_package(Path(item), limits) for item in paths]
    if not scans:
        raise PackageError("no package given")
    try:
        PackageReading(scans).source_package()
    except ValueError as exc:
        raise PackageError(f"package parts cannot be combined: {exc}") from exc
    return PackageReading(scans)