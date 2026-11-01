import json
from pathlib import Path

from lsofframp.core.evidence import evidence_schema

SCHEMA_FILE = Path(__file__).resolve().parents[1] / "schemas" / "evidence.v0.1.json"


def test_evidence_schema_file_matches_models():
    stored = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    assert stored == evidence_schema()


def test_evidence_schema_requires_manifest_digest():
    assert "manifest_digest" in evidence_schema()["required"]
