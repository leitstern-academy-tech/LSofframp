import os
import stat
import zipfile
from pathlib import Path

import pytest

from lsofframp.core.manifest import OpenStandard, PackageKind, sha256_ref
from lsofframp.readers.formats import describe_format
from lsofframp.readers.package import (
    IssueCode,
    Limits,
    PackageError,
    read_packages,
    scan_directory,
    scan_package,
    scan_zip,
)


def make_zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path


def codes(scan) -> list[IssueCode]:
    return [issue.code for issue in scan.issues]


def by_path(scan) -> dict:
    return {entry.path: entry for entry in scan.entries}


def test_zip_entries_are_hashed_and_sorted(tmp_path):
    archive = make_zip(tmp_path / "export.zip", {"b/two.txt": b"two", "a.txt": b"abc"})
    scan = scan_zip(archive)
    assert [entry.path for entry in scan.entries] == ["a.txt", "b/two.txt"]
    assert by_path(scan)["a.txt"].hash == sha256_ref(b"abc")
    assert scan.part.kind is PackageKind.ZIP
    assert scan.part.entry_count == 2
    assert not scan.issues


def test_zip_directory_entries_are_kept_as_folders(tmp_path):
    archive = tmp_path / "export.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("docs/", b"")
        handle.writestr("docs/a.txt", b"x")
    entries = by_path(scan_zip(archive))
    assert entries["docs"].is_dir
    assert entries["docs"].hash is None
    assert not entries["docs/a.txt"].is_dir


@pytest.mark.parametrize("name", ["../evil.txt", "/abs.txt", "a/../../b.txt", "C:/x.txt"])
def test_unsafe_zip_paths_are_skipped_not_fatal(tmp_path, name):
    archive = make_zip(tmp_path / "export.zip", {name: b"x", "ok.txt": b"ok"})
    scan = scan_zip(archive)
    assert [entry.path for entry in scan.entries] == ["ok.txt"]
    assert codes(scan) == [IssueCode.UNSAFE_PATH]


def test_duplicate_paths_keep_the_first_entry(tmp_path):
    archive = tmp_path / "export.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("a.txt", b"first")
        with pytest.warns(UserWarning):
            handle.writestr("a.txt", b"second")
    scan = scan_zip(archive)
    assert by_path(scan)["a.txt"].hash == sha256_ref(b"first")
    assert codes(scan) == [IssueCode.DUPLICATE_PATH]


def test_case_collisions_are_reported_but_both_kept(tmp_path):
    archive = make_zip(tmp_path / "export.zip", {"Report.txt": b"1", "report.txt": b"2"})
    scan = scan_zip(archive)
    assert len(scan.entries) == 2
    assert codes(scan) == [IssueCode.CASE_COLLISION]


def test_symlink_entries_are_skipped(tmp_path):
    archive = tmp_path / "export.zip"
    link = zipfile.ZipInfo("link")
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr(link, "target.txt")
        handle.writestr("target.txt", b"x")
    scan = scan_zip(archive)
    assert [entry.path for entry in scan.entries] == ["target.txt"]
    assert codes(scan) == [IssueCode.SYMLINK]


def test_encrypted_entries_are_reported(tmp_path):
    archive = make_zip(tmp_path / "export.zip", {"secret.txt": b"cipher"})
    raw = bytearray(archive.read_bytes())
    central = raw.index(b"PK\x01\x02")
    raw[central + 8] |= 0x1
    archive.write_bytes(bytes(raw))
    scan = scan_zip(archive)
    assert not scan.entries
    assert codes(scan) == [IssueCode.ENCRYPTED]


def test_crc_corruption_is_reported_and_other_entries_survive(tmp_path):
    archive = tmp_path / "export.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("bad.txt", b"payload-payload")
        handle.writestr("good.txt", b"fine")
    raw = bytearray(archive.read_bytes())
    raw[raw.index(b"payload-payload")] ^= 0xFF
    archive.write_bytes(bytes(raw))
    scan = scan_zip(archive)
    assert [entry.path for entry in scan.entries] == ["good.txt"]
    assert codes(scan) == [IssueCode.CORRUPT_ENTRY]


def test_extreme_compression_ratio_is_not_read(tmp_path):
    archive = make_zip(tmp_path / "bomb.zip", {"zeros.bin": b"\0" * (8 * 1024**2)})
    scan = scan_zip(archive)
    assert not scan.entries
    assert codes(scan) == [IssueCode.SUSPICIOUS_RATIO]


def test_small_highly_compressible_entries_are_fine(tmp_path):
    archive = make_zip(tmp_path / "ok.zip", {"zeros.bin": b"\0" * 10_000})
    assert not scan_zip(archive).issues


