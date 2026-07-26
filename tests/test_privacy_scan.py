from __future__ import annotations

from pathlib import Path

from scripts import privacy_scan
from scripts.privacy_scan import scan

_EMAIL_FIXTURE = "person" + chr(64) + "example.com"


def test_scanner_source_is_self_scannable(tmp_path) -> None:
    source = Path(privacy_scan.__file__)
    candidate = tmp_path / source.name
    candidate.write_bytes(source.read_bytes())

    assert scan(tmp_path) == []


def test_privacy_scan_reports_only_redacted_location(tmp_path) -> None:
    value = _EMAIL_FIXTURE
    sensitive_filename = "private-notes.txt"
    (tmp_path / sensitive_filename).write_text(
        f"contact={value}\n",
        encoding="utf-8",
    )

    findings = scan(tmp_path)

    assert [(item.kind, item.line, item.path) for item in findings] == [
        ("email_address", 1, "<redacted-path>")
    ]
    assert value not in repr(findings)
    assert sensitive_filename not in repr(findings)


def test_privacy_scan_accepts_external_literal_denylist(tmp_path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "note.txt").write_text("internal-alias\n", encoding="utf-8")
    denylist = tmp_path / "denylist.txt"
    denylist.write_text("internal-alias\n", encoding="utf-8")

    findings = scan(
        repository,
        denylist_file=denylist,
        require_denylist=True,
    )

    assert [(item.kind, item.line, item.path) for item in findings] == [
        ("denylist_literal_1", 1, "<redacted-path>")
    ]


def test_denylist_nfkc_casefold_and_cross_line_match(tmp_path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "note.txt").write_text("ＳＥＣＲＥＴ-\nAlias\n", encoding="utf-8")
    denylist = tmp_path / "denylist.txt"
    denylist.write_text("\ufeffsecret-alias\n", encoding="utf-8")

    findings = scan(
        repository,
        denylist_file=denylist,
        require_denylist=True,
    )

    assert [(item.kind, item.line, item.path) for item in findings] == [
        ("denylist_literal_1", 0, "<redacted-path>")
    ]
