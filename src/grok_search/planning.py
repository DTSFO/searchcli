from pydantic import BaseModel, Field, ValidationError, field_validator
from typing import Optional, Literal
import uuid


class IntentOutput(BaseModel):
    core_question: str = Field(description="Distilled core question in one sentence")
    query_type: Literal["factual", "comparative", "exploratory", "analytical"] = Field(
        description="factual=single answer, comparative=A vs B, exploratory=broad understanding, analytical=deep reasoning"
    )
    time_sensitivity: Literal["realtime", "recent", "historical", "irrelevant"] = Field(
        description="realtime=today, recent=days/weeks, historical=months+, irrelevant=timeless"
    )
    domain: Optional[str] = Field(default=None, description="Specific domain if identifiable")
    premise_valid: Optional[bool] = Field(default=None, description="False if the question contains a flawed assumption")
    ambiguities: Optional[list[str]] = Field(default=None, description="Unresolved ambiguities that may affect search direction")
    unverified_terms: Optional[list[str]] = Field(
        default=None,
        description="External classifications, rankings, or taxonomies that may be incomplete or outdated "
        "in training data (e.g., 'CCF-A', 'Fortune 500', 'OWASP Top 10'). "
        "Each should become a prerequisite sub-query in Phase 3."
    )


class ComplexityOutput(BaseModel):
    level: Literal[1, 2, 3] = Field(
        description="1=simple (1-2 searches), 2=moderate (3-5 searches), 3=complex (6+ searches)"
    )
    estimated_sub_queries: int = Field(ge=1, le=20)
    estimated_tool_calls: int = Field(ge=1, le=50)
    justification: str


