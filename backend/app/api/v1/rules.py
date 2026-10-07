"""Detection rule management endpoints (/api/v1/rules).

Routes translate HTTP to RuleService calls only. Every response, including
errors, uses the same envelope:
  success:  {"success": true, ...}
  failure:  {"success": false, "message": "...", "error_code": "RULE_NOT_FOUND", "details": [...optional]}
Errors never include stack traces, connection details or submitted values.
"""

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pymongo.database import Database

from app.core.database import get_database
from app.core.errors import DatabaseUnavailableError, summarize_validation_errors
from app.models.common import Severity
from app.models.rule import RuleCategory
from app.models.rule_management import (
    ErrorResponse,
    RuleCreateRequest,
    RuleDeleteResponse,
    RuleDetail,
    RuleListResponse,
    RuleResponse,
    RuleStatusRequest,
    RuleStatusResponse,
    RuleSummary,
    RuleUpdateRequest,
)
from app.repositories.detection_rule_repository import MAX_PAGE_LIMIT, DetectionRuleRepository
from app.services.rule_service import (
    DEFAULT_PAGE_LIMIT,
    RuleService,
    RuleServiceError,
)

_STATUS_BY_CODE = {
    "RULE_NOT_FOUND": 404,
    "RULE_ALREADY_EXISTS": 409,
    "RULE_PROTECTED": 409,
}
_VALIDATION_STATUS = 422

# Request field -> error code for schema-level validation failures.
_CODE_BY_FIELD = {
    "category": "INVALID_CATEGORY",
    "severity": "INVALID_SEVERITY",
    "conditions": "INVALID_CONDITION",
    "enabled": "INVALID_STATUS",
}


def _error(status: int, code: str, message: str, details: list[dict[str, str]] | None = None) -> JSONResponse:
    body = ErrorResponse(message=message, error_code=code, details=details)
    return JSONResponse(status_code=status, content=body.model_dump(exclude_none=True))


class RuleRoute(APIRoute):
    """Turns request-validation and service errors into the rule error envelope."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except RequestValidationError as exc:
                details = summarize_validation_errors(exc.errors())
                code = "INVALID_RULE"
                for error in exc.errors():
                    field = str(error["loc"][-1]) if error.get("loc") else ""
                    if field in _CODE_BY_FIELD:
                        code = _CODE_BY_FIELD[field]
                        break
                return _error(_VALIDATION_STATUS, code, "Invalid detection rule request", details)
            except RuleServiceError as exc:
                status = _STATUS_BY_CODE.get(exc.error_code, _VALIDATION_STATUS)
                return _error(status, exc.error_code, exc.message, exc.details)
            except DatabaseUnavailableError:
                return _error(503, "DATABASE_UNAVAILABLE", "Database is unavailable")

        return handler


router = APIRouter(prefix="/rules", tags=["rules"], route_class=RuleRoute)

_ERRORS = {404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}


def get_rule_service(database: Database = Depends(get_database)) -> RuleService:
    return RuleService(DetectionRuleRepository(database))


ServiceDep = Annotated[RuleService, Depends(get_rule_service)]
RuleIdPath = Annotated[str, Path(min_length=1, max_length=32)]


@router.get("", response_model=RuleListResponse, responses=_ERRORS)
def list_rules(
    service: ServiceDep,
    category: RuleCategory | None = None,
    severity: Severity | None = None,
    enabled: bool | None = None,
    name: Annotated[str | None, Query(min_length=1, max_length=120, description="Case-insensitive name search")] = None,
    page: Annotated[int, Query(ge=1, le=100_000)] = 1,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
) -> RuleListResponse:
    """List rules (summary fields), filtered and paginated in MongoDB."""
    result = service.list_rules(
        category=category.value if category else None,
        severity=severity.value if severity else None,
        enabled=enabled, name=name, page=page, limit=limit,
    )
    return RuleListResponse(
        page=result.page, limit=result.limit, total=result.total, count=len(result.rules),
        rules=[RuleSummary(**rule.model_dump(include=set(RuleSummary.model_fields))) for rule in result.rules],
    )


@router.get("/{rule_id}", response_model=RuleResponse, responses=_ERRORS)
def get_rule(rule_id: RuleIdPath, service: ServiceDep) -> RuleResponse:
    return RuleResponse(rule=RuleDetail.from_rule(service.get_rule(rule_id)))


@router.post("", response_model=RuleResponse, status_code=201, responses=_ERRORS)
def create_rule(payload: RuleCreateRequest, service: ServiceDep) -> RuleResponse:
    rule = service.create_rule(payload.model_dump(mode="json"))
    return RuleResponse(rule=RuleDetail.from_rule(rule))


@router.put("/{rule_id}", response_model=RuleResponse, responses=_ERRORS)
def update_rule(rule_id: RuleIdPath, payload: RuleUpdateRequest, service: ServiceDep) -> RuleResponse:
    """Update the fields that are sent. rule_id cannot be changed."""
    changes = payload.model_dump(mode="json", exclude_unset=True)
    rule = service.update_rule(rule_id, changes)
    return RuleResponse(rule=RuleDetail.from_rule(rule))


@router.patch("/{rule_id}/status", response_model=RuleStatusResponse, responses=_ERRORS)
def set_rule_status(rule_id: RuleIdPath, payload: RuleStatusRequest, service: ServiceDep) -> RuleStatusResponse:
    """Enable or disable a rule. The detection engine honours it on its next evaluation."""
    rule = service.set_enabled(rule_id, payload.enabled)
    return RuleStatusResponse(rule_id=rule.rule_id, enabled=rule.enabled)


@router.delete("/{rule_id}", response_model=RuleDeleteResponse, responses=_ERRORS)
def delete_rule(
    rule_id: RuleIdPath,
    service: ServiceDep,
    force: Annotated[bool, Query(description="Required to delete an initial system rule")] = False,
) -> RuleDeleteResponse:
    service.delete_rule(rule_id, force=force)
    return RuleDeleteResponse(rule_id=rule_id)
