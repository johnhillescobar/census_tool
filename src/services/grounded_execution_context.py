"""Request-scoped constraints for grounded Census tool execution."""

from __future__ import annotations

from contextvars import ContextVar, Token

from pydantic import BaseModel, ConfigDict, Field

from src.services.grounded_plan_validator import ValidatedGroundedPlan


class GroundedExecutionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: ValidatedGroundedPlan
    allowed_years: list[int] = Field(default_factory=list)


_ACTIVE_CONTEXT: ContextVar[GroundedExecutionContext | None] = ContextVar(
    "census_grounded_execution_context",
    default=None,
)


def get_grounded_execution_context() -> GroundedExecutionContext | None:
    return _ACTIVE_CONTEXT.get()


def set_grounded_execution_context(context: GroundedExecutionContext) -> Token[GroundedExecutionContext | None]:
    return _ACTIVE_CONTEXT.set(context)


def reset_grounded_execution_context(token: Token[GroundedExecutionContext | None]) -> None:
    _ACTIVE_CONTEXT.reset(token)


def validate_grounded_api_request(
    *,
    dataset: str,
    year: int,
    variables: list[str],
    geo_for: dict[str, str],
    geo_in: dict[str, str],
    geo_in_chained: list[dict[str, str]] | None = None,
) -> str | None:
    """Return a fail-closed reason when a request escapes the validated plan."""
    context = get_grounded_execution_context()
    if context is None:
        return None

    grounded = context.plan
    table = grounded.table
    geography = grounded.geography
    if geography is None:
        return "Validated plan does not contain geography"
    if dataset != table.dataset or dataset != geography.dataset:
        return f"Dataset {dataset!r} is outside validated plan dataset {table.dataset!r}"
    allowed_years = set(context.allowed_years or table.years_available or [geography.year])
    if year not in allowed_years or year not in table.years_available:
        return f"Year {year} is outside validated table/year constraints"
    if geo_for != geography.geo_for or geo_in != dict(geography.geo_in):
        return "Geography values are outside the validated plan"
    if geo_in_chained:
        return "Chained geography values are outside the validated plan"

    table_code = table.table_code.upper()
    allowed_literals = {"NAME"}
    invalid_variable = next(
        (
            variable
            for variable in variables
            if variable.upper() not in allowed_literals
            and variable.upper() != f"GROUP({table_code})"
            and not variable.upper().startswith(f"{table_code}_")
        ),
        None,
    )
    if invalid_variable is not None:
        return f"Variable {invalid_variable!r} is outside validated table {table.table_code}"
    return None


__all__ = [
    "GroundedExecutionContext",
    "get_grounded_execution_context",
    "reset_grounded_execution_context",
    "set_grounded_execution_context",
    "validate_grounded_api_request",
]