class SubQuery(BaseModel):
    id: str = Field(min_length=1, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$", description="Unique identifier (e.g., 'sq1')")
    goal: str
    expected_output: str = Field(description="What a successful result looks like")
    tool_hint: Optional[Literal["web_search", "web_fetch", "web_map"]] = Field(default=None, description="Suggested tool")
    boundary: str = Field(description="What this sub-query explicitly excludes — MUST state mutual exclusion with sibling sub-queries, not just the broader domain")
    depends_on: Optional[list[str]] = Field(default=None, description="IDs of prerequisite sub-queries")


class SearchTerm(BaseModel):
    term: str = Field(min_length=1, description="Search query string. MUST be ≤8 words.")
    purpose: str = Field(description="Single sub-query ID this term serves (e.g., 'sq2'). ONE term per sub-query — do NOT combine like 'sq1+sq2'.")
    round: int = Field(ge=1, description="Execution round: 1=broad discovery, 2+=targeted follow-up refined by round 1 findings")

    @field_validator("term")
    @classmethod
    def validate_term(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Search term must not be empty")
        if len(value.split()) > 8:
            raise ValueError("Search term must contain at most 8 words")
        return value


class StrategyOutput(BaseModel):
    approach: Literal["broad_first", "narrow_first", "targeted"] = Field(
        description="broad_first=wide then narrow, narrow_first=precise then expand, targeted=known-item"
    )
    search_terms: list[SearchTerm]
    fallback_plan: Optional[str] = Field(default=None, description="Fallback if primary searches fail")


class ToolPlanItem(BaseModel):
    sub_query_id: str
    tool: Literal["web_search", "web_fetch", "web_map"]
    reason: str
    params: Optional[dict] = Field(default=None, description="Tool-specific parameters")


class ExecutionOrderOutput(BaseModel):
    parallel: list[list[str]] = Field(description="Groups of sub-query IDs runnable in parallel")
    sequential: list[str] = Field(description="Sub-query IDs that must run in order")
    estimated_rounds: int = Field(ge=1)


PHASE_NAMES = [
    "intent_analysis",
    "complexity_assessment",
    "query_decomposition",
    "search_strategy",
    "tool_selection",
    "execution_order",
]

REQUIRED_PHASES: dict[int, set[str]] = {
    1: {"intent_analysis", "complexity_assessment", "query_decomposition"},
    2: {"intent_analysis", "complexity_assessment", "query_decomposition", "search_strategy", "tool_selection"},
    3: set(PHASE_NAMES),
}

_ACCUMULATIVE_LIST_PHASES = {"query_decomposition", "tool_selection"}
_MERGE_STRATEGY_PHASE = "search_strategy"
_SINGLETON_PHASES = {"intent_analysis", "complexity_assessment", "execution_order"}
_PHASE_MODELS = {
    "intent_analysis": IntentOutput,
    "complexity_assessment": ComplexityOutput,
    "query_decomposition": SubQuery,
    "tool_selection": ToolPlanItem,
    "execution_order": ExecutionOrderOutput,
}


def _split_csv(value: str) -> list[str]:
    return [s.strip() for s in value.split(",") if s.strip()] if value else []


class PhaseRecord(BaseModel):
    phase: str
    thought: str
    data: dict | list | None = None
    confidence: float = 1.0


class PlanningSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.phases: dict[str, PhaseRecord] = {}
        self.complexity_level: int | None = None

    @property
    def completed_phases(self) -> list[str]:
        return [p for p in PHASE_NAMES if p in self.phases]

    def required_phases(self) -> set[str]:
        return REQUIRED_PHASES.get(self.complexity_level or 3, REQUIRED_PHASES[3])

    def is_complete(self) -> bool:
        if self.complexity_level is None:
            return False
        return not self.validation_errors()

    def validation_errors(self) -> list[dict]:
        errors: list[dict] = []
        if self.complexity_level is None:
            return [{"code": "missing_complexity"}]
        for phase in self.required_phases() - self.phases.keys():
            errors.append({"code": "missing_phase", "phase": phase})
        sub_queries = self.phases.get("query_decomposition")
        items = sub_queries.data if sub_queries and isinstance(sub_queries.data, list) else []
        ids = [item.get("id") for item in items if isinstance(item, dict)]
        duplicate_ids = sorted({item for item in ids if item and ids.count(item) > 1})
        if duplicate_ids:
            errors.append({"code": "duplicate_sub_query_ids", "ids": duplicate_ids})
        known = {item for item in ids if item}
        for item in items:
            for dependency in item.get("depends_on") or []:
                if dependency not in known:
                    errors.append({"code": "unknown_dependency", "sub_query_id": item.get("id"), "depends_on": dependency})
        graph = {item.get("id"): item.get("depends_on") or [] for item in items if item.get("id")}
        visiting: set[str] = set()
        visited: set[str] = set()
        def visit(node: str) -> bool:
            if node in visiting: return True
            if node in visited: return False
            visiting.add(node)
            cyclic = any(dep in graph and visit(dep) for dep in graph[node])
            visiting.remove(node); visited.add(node)
            return cyclic
        if any(visit(node) for node in graph):
            errors.append({"code": "dependency_cycle"})
        complexity = self.phases.get("complexity_assessment")
        expected = (complexity.data or {}).get("estimated_sub_queries", 0) if complexity else 0
        if expected and len(known) < expected:
            errors.append({"code": "insufficient_sub_queries", "expected": expected, "actual": len(known)})
        if self.complexity_level and self.complexity_level >= 2:
            strategy = self.phases.get("search_strategy")
            purposes = {term.get("purpose") for term in (strategy.data or {}).get("search_terms", [])} if strategy else set()
            unknown_terms = sorted(purposes - known)
            if unknown_terms: errors.append({"code": "unknown_search_term_ids", "ids": unknown_terms})
            missing_terms = sorted(known - purposes)
            if missing_terms: errors.append({"code": "missing_search_terms", "ids": missing_terms})
            tools = self.phases.get("tool_selection")
            mapped = {item.get("sub_query_id") for item in (tools.data if tools and isinstance(tools.data, list) else [])}
            unknown_tools = sorted(mapped - known)
            if unknown_tools: errors.append({"code": "unknown_tool_mapping_ids", "ids": unknown_tools})
            missing_tools = sorted(known - mapped)
            if missing_tools: errors.append({"code": "missing_tool_mappings", "ids": missing_tools})
        expected_calls = (complexity.data or {}).get("estimated_tool_calls", 0) if complexity else 0
        tools = self.phases.get("tool_selection")
        actual_calls = len(tools.data) if tools and isinstance(tools.data, list) else len(known)
        if expected_calls and actual_calls < expected_calls:
            errors.append({"code": "insufficient_tool_calls", "expected": expected_calls, "actual": actual_calls})
        execution = self.phases.get("execution_order")
        if execution:
            data = execution.data or {}
            execution_ids = [item for group in data.get("parallel", []) for item in group] + data.get("sequential", [])
            duplicate_execution = sorted({item for item in execution_ids if execution_ids.count(item) > 1})
            if duplicate_execution: errors.append({"code": "duplicate_execution_ids", "ids": duplicate_execution})
            unknown_execution = sorted(set(execution_ids) - known)
            if unknown_execution: errors.append({"code": "unknown_execution_ids", "ids": unknown_execution})
            missing_execution = sorted(known - set(execution_ids))
            if missing_execution: errors.append({"code": "missing_execution_ids", "ids": missing_execution})
            parallel_groups = data.get("parallel", [])
            group_by_id = {item: index for index, group in enumerate(parallel_groups) for item in group}
            positions = {item: index for index, item in enumerate(execution_ids)}
            for node, dependencies in graph.items():
                for dependency in dependencies:
                    if node in group_by_id and group_by_id.get(node) == group_by_id.get(dependency):
                        errors.append({"code": "dependency_in_parallel_group", "sub_query_id": node, "depends_on": dependency})
                    if node in positions and dependency in positions and positions[dependency] >= positions[node]:
                        errors.append({"code": "dependency_order_violation", "sub_query_id": node, "depends_on": dependency})
        return errors

    def build_executable_plan(self) -> dict:
        return {name: record.data for name, record in self.phases.items()}

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "complexity_level": self.complexity_level,
            "phases": {name: record.model_dump() for name, record in self.phases.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlanningSession":
        session = cls(data["session_id"])
        session.complexity_level = data.get("complexity_level")
        session.phases = {
            name: PhaseRecord.model_validate(record)
            for name, record in (data.get("phases") or {}).items()
        }
        return session


class PlanningEngine:
    def __init__(self):
        self._sessions: dict[str, PlanningSession] = {}

    def get_session(self, session_id: str) -> PlanningSession | None:
        return self._sessions.get(session_id)

    def put_session(self, session: PlanningSession) -> None:
        self._sessions[session.session_id] = session

    def process_phase(
        self,
        phase: str,
        thought: str,
        session_id: str = "",
        is_revision: bool = False,
        revises_phase: str = "",
        confidence: float = 1.0,
        phase_data: dict | list | None = None,
    ) -> dict:
        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
        else:
            sid = session_id if session_id else uuid.uuid4().hex[:12]
            session = PlanningSession(sid)
            self._sessions[sid] = session

        target = revises_phase if is_revision and revises_phase else phase
        if target not in PHASE_NAMES:
            raise ValueError(f"Unknown phase: {target}. Valid: {', '.join(PHASE_NAMES)}")

        try:
            if target in _PHASE_MODELS:
                phase_data = _PHASE_MODELS[target].model_validate(phase_data).model_dump(exclude_none=True)
            elif target == "search_strategy":
                if not isinstance(phase_data, dict) or not phase_data.get("search_terms"):
                    raise ValueError("search_strategy requires search_terms")
                phase_data = dict(phase_data)
                phase_data["search_terms"] = [SearchTerm.model_validate(item).model_dump() for item in phase_data["search_terms"]]
                if phase_data.get("approach") not in (None, "", "broad_first", "narrow_first", "targeted"):
                    raise ValueError("Invalid search approach")
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

        if target in _SINGLETON_PHASES and target in session.phases and not is_revision:
            raise ValueError(f"Phase '{target}' already exists; use --revision to replace it")
        target_index = PHASE_NAMES.index(target)
        if target_index:
            predecessor = PHASE_NAMES[target_index - 1]
            if predecessor not in session.phases:
                raise ValueError(f"Phase '{target}' requires '{predecessor}' first")
        if is_revision:
            for stale in PHASE_NAMES[target_index:]:
                session.phases.pop(stale, None)
            if target == "intent_analysis":
                session.complexity_level = None

        if target in _ACCUMULATIVE_LIST_PHASES:
            if is_revision:
                session.phases[target] = PhaseRecord(
                    phase=target, thought=thought,
                    data=[phase_data] if not isinstance(phase_data, list) else phase_data,
                    confidence=confidence,
                )
            elif target in session.phases and isinstance(session.phases[target].data, list):
                session.phases[target].data.append(phase_data)
                session.phases[target].thought = thought
                session.phases[target].confidence = confidence
            else:
                session.phases[target] = PhaseRecord(
                    phase=target, thought=thought, data=[phase_data], confidence=confidence,
                )
        elif target == _MERGE_STRATEGY_PHASE:
            existing = session.phases.get(target)
            if is_revision:
                session.phases[target] = PhaseRecord(
                    phase=target, thought=thought, data=phase_data, confidence=confidence,
                )
            elif existing and isinstance(existing.data, dict) and isinstance(phase_data, dict):
                existing.data.setdefault("search_terms", []).extend(phase_data.get("search_terms", []))
                if phase_data.get("approach"):
                    existing.data["approach"] = phase_data["approach"]
                if phase_data.get("fallback_plan"):
                    existing.data["fallback_plan"] = phase_data["fallback_plan"]
                existing.thought = thought
                existing.confidence = confidence
            else:
                session.phases[target] = PhaseRecord(
                    phase=target, thought=thought, data=phase_data, confidence=confidence,
                )
        else:
            session.phases[target] = PhaseRecord(
                phase=target, thought=thought, data=phase_data, confidence=confidence,
            )

        if target == "complexity_assessment" and isinstance(phase_data, dict):
            level = phase_data.get("level")
            if level in (1, 2, 3):
                session.complexity_level = level
                for stale in PHASE_NAMES:
                    if stale not in session.required_phases():
                        session.phases.pop(stale, None)

        complete = session.is_complete()
        result: dict = {
            "session_id": session.session_id,
            "completed_phases": session.completed_phases,
            "complexity_level": session.complexity_level,
            "plan_complete": complete,
        }

        remaining = [p for p in PHASE_NAMES if p in session.required_phases() and p not in session.phases]
        if remaining:
            result["phases_remaining"] = remaining

        diagnostics = session.validation_errors()
        if diagnostics:
            result["validation_errors"] = diagnostics

        if complete:
            result["executable_plan"] = session.build_executable_plan()

        return result


engine = PlanningEngine()