def test_entry_size_limit(tmp_path):
    archive = make_zip(tmp_path / "export.zip", {"big.txt": b"x" * 100, "small.txt": b"x"})
    scan = scan_zip(archive, Limits(max_entry_bytes=50))
    assert [entry.path for entry in scan.entries] == ["small.txt"]
    assert codes(scan) == [IssueCode.ENTRY_TOO_LARGE]


def test_total_size_limit_stops_the_scan(tmp_path):
    archive = make_zip(tmp_path / "export.zip", {f"f{i}.txt": b"x" * 40 for i in range(5)})
    scan = scan_zip(archive, Limits(max_total_bytes=100))
    assert len(scan.entries) == 3
    assert codes(scan) == [IssueCode.LIMIT_TOTAL]


def test_entry_count_limit(tmp_path):
    archive = make_zip(tmp_path / "export.zip", {f"f{i}.txt": b"x" for i in range(6)})
    scan = scan_zip(archive, Limits(max_entries=4))
    assert len(scan.entries) == 4
    assert codes(scan) == [IssueCode.LIMIT_ENTRIES]


def test_non_zip_file_raises_package_error(tmp_path):
    target = tmp_path / "not-a-zip.zip"
    target.write_text("plain text", encoding="utf-8")
    with pytest.raises(PackageError):
        scan_package(target)


def test_missing_path_raises_package_error(tmp_path):
    with pytest.raises(PackageError):
        scan_package(tmp_path / "missing")


def test_directory_scan_matches_zip_scan(tmp_path):
    members = {"a.txt": b"abc", "sub/b.txt": b"def"}
    archive = make_zip(tmp_path / "export.zip", members)
    root = tmp_path / "export"
    for name, data in members.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    from_zip = {(e.path, e.hash) for e in scan_zip(archive).entries if not e.is_dir}
    scan = scan_directory(root)
    assert {(e.path, e.hash) for e in scan.entries if not e.is_dir} == from_zip
    assert scan.part.kind is PackageKind.DIRECTORY
    assert scan.part.bytes == 6
    assert by_path(scan)["sub"].is_dir


def test_directory_digest_is_stable_and_content_sensitive(tmp_path):
    root = tmp_path / "export"
    root.mkdir()
    (root / "a.txt").write_bytes(b"one")
    first = scan_directory(root).part.hash
    assert first == scan_directory(root).part.hash
    (root / "a.txt").write_bytes(b"two")
    assert scan_directory(root).part.hash != first


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_directory_symlinks_are_not_followed(tmp_path):
    root = tmp_path / "export"
    root.mkdir()
    (root / "a.txt").write_bytes(b"x")
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"secret")
    try:
        os.symlink(outside, root / "link.txt")
    except OSError:
        pytest.skip("cannot create symlinks here")
    scan = scan_directory(root)
    assert [entry.path for entry in scan.entries] == ["a.txt"]
    assert codes(scan) == [IssueCode.SYMLINK]


def test_directory_entry_limit(tmp_path):
    root = tmp_path / "export"
    root.mkdir()
    for index in range(5):
        (root / f"f{index}.txt").write_bytes(b"x")
    scan = scan_directory(root, Limits(max_entries=3))
    assert len(scan.entries) == 3
    assert IssueCode.LIMIT_ENTRIES in codes(scan)


def test_read_packages_combines_parts(tmp_path):
    first = make_zip(tmp_path / "part-1.zip", {"a.txt": b"1"})
    second = make_zip(tmp_path / "part-2.zip", {"b.txt": b"2"})
    reading = read_packages([first, second])
    assert [part.name for part in reading.source_package().parts] == ["part-1.zip", "part-2.zip"]
    assert {entry.part for entry in reading.entries} == {"part-1.zip", "part-2.zip"}


def test_read_packages_rejects_same_name_twice(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "y").mkdir()
    first = make_zip(tmp_path / "x" / "export.zip", {"a.txt": b"1"})
    second = make_zip(tmp_path / "y" / "export.zip", {"b.txt": b"2"})
    with pytest.raises(PackageError):
        read_packages([first, second])


def test_read_packages_needs_input():
    with pytest.raises(PackageError):
        read_packages([])


@pytest.mark.parametrize(
    ("path", "mediatype", "standard"),
    [
        ("Mail/All.MBOX", "application/mbox", OpenStandard.YES),
        ("cal/events.ics", "text/calendar", OpenStandard.YES),
        ("old/report.doc", "application/msword", OpenStandard.NO),
        ("Drive/notes.gdoc", None, OpenStandard.NO),
        ("data/blob.xyz", None, OpenStandard.UNKNOWN),
    ],
)
def test_describe_format_by_extension(path, mediatype, standard):
    info = describe_format(path)
    assert info.mediatype == mediatype
    assert info.open_standard is standard


def test_describe_format_without_extension():
    info = describe_format("README")
    assert info.extension is None
    assert info.open_standard is OpenStandard.UNKNOWN