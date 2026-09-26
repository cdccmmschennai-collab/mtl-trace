from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile, status

from backend.api.errors import http_error as _http_error
from backend.api.errors import read_upload
from backend.models.schemas import (
    MilestoneCreate,
    MilestoneDetail,
    MilestoneSummary,
    ScopeImportResult,
    ScopeOut,
    ScopeValidationReport,
)
from backend.services.milestones import (
    ConflictError,
    InvalidInputError,
    MilestoneService,
    NotFoundError,
    ScopeRejectedError,
)

router = APIRouter(prefix="/api/milestones", tags=["milestones"])


def get_service(request: Request) -> MilestoneService:
    return request.app.state.milestone_service


Service = Annotated[MilestoneService, Depends(get_service)]


@router.post("", response_model=MilestoneDetail, status_code=status.HTTP_201_CREATED)
def create_milestone(body: MilestoneCreate, service: Service):
    try:
        return service.create_milestone(body.milestone_code, body.project_name, body.package_name)
    except (ConflictError, InvalidInputError) as exc:
        raise _http_error(exc)


@router.get("", response_model=list[MilestoneSummary])
def list_milestones(service: Service):
    return service.list_milestones()


@router.get("/{milestone_id}", response_model=MilestoneDetail)
def get_milestone(milestone_id: int, service: Service):
    try:
        return service.get_milestone(milestone_id)
    except NotFoundError as exc:
        raise _http_error(exc)


@router.post("/{milestone_id}/scope/validate", response_model=ScopeValidationReport)
async def validate_scope(milestone_id: int, service: Service, file: UploadFile = File(...)):
    """Dry run: validate a scope workbook without importing anything."""
    name, data = await read_upload(file, "scope.xlsx")
    try:
        return service.validate_scope(milestone_id, name, data)
    except (NotFoundError, ConflictError) as exc:
        raise _http_error(exc)


@router.post("/{milestone_id}/scope", response_model=ScopeImportResult, status_code=status.HTTP_201_CREATED)
async def import_scope(milestone_id: int, service: Service, file: UploadFile = File(...)):
    """Validate and import (replacing any unlocked draft scope). Rejected with 422 on any error."""
    name, data = await read_upload(file, "scope.xlsx")
    try:
        report = service.import_scope(milestone_id, name, data)
        return {"report": ScopeValidationReport.model_validate(report),
                "milestone": MilestoneDetail.model_validate(service.get_milestone(milestone_id))}
    except (NotFoundError, ConflictError, ScopeRejectedError) as exc:
        raise _http_error(exc)


@router.get("/{milestone_id}/scope", response_model=ScopeOut)
def get_scope(milestone_id: int, service: Service):
    try:
        return service.get_scope(milestone_id)
    except NotFoundError as exc:
        raise _http_error(exc)


@router.post("/{milestone_id}/scope/lock", response_model=MilestoneDetail)
def lock_scope(milestone_id: int, service: Service):
    try:
        return service.lock_scope(milestone_id)
    except (NotFoundError, ConflictError) as exc:
        raise _http_error(exc)
