from pathlib import Path

from cagent.secret_scan import format_findings, redact_text, scan_text, scan_workspace
from cagent.tools import WorkspaceTools
from cagent.trust import format_trust_status, is_trusted, load_trust, trust_workspace


def test_secret_scan_detects_and_redacts_env_secret_assignment():
    text = "API_KEY=1234567890abcdef\nnormal=value\n"

    findings = scan_text(text, path=".env")

    assert len(findings) == 1
    assert findings[0].kind == "env_secret_assignment"
    assert "<REDACTED:env_secret_assignment>" in redact_text(text)
    assert "Likely secrets" in format_findings(findings)


def test_scan_workspace_skips_binary_and_reports_text_findings(tmp_path):
    (tmp_path / ".env").write_text("TOKEN=1234567890abcdef\n", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"\x00\x01secret")

    findings = scan_workspace(tmp_path)

    assert len(findings) == 1
    assert findings[0].path == ".env"


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
