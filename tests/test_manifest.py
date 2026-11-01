import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from lsofframp.core.manifest import (
    ChecksumError,
    Confidence,
    ExternalReference,
    Manifest,
    ManifestError,
    ManifestLoadError,
    ManifestObject,
    ObjectKind,
    PackageKind,
    PackagePart,
    ProviderInfo,
    SourcePackage,
    ToolInfo,
    UnsafePathError,
    derive_object_id,
    directory_digest,
    manifest_schema,
    sha256_file,
    sha256_ref,
    strip_url_secrets,
    validate_package_path,
)

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
GENERATED_AT = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)
SCHEMA_FILE = Path(__file__).resolve().parents[1] / "schemas" / "manifest.v0.1.json"


def make_part(name: str = "export-001.zip") -> PackagePart:
    return PackagePart(name=name, kind=PackageKind.ZIP, hash=HASH_A, bytes=1024, entry_count=3)


def make_object(
    kind: ObjectKind = ObjectKind.FILE,
    path: str | None = "docs/a.txt",
    original_id: str | None = None,
    **fields,
) -> ManifestObject:
    return ManifestObject(
        id=derive_object_id(kind, path, original_id),
        kind=kind,
        path=path,
        original_id=original_id,
        **fields,
    )


def make_manifest(objects=None, **fields) -> Manifest:
    values = {
        "generated_at": GENERATED_AT,
        "tool": ToolInfo(name="lsofframp", version="0.0.1"),
        "source_package": SourcePackage(parts=[make_part()]),
        "objects": objects or [],
    }
    values.update(fields)
    return Manifest(**values)


@pytest.mark.parametrize(
    "path",
    ["../x", "/etc/passwd", "a/../b", "C:\\x", "C:x", "a\\b", "", "a//b", "a/", "./a", "a/\x00b"],
)
def test_unsafe_paths_are_rejected(path):
    with pytest.raises(UnsafePathError):
        validate_package_path(path)


@pytest.mark.parametrize("path", ["a", "a/b.txt", "Mail/Inbox.mbox", "Ünïcode/datei.txt", "a b/c"])
def test_safe_paths_pass_unchanged(path):
    assert validate_package_path(path) == path


def test_unsafe_path_in_object_fails_validation():
    with pytest.raises(ValidationError):
        make_object(path="../../secret")


def test_object_id_is_stable_and_depends_on_inputs():
    first = derive_object_id(ObjectKind.FILE, "a.txt", None)
    assert first == derive_object_id(ObjectKind.FILE, "a.txt", None)
    assert first != derive_object_id(ObjectKind.FILE, "b.txt", None)
    assert first != derive_object_id(ObjectKind.FOLDER, "a.txt", None)
    assert first != derive_object_id(ObjectKind.FILE, "a.txt", "provider-1")


def test_object_id_survives_lone_surrogates():
    assert derive_object_id(ObjectKind.FILE, "bad\udcffname", None).startswith("obj_")


