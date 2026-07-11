from grok_search.services import PlanningService
from grok_search.state import StateRepository
from concurrent.futures import ProcessPoolExecutor


def _phase(service, phase, session_id="", data=None, revision=False):
    return service.process(phase, phase, session_id=session_id, is_revision=revision, phase_data=data)


def _append_sub_query(root, session_id, item_id):
    service = PlanningService(StateRepository(root))
    return _phase(service, "query_decomposition", session_id, {
        "id": item_id, "goal": item_id, "expected_output": "o", "boundary": "b"
    })


def _level3_before_execution(tmp_path, depends=False):
    service = PlanningService(StateRepository(tmp_path))
    sid = _phase(service, "intent_analysis", data={"core_question": "q", "query_type": "factual", "time_sensitivity": "recent"})["session_id"]
    _phase(service, "complexity_assessment", sid, {"level": 3, "estimated_sub_queries": 2, "estimated_tool_calls": 2, "justification": "x"})
    _phase(service, "query_decomposition", sid, {"id": "sq1", "goal": "g1", "expected_output": "o", "boundary": "b"})
    _phase(service, "query_decomposition", sid, {"id": "sq2", "goal": "g2", "expected_output": "o", "boundary": "b", "depends_on": ["sq1"] if depends else []})
    _phase(service, "search_strategy", sid, {"approach": "targeted", "search_terms": [{"term": "one", "purpose": "sq1", "round": 1}]})
    _phase(service, "search_strategy", sid, {"search_terms": [{"term": "two", "purpose": "sq2", "round": 1}]})
    _phase(service, "tool_selection", sid, {"sub_query_id": "sq1", "tool": "web_search", "reason": "r"})
    _phase(service, "tool_selection", sid, {"sub_query_id": "sq2", "tool": "web_search", "reason": "r"})
    return service, sid


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


def test_plan_requires_valid_dependencies_and_estimated_count(tmp_path):
    service = PlanningService(StateRepository(tmp_path))
    result = _phase(service, "intent_analysis", data={"core_question": "q", "query_type": "factual", "time_sensitivity": "recent"})
    sid = result["session_id"]
    _phase(service, "complexity_assessment", sid, {"level": 1, "estimated_sub_queries": 2, "estimated_tool_calls": 2, "justification": "x"})
    result = _phase(service, "query_decomposition", sid, {"id": "sq1", "goal": "g", "expected_output": "o", "boundary": "b", "depends_on": ["ghost"]})
    assert result["plan_complete"] is False
    codes = {item["code"] for item in result["validation_errors"]}
    assert {"unknown_dependency", "insufficient_sub_queries"} <= codes


def test_revision_discards_downstream_and_complexity_downgrade(tmp_path):
    service = PlanningService(StateRepository(tmp_path))
    sid = _phase(service, "intent_analysis", data={"core_question": "q", "query_type": "factual", "time_sensitivity": "recent"})["session_id"]
    _phase(service, "complexity_assessment", sid, {"level": 2, "estimated_sub_queries": 1, "estimated_tool_calls": 1, "justification": "x"})
    _phase(service, "query_decomposition", sid, {"id": "sq1", "goal": "g", "expected_output": "o", "boundary": "b"})
    _phase(service, "search_strategy", sid, {"approach": "targeted", "search_terms": [{"term": "short term", "purpose": "sq1", "round": 1}]})
    complete = _phase(service, "tool_selection", sid, {"sub_query_id": "sq1", "tool": "web_search", "reason": "r"})
    assert complete["plan_complete"] is True
    revised = _phase(service, "complexity_assessment", sid, {"level": 1, "estimated_sub_queries": 1, "estimated_tool_calls": 1, "justification": "simple"}, revision=True)
    assert revised["completed_phases"] == ["intent_analysis", "complexity_assessment"]
    assert "executable_plan" not in revised


def test_singleton_phase_requires_revision(tmp_path):
    service = PlanningService(StateRepository(tmp_path))
    sid = _phase(service, "intent_analysis", data={"core_question": "q", "query_type": "factual", "time_sensitivity": "recent"})["session_id"]
    import pytest
    with pytest.raises(Exception, match="use --revision"):
        _phase(service, "intent_analysis", sid, {"core_question": "q2", "query_type": "factual", "time_sensitivity": "recent"})


def test_phase_order_is_enforced(tmp_path):
    import pytest
    with pytest.raises(Exception, match="requires 'intent_analysis'"):
        _phase(PlanningService(StateRepository(tmp_path)), "complexity_assessment", data={
            "level": 1, "estimated_sub_queries": 1, "estimated_tool_calls": 1, "justification": "x"
        })


