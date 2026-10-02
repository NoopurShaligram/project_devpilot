from forge_advisor.graph.workflow import graph


def test_explanation_recommends_chat():
    result = graph.invoke({"task": "Explain why Python lists are mutable"})
    response = result["response"]
    assert response.recommended_interface.value == "chat"
    assert response.risk.value == "low"


def test_feature_with_tests_recommends_coding_agent():
    result = graph.invoke({"task": "Implement OAuth login in the FastAPI backend and run tests"})
    response = result["response"]
    assert response.recommended_interface.value == "coding_agent"
    assert response.requires_human_approval is True
    assert "terminal/test runner" in response.required_capabilities


def test_production_is_critical():
    result = graph.invoke({"task": "Deploy this service to production"})
    response = result["response"]
    assert response.risk.value == "critical"
    assert response.requires_human_approval is True
