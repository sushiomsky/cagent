import json

from cagent.secret_scan import (
    SecretAllowlist,
    findings_json,
    format_findings,
    load_allowlist,
    redact_text,
    scan_text,
    scan_workspace,
    shannon_entropy,
)
from cagent.tools import WorkspaceTools
from cagent.trust import format_trust_status, is_trusted, load_trust, trust_workspace


def test_secret_scan_detects_and_redacts_env_secret_assignment():
    text = "API_KEY=1234567890abcdef\nnormal=value\n"

    findings = scan_text(text, path=".env")

    assert len(findings) == 1
    assert findings[0].kind == "env_secret_assignment"
    assert findings[0].severity == "medium"
    assert findings[0].entropy > 2.6
    assert "<REDACTED:env_secret_assignment>" in redact_text(text)
    assert "Likely secrets" in format_findings(findings)


def test_scan_workspace_skips_binary_and_reports_text_findings(tmp_path):
    (tmp_path / ".env").write_text("TOKEN=1234567890abcdef\n", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"\x00\x01secret")

    findings = scan_workspace(tmp_path)

    assert len(findings) == 1
    assert findings[0].path == ".env"


def test_secret_allowlist_filters_matching_lines(tmp_path):
    (tmp_path / ".env").write_text("TOKEN=1234567890abcdef\n", encoding="utf-8")
    (tmp_path / ".cagent-secret-allowlist").write_text(r"TOKEN=1234567890abcdef" + "\n", encoding="utf-8")

    findings = scan_workspace(tmp_path)

    assert findings == []
    assert load_allowlist(tmp_path).patterns


def test_allowlist_can_be_passed_to_scan_text():
    text = "TOKEN=1234567890abcdef\n"
    allowlist = SecretAllowlist(patterns=())

    assert scan_text(text, path=".env", allowlist=allowlist)
    assert not scan_text(text, path=".env", allowlist=SecretAllowlist(patterns=(__import__("re").compile("TOKEN="),)))


def test_findings_json_is_machine_readable():
    findings = scan_text("TOKEN=1234567890abcdef\n", path=".env")

    parsed = json.loads(findings_json(findings))

    assert parsed[0]["path"] == ".env"
    assert parsed[0]["severity"] == "medium"
    assert parsed[0]["entropy"] > 2.6


def test_entropy_filters_low_entropy_placeholders():
    assert shannon_entropy("aaaaaaaaaaaaaaaa") == 0
    assert not scan_text("TOKEN=aaaaaaaaaaaaaaaa\n", path=".env")


def test_critical_findings_sort_before_medium():
    findings = scan_text("TOKEN=1234567890abcdef\nsk-abcdefghijklmnopqrstuvwxyz012345\n", path=".env")

    assert findings[0].severity == "critical"


def test_workspace_tools_redact_file_output_by_default(tmp_path):
    (tmp_path / "settings.env").write_text("PASSWORD=1234567890abcdef\n", encoding="utf-8")
    tools = WorkspaceTools(
        workspace=tmp_path,
        allow_write=False,
        allow_shell=False,
        dry_run=False,
        shell_timeout_seconds=5,
    )

    result = tools.read_file(path="settings.env")

    assert result.ok
    assert "<REDACTED:env_secret_assignment>" in result.output
    assert "1234567890abcdef" not in result.output


def test_workspace_tools_can_disable_redaction_explicitly(tmp_path):
    (tmp_path / "settings.env").write_text("PASSWORD=1234567890abcdef\n", encoding="utf-8")
    tools = WorkspaceTools(
        workspace=tmp_path,
        allow_write=False,
        allow_shell=False,
        dry_run=False,
        shell_timeout_seconds=5,
        redact_secrets=False,
    )

    result = tools.read_file(path="settings.env")

    assert result.ok
    assert "1234567890abcdef" in result.output


def test_trust_workspace_roundtrip(tmp_path):
    info = trust_workspace(tmp_path, reason="Reviewed test workspace")

    assert info.trusted is True
    assert is_trusted(tmp_path)
    assert load_trust(tmp_path).reason == "Reviewed test workspace"  # type: ignore[union-attr]
    assert "Reviewed test workspace" in format_trust_status(tmp_path)
