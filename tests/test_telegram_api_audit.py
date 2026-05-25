import scripts.audit_telegram_api_surface as audit


def test_recent_change_audit_requirements_are_satisfied_locally():
    assert audit._missing_recent_fields() == []
    assert audit._missing_recent_method_parameters() == []
    assert "guest_query_id" in audit.RECENT_FIELD_REQUIREMENTS["Message"]
    assert "result" in audit.RECENT_METHOD_PARAMETER_REQUIREMENTS["answer_guest_query"]
