from grok_search.services import PlanningService
from grok_search.state import StateRepository


def test_planning_persists_between_service_instances(tmp_path):
    state = StateRepository(tmp_path)
    first = PlanningService(state).process(
        "intent_analysis", "understand intent", phase_data={
            "core_question": "What changed?", "query_type": "factual", "time_sensitivity": "recent"
        },
    )
    session_id = first["session_id"]
    second = PlanningService(StateRepository(tmp_path)).process(
        "complexity_assessment", "simple task", session_id=session_id,
        phase_data={"level": 1, "estimated_sub_queries": 1, "estimated_tool_calls": 1, "justification": "direct"},
    )
    assert second["completed_phases"] == ["intent_analysis", "complexity_assessment"]

