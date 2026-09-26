from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import FileResponse

from backend.api.errors import http_error
from backend.models.schemas import CanonicalPageOut, ConsolidationOut, OutputOut
from backend.services.consolidation import ConsolidationService
from backend.services.milestones import ConflictError, InvalidInputError, NotFoundError

router = APIRouter(prefix="/api/runs", tags=["consolidation"])


def get_service(request: Request) -> ConsolidationService:
    return request.app.state.consolidation_service


Service = Annotated[ConsolidationService, Depends(get_service)]
Errors = (NotFoundError, ConflictError, InvalidInputError)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/{run_id}/consolidate", response_model=ConsolidationOut, status_code=status.HTTP_201_CREATED)
def consolidate(run_id: int, service: Service):
    """Build the run's canonical dataset from its stored source records, once. Generates the consolidated
    workbook structure and canonical snapshot. No comparison results are produced."""
    try:
        return service.consolidate(run_id)
    except Errors as exc:
        raise http_error(exc)


@router.get("/{run_id}/consolidation", response_model=ConsolidationOut)
def get_consolidation(run_id: int, service: Service):
    try:
        return service.get_consolidation(run_id)
    except Errors as exc:
        raise http_error(exc)


@router.get("/{run_id}/canonical", response_model=CanonicalPageOut)
def canonical(run_id: int, service: Service, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
              filter: str = Query("all"), search: str | None = Query(None, max_length=200)):
    try:
        return service.canonical_rows(run_id, offset, limit, filter, search)
    except Errors as exc:
        raise http_error(exc)


@router.get("/{run_id}/outputs", response_model=list[OutputOut])
def outputs(run_id: int, service: Service):
    try:
        return service.list_outputs(run_id)
    except Errors as exc:
        raise http_error(exc)


@router.get("/{run_id}/outputs/{output_id}/download")
def download(run_id: int, output_id: int, service: Service):
    try:
        path, name = service.output_file(run_id, output_id)
    except Errors as exc:
        raise http_error(exc)
    media = XLSX if name.lower().endswith(".xlsx") else "text/csv"
    return FileResponse(path, media_type=media, filename=name)
