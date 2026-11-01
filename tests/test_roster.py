from datetime import date

import pytest

from lsofframp.core.roster import MAX_ROSTER_ROWS, Roster, RosterLoadError

AS_OF = date(2026, 10, 1)


def write(tmp_path, text: str, name: str = "roster.csv", encoding: str = "utf-8"):
    target = tmp_path / name
    target.write_bytes(text.encode(encoding))
    return target


def test_minimal_roster_is_read(tmp_path):
    text = "email,active\nAnna@Example.org,true\nben@example.org,no\n"
    roster = Roster.load(write(tmp_path, text), AS_OF)
    assert [(m.email, m.active) for m in roster.members] == [
        ("anna@example.org", True),
        ("ben@example.org", False),
    ]
    assert roster.info.row_count == 2
    assert roster.info.as_of == AS_OF
    assert roster.info.sha256.startswith("sha256:")


def test_optional_columns_and_extra_columns(tmp_path):
    text = (
        "Email,Active,Name,Role,Phone\n"
        "anna@example.org,ja,Anna,Chair,123\n"
        "ben@example.org,1,,,\n"
    )
    roster = Roster.load(write(tmp_path, text), AS_OF)
    assert roster.members[0].name == "Anna"
    assert roster.members[0].role == "Chair"
    assert roster.members[1].name is None


def test_semicolon_delimiter_and_byte_order_mark(tmp_path):
    target = tmp_path / "roster.csv"
    content = "email;active;name\nanna@example.org;ja;Jürgen\n"
    target.write_bytes(b"\xef\xbb\xbf" + content.encode())
    roster = Roster.load(target, AS_OF)
    assert roster.members[0].name == "Jürgen"


def test_blank_rows_are_skipped(tmp_path):
    roster = Roster.load(write(tmp_path, "email,active\n\nanna@example.org,true\n,\n"), AS_OF)
    assert roster.info.row_count == 1


def test_find_ignores_case_and_spaces(tmp_path):
    roster = Roster.load(write(tmp_path, "email,active\nanna@example.org,true\n"), AS_OF)
    assert roster.find("  ANNA@example.org ") is not None
    assert roster.find("other@example.org") is None


def test_hash_follows_the_file_bytes(tmp_path):
    first = Roster.load(write(tmp_path, "email,active\na@example.org,true\n", "a.csv"), AS_OF)
    same = Roster.load(write(tmp_path, "email,active\na@example.org,true\n", "b.csv"), AS_OF)
    other = Roster.load(write(tmp_path, "email,active\na@example.org,false\n", "c.csv"), AS_OF)
    assert first.info.sha256 == same.info.sha256 != other.info.sha256


@pytest.mark.parametrize(
    "text",
    [
        "",
        "\n",
        "email\nanna@example.org\n",
        "active\ntrue\n",
        "email,email,active\na@example.org,a@example.org,true\n",
        "email,active\nnot-an-address,true\n",
        "email,active\nanna@example.org,maybe\n",
        "email,active\nanna@example.org,\n",
        "email,active\nanna@example.org,true,extra\n",
        "email,active\nanna@example.org,true\nANNA@example.org,false\n",
    ],
)
def test_invalid_rosters_are_rejected(tmp_path, text):
    with pytest.raises(RosterLoadError):
        Roster.load(write(tmp_path, text), AS_OF)


def test_errors_do_not_reveal_cell_contents(tmp_path):
    target = write(tmp_path, "email,active\nsecret-person@example.org,perhaps\n")
    with pytest.raises(RosterLoadError) as caught:
        Roster.load(target, AS_OF)
    assert "secret-person" not in str(caught.value)
    assert "perhaps" not in str(caught.value)
    assert "row 2" in str(caught.value)


def test_missing_and_non_utf8_files(tmp_path):
    with pytest.raises(RosterLoadError):
        Roster.load(tmp_path / "missing.csv", AS_OF)
    with pytest.raises(RosterLoadError):
        target = write(tmp_path, "email,active\nä@example.org,true\n", encoding="latin-1")
        Roster.load(target, AS_OF)


def test_row_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("lsofframp.core.roster.MAX_ROSTER_ROWS", 2)
    text = "email,active\n" + "".join(f"u{i}@example.org,true\n" for i in range(3))
    with pytest.raises(RosterLoadError):
        Roster.load(write(tmp_path, text), AS_OF)
    assert MAX_ROSTER_ROWS == 100_000
