from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_readme_links_core_telegram_docs():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/native_telegram_sdk.md" in readme
    assert "docs/live_telegram_verification.md" in readme
    assert "docs/railway_template.md" in readme


def test_completion_audit_links_live_runbook_and_sdk_docs():
    audit = (ROOT / "docs" / "telegram_v10_completion_audit.md").read_text(encoding="utf-8")

    assert "docs/native_telegram_sdk.md" in audit
    assert "docs/live_telegram_verification.md" in audit


def test_completion_audit_mentions_recent_v10_field_and_parameter_gates():
    audit = (ROOT / "docs" / "telegram_v10_completion_audit.md").read_text(encoding="utf-8")

    assert "recent_field_missing=0" in audit
    assert "recent_method_parameter_missing=0" in audit


def test_live_runbook_documents_strict_bot_to_bot_gate():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "live_telegram_verification.md").read_text(encoding="utf-8")
    audit = (ROOT / "docs" / "telegram_v10_completion_audit.md").read_text(encoding="utf-8")

    assert "TELEGRAM_REQUIRE_BOT_TO_BOT=1" in readme
    assert "TELEGRAM_REQUIRE_BOT_TO_BOT=\"1\"" in runbook
    assert "TELEGRAM_REQUIRE_BOT_TO_BOT=\"1\"" in audit