def test_concurrent_updates_preserve_all_sub_queries(tmp_path):
    service = PlanningService(StateRepository(tmp_path))
    sid = _phase(service, "intent_analysis", data={"core_question": "q", "query_type": "factual", "time_sensitivity": "recent"})["session_id"]
    _phase(service, "complexity_assessment", sid, {"level": 1, "estimated_sub_queries": 4, "estimated_tool_calls": 4, "justification": "x"})
    with ProcessPoolExecutor(max_workers=4) as pool:
        list(pool.map(_append_sub_query, [tmp_path] * 4, [sid] * 4, ["sq1", "sq2", "sq3", "sq4"]))
    record = StateRepository(tmp_path).load("planning", sid, refresh=False)
    items = record["data"]["phases"]["query_decomposition"]["data"]
    assert {item["id"] for item in items} == {"sq1", "sq2", "sq3", "sq4"}


def test_execution_rejects_dependency_inside_parallel_group(tmp_path):
    service, sid = _level3_before_execution(tmp_path, depends=True)
    result = _phase(service, "execution_order", sid, {"parallel": [["sq1", "sq2"]], "sequential": [], "estimated_rounds": 1})
    assert result["plan_complete"] is False
    assert "dependency_in_parallel_group" in {item["code"] for item in result["validation_errors"]}


def test_execution_rejects_duplicate_ids(tmp_path):
    service, sid = _level3_before_execution(tmp_path)
    result = _phase(service, "execution_order", sid, {"parallel": [["sq1", "sq2"]], "sequential": ["sq1"], "estimated_rounds": 1})
    assert "duplicate_execution_ids" in {item["code"] for item in result["validation_errors"]}


def test_planning_field_constraints(tmp_path):
    import pytest
    service = PlanningService(StateRepository(tmp_path))
    sid = _phase(service, "intent_analysis", data={"core_question": "q", "query_type": "factual", "time_sensitivity": "recent"})["session_id"]
    _phase(service, "complexity_assessment", sid, {"level": 1, "estimated_sub_queries": 1, "estimated_tool_calls": 1, "justification": "x"})
    for data in (
        {"id": "", "goal": "g", "expected_output": "o", "boundary": "b"},
        {"id": "sq1", "goal": "g", "expected_output": "o", "boundary": "b", "tool_hint": "banana"},
    ):
        with pytest.raises(Exception):
            _phase(service, "query_decomposition", sid, data)


def test_search_term_constraints_and_multiple_tool_calls(tmp_path):
    import pytest
    service = PlanningService(StateRepository(tmp_path))
    sid = _phase(service, "intent_analysis", data={"core_question": "q", "query_type": "factual", "time_sensitivity": "recent"})["session_id"]
    _phase(service, "complexity_assessment", sid, {"level": 2, "estimated_sub_queries": 1, "estimated_tool_calls": 2, "justification": "x"})
    _phase(service, "query_decomposition", sid, {"id": "sq1", "goal": "g", "expected_output": "o", "boundary": "b"})
    for term in ("   ", "one two three four five six seven eight nine"):
        with pytest.raises(Exception):
            _phase(service, "search_strategy", sid, {"approach": "targeted", "search_terms": [{"term": term, "purpose": "sq1", "round": 1}]})
    _phase(service, "search_strategy", sid, {"approach": "targeted", "search_terms": [{"term": "valid", "purpose": "sq1", "round": 1}]})
    _phase(service, "tool_selection", sid, {"sub_query_id": "sq1", "tool": "web_search", "reason": "first"})
    result = _phase(service, "tool_selection", sid, {"sub_query_id": "sq1", "tool": "web_fetch", "reason": "second"})
    assert result["plan_complete"] is True


def test_intent_revision_resets_complexity(tmp_path):
    service = PlanningService(StateRepository(tmp_path))
    sid = _phase(service, "intent_analysis", data={"core_question": "q", "query_type": "factual", "time_sensitivity": "recent"})["session_id"]
    _phase(service, "complexity_assessment", sid, {"level": 1, "estimated_sub_queries": 1, "estimated_tool_calls": 1, "justification": "x"})
    result = _phase(service, "intent_analysis", sid, {"core_question": "new", "query_type": "factual", "time_sensitivity": "recent"}, revision=True)
    assert result["complexity_level"] is None
    assert result["completed_phases"] == ["intent_analysis"]