def test_sha256_file_matches_known_digest(tmp_path):
    target = tmp_path / "data.bin"
    target.write_bytes(b"abc")
    assert sha256_file(target) == sha256_ref(b"abc")
    assert sha256_file(target) == (
        "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_sha256_file_reports_unreadable_file(tmp_path):
    with pytest.raises(ChecksumError):
        sha256_file(tmp_path / "missing.bin")


def test_directory_digest_ignores_walk_order():
    entries = [("b.txt", HASH_B), ("a/c.txt", HASH_A)]
    assert directory_digest(entries) == directory_digest(reversed(entries))


def test_directory_digest_changes_with_content():
    assert directory_digest([("a.txt", HASH_A)]) != directory_digest([("a.txt", HASH_B)])


def test_directory_digest_rejects_duplicates_and_bad_input():
    with pytest.raises(ChecksumError):
        directory_digest([("a.txt", HASH_A), ("a.txt", HASH_B)])
    with pytest.raises(ChecksumError):
        directory_digest([("a.txt", "md5:abc")])
    with pytest.raises(UnsafePathError):
        directory_digest([("../a.txt", HASH_A)])


def test_url_secrets_are_removed():
    url = "https://user:pw@Example.com:8443/a/b?token=abc#frag"
    assert strip_url_secrets(url) == "https://example.com:8443/a/b"
    assert strip_url_secrets("https://[::1]/x?y=1") == "https://[::1]/x"
    assert strip_url_secrets("provider-doc:abc123?sig=1") == "provider-doc:abc123"
    assert strip_url_secrets("https://exa mple.com:99999999/p?q=1") == (
        "https://exa mple.com:99999999/p"
    )


def test_external_reference_drops_query_and_rejects_empty_result():
    reference = ExternalReference(target="https://example.com/doc?sig=secret")
    assert reference.target == "https://example.com/doc"
    with pytest.raises(ValidationError):
        ExternalReference(target="?sig=secret")


def test_null_and_empty_sharing_stay_distinct():
    unknown = make_object(path="unknown.txt")
    private = make_object(path="private.txt", shared_with=[])
    data = json.loads(make_manifest([unknown, private]).to_json())
    by_path = {item["path"]: item for item in data["objects"]}
    assert by_path["unknown.txt"]["shared_with"] is None
    assert by_path["private.txt"]["shared_with"] == []


def test_output_does_not_depend_on_input_order():
    objects = [make_object(path=f"f{i}.txt") for i in range(5)]
    forward = make_manifest(list(objects))
    backward = make_manifest(list(reversed(objects)))
    assert forward.to_json() == backward.to_json()
    ids = [item.id for item in forward.objects]
    assert ids == sorted(ids)


def test_roundtrip_through_file(tmp_path):
    manifest = make_manifest(
        [
            make_object(path="a.txt", shared_with=[]),
            make_object(
                ObjectKind.MAIL_MESSAGE,
                path="mail/inbox.mbox",
                original_id="msg:1",
                mail={"labels": ["Inbox"], "attachment_count": 0},
            ),
        ]
    )
    target = tmp_path / "manifest.json"
    manifest.write(target)
    assert Manifest.load(target) == manifest
    assert target.read_bytes().endswith(b"}\n")
    assert b"\r\n" not in target.read_bytes()
    assert [item.name for item in tmp_path.iterdir()] == ["manifest.json"]


def test_digest_changes_when_content_changes():
    first = make_manifest([make_object(path="a.txt")])
    second = make_manifest([make_object(path="b.txt")])
    assert first.digest() != second.digest()
    assert first.digest() == make_manifest([make_object(path="a.txt")]).digest()


def test_dependency_on_unknown_object_is_rejected():
    ghost = derive_object_id(ObjectKind.FILE, "ghost.txt", None)
    with pytest.raises(ValidationError):
        make_manifest([make_object(path="a.txt", depends_on=[ghost])])


def test_dependency_on_known_object_is_accepted():
    target = make_object(path="target.txt")
    holder = make_object(path="holder.txt", depends_on=[target.id])
    assert make_manifest([holder, target])


def test_self_dependency_is_rejected():
    own_id = derive_object_id(ObjectKind.FILE, "a.txt", None)
    with pytest.raises(ValidationError):
        make_object(path="a.txt", depends_on=[own_id])


def test_duplicate_object_ids_are_rejected():
    with pytest.raises(ValidationError):
        make_manifest([make_object(path="a.txt"), make_object(path="a.txt")])


def test_unknown_part_is_rejected():
    with pytest.raises(ValidationError):
        make_manifest([make_object(path="a.txt", part="other.zip")])


def test_duplicate_part_names_are_rejected():
    with pytest.raises(ValidationError):
        SourcePackage(parts=[make_part("same.zip"), make_part("same.zip")])


def test_part_name_must_not_contain_a_path():
    with pytest.raises(ValidationError):
        make_part("dir/export.zip")


def test_kind_specific_block_must_match_kind():
    with pytest.raises(ValidationError):
        make_object(ObjectKind.FILE, path="a.txt", mail={"labels": []})
    with pytest.raises(ValidationError):
        make_object(
            ObjectKind.CONTACT, path="c.vcf", original_id="c:1", event={"recurring": False}
        )


def test_files_and_folders_need_a_path():
    with pytest.raises(ValidationError):
        make_object(ObjectKind.FILE, path=None)


def test_share_entry_needs_a_principal_unless_anyone_with_link():
    with pytest.raises(ValidationError):
        make_object(path="a.txt", shared_with=[{"role": "viewer"}])
    shared = make_object(
        path="b.txt",
        shared_with=[{"principal_kind": "anyone_with_link", "role": "viewer"}],
    )
    assert shared.shared_with[0].principal is None


def test_provider_must_be_consistent():
    assert ProviderInfo().confidence is Confidence.NONE
    with pytest.raises(ValidationError):
        ProviderInfo(id="takeout", signals=[], confidence=Confidence.HIGH)
    with pytest.raises(ValidationError):
        ProviderInfo(id="takeout", signals=["archive_browser.html"], confidence=Confidence.NONE)
    with pytest.raises(ValidationError):
        ProviderInfo(id="unknown", confidence=Confidence.LOW)


def test_declared_hash_consistency():
    with pytest.raises(ValidationError):
        make_object(path="a.txt", integrity={"declared_matches": True})
    with pytest.raises(ValidationError):
        make_object(
            path="a.txt",
            integrity={"hash": HASH_A, "declared_hash": HASH_B, "declared_matches": True},
        )
    ok = make_object(
        path="b.txt",
        integrity={"hash": HASH_A, "declared_hash": HASH_A, "declared_matches": True},
    )
    assert ok.integrity.declared_matches is True


def test_format_is_normalised():
    item = make_object(path="a.txt", format={"mediatype": "Text/Plain", "extension": ".TXT"})
    assert item.format.mediatype == "text/plain"
    assert item.format.extension == "txt"


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        ManifestObject(
            id=derive_object_id(ObjectKind.FILE, "a.txt", None),
            kind=ObjectKind.FILE,
            path="a.txt",
            subject="should never be stored",
        )


def test_naive_timestamp_is_rejected_and_offsets_become_utc():
    with pytest.raises(ValidationError):
        make_manifest(generated_at=datetime(2026, 11, 1, 12, 0, 0))
    local = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=1)))
    manifest = make_manifest(generated_at=local)
    assert manifest.generated_at.utcoffset() == timedelta(0)
    assert '"generated_at": "2026-11-01T11:00:00Z"' in manifest.to_json()


def test_load_reports_missing_and_invalid_files(tmp_path):
    with pytest.raises(ManifestLoadError):
        Manifest.load(tmp_path / "missing.json")
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(ManifestLoadError):
        Manifest.load(broken)
    wrong_version = tmp_path / "wrong.json"
    data = json.loads(make_manifest().to_json())
    data["schema_version"] = "9.9"
    wrong_version.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ManifestLoadError):
        Manifest.load(wrong_version)


def test_write_to_missing_directory_raises_manifest_error(tmp_path):
    with pytest.raises(ManifestError):
        make_manifest().write(tmp_path / "no-such-dir" / "manifest.json")


def test_schema_file_matches_models():
    stored = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    assert stored == manifest_schema()