from forge_advisor.graph.workflow import graph


def advise(task: str):
    return graph.invoke({"task": task})["response"]


def test_explanation_uses_chat_and_low_risk():
    response = advise("Explain why Python lists are mutable")
    assert response.recommended_interface.value == "chat"
    assert response.risk.value == "low"
    assert response.requires_human_approval is False


def test_feature_with_tests_uses_coding_agent():
    response = advise("Implement OAuth login in the FastAPI backend and run tests")
    assert response.recommended_interface.value == "coding_agent"
    assert response.risk.value == "medium"
    assert response.requires_human_approval is True
    assert "terminal/test runner" in response.required_capabilities


def test_production_is_critical():
    response = advise("Deploy this service to production")
    assert response.risk.value == "critical"
    assert response.requires_human_approval is True
    assert "Approve before any production-affecting action" in response.approval_points


def test_data_deletion_is_high_risk():
    response = advise("Delete old customer records from PostgreSQL")
    assert response.risk.value == "high"
    assert response.requires_human_approval is True
    assert "external integrations" in response.required_capabilities


def test_debugging_with_tests_uses_coding_agent():
    response = advise("Debug the failing checkout endpoint and run pytest")
    assert response.analysis.category.value == "debugging"
    assert response.recommended_interface.value == "coding_agent"
    assert response.risk.value == "medium"
