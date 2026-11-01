"""Turn a package reading into a Portability Manifest."""

from datetime import datetime, timezone

from lsofframp.core.manifest import (
    IntegrityInfo,
    Manifest,
    ManifestObject,
    ObjectKind,
    ToolInfo,
    derive_object_id,
)
from lsofframp.readers.formats import describe_format
from lsofframp.readers.package import Entry, IssueCode, PackageReading, ReadIssue


def build_manifest(
    reading: PackageReading,
    tool_version: str,
    generated_at: datetime | None = None,
) -> tuple[Manifest, list[ReadIssue]]:
    """Return the manifest and the issues raised while merging the parts.

    An entry whose path already came from an earlier part is not added twice;
    the repetition is reported. Folders repeated across parts are merged silently.
    """
    objects: dict[str, ManifestObject] = {}
    issues: list[ReadIssue] = []
    for entry in reading.entries:
        item = _object_for(entry)
        known = objects.get(item.id)
        if known is None:
            objects[item.id] = item
        elif not entry.is_dir:
            issues.append(
                ReadIssue(
                    IssueCode.DUPLICATE_PATH,
                    entry.part,
                    entry.path,
                    f"path already present in part {known.part!r}; later copy ignored",
                )
            )
    manifest = Manifest(
        generated_at=generated_at or datetime.now(timezone.utc),
        tool=ToolInfo(name="lsofframp", version=tool_version),
        source_package=reading.source_package(),
        objects=list(objects.values()),
    )
    return manifest, issues


def _object_for(entry: Entry) -> ManifestObject:
    kind = ObjectKind.FOLDER if entry.is_dir else ObjectKind.FILE
    fields: dict = {
        "id": derive_object_id(kind, entry.path, None),
        "kind": kind,
        "part": entry.part,
        "path": entry.path,
    }
    if not entry.is_dir:
        fields["format"] = describe_format(entry.path)
        fields["integrity"] = IntegrityInfo(bytes=entry.size, hash=entry.hash)
    return ManifestObject(**fields)