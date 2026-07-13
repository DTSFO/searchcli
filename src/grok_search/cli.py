from __future__ import annotations

import asyncio
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional

import typer
import click
from pydantic import AnyHttpUrl, TypeAdapter, ValidationError
from typer.core import TyperGroup

from .config import config
from .errors import AppError, ConfigAppError, UsageAppError
from .integrations import claude_builtins
from .output import OutputOptions, failure, render, success
from .services import ConfigService, ContentService, PlanningService, SearchService
from .state import StateRepository


_OUTPUT_FLAGS = {"--pretty", "--quiet"}


class OutputOptionsGroup(TyperGroup):
    """Accept global output flags in the common trailing position too."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        normalized = list(args)
        trailing: list[str] = []
        if "--" not in normalized:
            while normalized and normalized[-1] in _OUTPUT_FLAGS:
                trailing.append(normalized.pop())
        if trailing:
            normalized = [*reversed(trailing), *normalized]
        return super().parse_args(ctx, normalized)


app = typer.Typer(cls=OutputOptionsGroup, help="Agent-friendly web search CLI.", no_args_is_help=False, invoke_without_command=True, pretty_exceptions_enable=False)
sources_app = typer.Typer(help="Retrieve persisted search sources.")
config_app = typer.Typer(help="Inspect and import configuration.")
model_app = typer.Typer(help="List or switch Grok models.")
plan_app = typer.Typer(help="Build a persistent multi-phase search plan.")
session_app = typer.Typer(help="Manage persistent planning and source sessions.")
integrations_app = typer.Typer(help="Manage optional agent integrations.")
claude_app = typer.Typer(help="Manage Claude Code integration.")
app.add_typer(sources_app, name="sources")
app.add_typer(config_app, name="config")
app.add_typer(model_app, name="model")
app.add_typer(plan_app, name="plan")
app.add_typer(session_app, name="session")
app.add_typer(integrations_app, name="integrations")
integrations_app.add_typer(claude_app, name="claude")


class Runtime:
    options = OutputOptions()


runtime = Runtime()


def package_version() -> str:
    try:
        return version("grok-search")
    except PackageNotFoundError:
        return "0.0.0+local"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(package_version())
        raise typer.Exit()


@app.callback()
def root(
    ctx: typer.Context,
    pretty: bool = typer.Option(False, "--pretty", help="Render indented human-readable JSON."),
    quiet: bool = typer.Option(False, "--quiet", help="Print only the command's core result."),
    version_flag: Optional[bool] = typer.Option(None, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."),
) -> None:
    if pretty and quiet:
        raise UsageAppError("--pretty and --quiet are mutually exclusive")
    runtime.options = OutputOptions(pretty=pretty, quiet=quiet)
    if ctx.invoked_subcommand is None and not version_flag:
        raise UsageAppError("A command is required; run 'search --help' for usage")


def _emit(command: str, data, meta: dict | None = None, quiet_value=None) -> None:
    typer.echo(render(success(command, data, meta), runtime.options, quiet_value))


def _run(awaitable):
    return asyncio.run(awaitable)


def _url(value: str) -> str:
    try:
        return str(TypeAdapter(AnyHttpUrl).validate_python(value))
    except ValidationError as exc:
        raise UsageAppError("URL must be a valid HTTP(S) URL") from exc


@app.command("search")
def search(query: str, platform: str = "", model: str = "", extra_sources: int = typer.Option(0, min=0)) -> None:
    data = _run(SearchService().search(query, platform, model, extra_sources))
    _emit("search", data, {"warnings": data.pop("warnings", [])}, data["content"])


@sources_app.command("get")
def sources_get(session_id: str) -> None:
    data = SearchService().sources(session_id)
    _emit("sources.get", data, quiet_value=data["sources"])


@app.command("fetch")
def fetch(url: str) -> None:
    data = _run(ContentService().fetch(_url(url)))
    _emit("fetch", data, {"warnings": data.pop("warnings", [])}, data["content"])


@app.command("map")
def map_site(url: str, instructions: str = "", max_depth: int = typer.Option(1, min=1, max=5),
             max_breadth: int = typer.Option(20, min=1, max=500), limit: int = typer.Option(50, min=1, max=500),
             timeout: int = typer.Option(150, min=10, max=150)) -> None:
    data = _run(ContentService().map(_url(url), instructions, max_depth, max_breadth, limit, timeout))
    _emit("map", data, quiet_value=data.get("results"))


@config_app.command("show")
def config_show(check: bool = typer.Option(False, "--check")) -> None:
    _emit("config.show", _run(ConfigService().show(check)))


@config_app.command("import-env")
def config_import_env(file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True)) -> None:
    _emit("config.import-env", ConfigService().import_env(file))


@model_app.command("list")
def model_list() -> None:
    models = _run(SearchService().models())
    _emit("model.list", {"models": models, "count": len(models)}, quiet_value=models)


@model_app.command("current")
def model_current() -> None:
    _emit("model.current", {"model": config.grok_model}, quiet_value=config.grok_model)


@model_app.command("set")
def model_set(model: str) -> None:
    previous = config.grok_model
    try:
        config.set_model(model)
    except ValueError as exc:
        raise ConfigAppError(str(exc)) from exc
    _emit("model.set", {"previous_model": previous, "current_model": config.grok_model}, quiet_value=config.grok_model)


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@plan_app.command("intent")
def plan_intent(thought: str = typer.Option(...), core_question: str = typer.Option(...),
                query_type: str = typer.Option(...), time_sensitivity: str = typer.Option(...),
                session_id: str = typer.Option("", help="Existing planning session ID; cannot create a named session."), confidence: float = 1.0, domain: str = "",
                premise_valid: Optional[bool] = None, ambiguities: str = "", unverified_terms: str = "",
                revision: bool = False) -> None:
    data = {"core_question": core_question, "query_type": query_type, "time_sensitivity": time_sensitivity}
    if domain: data["domain"] = domain
    if premise_valid is not None: data["premise_valid"] = premise_valid
    if ambiguities: data["ambiguities"] = _csv(ambiguities)
    if unverified_terms: data["unverified_terms"] = _csv(unverified_terms)
    result = PlanningService().process("intent_analysis", thought, session_id, revision, confidence, data)
    _emit("plan.intent", result, quiet_value=result["session_id"])


@plan_app.command("complexity")
def plan_complexity(session_id: str, thought: str = typer.Option(...), level: int = typer.Option(..., min=1, max=3),
                    estimated_sub_queries: int = typer.Option(..., min=1, max=20),
                    estimated_tool_calls: int = typer.Option(..., min=1, max=50),
                    justification: str = typer.Option(...), confidence: float = 1.0, revision: bool = False) -> None:
    data = {"level": level, "estimated_sub_queries": estimated_sub_queries,
            "estimated_tool_calls": estimated_tool_calls, "justification": justification}
    _emit("plan.complexity", PlanningService().process("complexity_assessment", thought, session_id, revision, confidence, data))


@plan_app.command("sub-query")
def plan_sub_query(session_id: str, thought: str = typer.Option(...), id: str = typer.Option(...),
                   goal: str = typer.Option(...), expected_output: str = typer.Option(...), boundary: str = typer.Option(...),
                   depends_on: str = "", tool_hint: str = "", confidence: float = 1.0, revision: bool = False) -> None:
    data = {"id": id, "goal": goal, "expected_output": expected_output, "boundary": boundary}
    if depends_on: data["depends_on"] = _csv(depends_on)
    if tool_hint: data["tool_hint"] = tool_hint
    _emit("plan.sub-query", PlanningService().process("query_decomposition", thought, session_id, revision, confidence, data))


@plan_app.command("search-term")
def plan_search_term(session_id: str, thought: str = typer.Option(...), term: str = typer.Option(...),
                     purpose: str = typer.Option(...), round_: int = typer.Option(..., "--round", min=1),
                     approach: str = "", fallback_plan: str = "", confidence: float = 1.0, revision: bool = False) -> None:
    data = {"search_terms": [{"term": term, "purpose": purpose, "round": round_}]}
    if approach: data["approach"] = approach
    if fallback_plan: data["fallback_plan"] = fallback_plan
    _emit("plan.search-term", PlanningService().process("search_strategy", thought, session_id, revision, confidence, data))


@plan_app.command("tool-mapping")
def plan_tool_mapping(session_id: str, thought: str = typer.Option(...), sub_query_id: str = typer.Option(...),
                      tool: str = typer.Option(...), reason: str = typer.Option(...), params_json: str = "",
                      confidence: float = 1.0, revision: bool = False) -> None:
    data = {"sub_query_id": sub_query_id, "tool": tool, "reason": reason}
    if params_json:
        try: data["params"] = json.loads(params_json)
        except json.JSONDecodeError as exc: raise UsageAppError("--params-json must be valid JSON") from exc
    _emit("plan.tool-mapping", PlanningService().process("tool_selection", thought, session_id, revision, confidence, data))


@plan_app.command("execution")
def plan_execution(session_id: str, thought: str = typer.Option(...), parallel_groups: str = typer.Option(...),
                   sequential: str = typer.Option(...), estimated_rounds: int = typer.Option(..., min=1),
                   confidence: float = 1.0, revision: bool = False) -> None:
    data = {"parallel": [_csv(group) for group in parallel_groups.split(";") if group.strip()],
            "sequential": _csv(sequential), "estimated_rounds": estimated_rounds}
    _emit("plan.execution", PlanningService().process("execution_order", thought, session_id, revision, confidence, data))


def _kind(value: str) -> str | None:
    if value == "all": return None
    if value not in {"planning", "sources"}: raise UsageAppError("--kind must be planning, sources, or all")
    return value


@session_app.command("list")
def session_list(kind: str = "all") -> None:
    records = StateRepository().list(_kind(kind))
    _emit("session.list", {"sessions": records, "count": len(records)}, quiet_value=records)


@session_app.command("show")
def session_show(session_id: str, kind: str = "planning") -> None:
    record = StateRepository().load(_kind(kind) or "planning", session_id, refresh=False)
    _emit("session.show", record, quiet_value=record["data"])


@session_app.command("delete")
def session_delete(session_id: str, kind: str = "planning") -> None:
    deleted = StateRepository().delete(_kind(kind) or "planning", session_id)
    _emit("session.delete", {"session_id": session_id, "deleted": deleted})


@session_app.command("clear")
def session_clear(kind: str = "all") -> None:
    count = StateRepository().clear(_kind(kind))
    _emit("session.clear", {"deleted_count": count}, quiet_value=count)


def _claude(action: str, project_root: Optional[Path]) -> None:
    _emit(f"integrations.claude.{action}", claude_builtins(action, project_root))


@claude_app.command("status")
def claude_status(project_root: Optional[Path] = typer.Option(None, "--project-root")) -> None: _claude("status", project_root)


@claude_app.command("disable-builtins")
def claude_disable(project_root: Optional[Path] = typer.Option(None, "--project-root")) -> None: _claude("disable", project_root)


@claude_app.command("enable-builtins")
def claude_enable(project_root: Optional[Path] = typer.Option(None, "--project-root")) -> None: _claude("enable", project_root)


def main() -> None:
    try:
        app(standalone_mode=False)
    except AppError as exc:
        typer.echo(render(failure("cli", exc.code, exc.message, exc.details), runtime.options), err=True)
        raise SystemExit(exc.exit_code) from exc
    except typer.Exit as exc:
        raise SystemExit(exc.exit_code) from exc
    except click.ClickException as exc:
        typer.echo(render(failure("cli", "usage_error", exc.format_message()), runtime.options), err=True)
        raise SystemExit(2) from exc
    except Exception as exc:
        if getattr(exc, "exit_code", None) == 2 and hasattr(exc, "format_message"):
            typer.echo(render(failure("cli", "usage_error", exc.format_message()), runtime.options), err=True)
            raise SystemExit(2) from exc
        typer.echo(render(failure("cli", "internal_error", str(exc)), runtime.options), err=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
