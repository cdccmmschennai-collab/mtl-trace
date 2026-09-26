from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status

from backend.api.errors import http_error, read_upload
from backend.models.schemas import (
    RunCreate,
    RunOut,
    RunSourceOut,
    SourceIdentificationOut,
    SourceRowsOut,
    SourceTypeOut,
)
from backend.services.milestones import ConflictError, InvalidInputError, NotFoundError
from backend.services.runs import RunService

router = APIRouter(prefix="/api", tags=["runs"])


def get_service(request: Request) -> RunService:
    return request.app.state.run_service


Service = Annotated[RunService, Depends(get_service)]
Errors = (NotFoundError, ConflictError, InvalidInputError)


def _type(value: str | None) -> str | None:
    return value.strip().upper() or None if value else None


@router.get("/source-types", response_model=list[SourceTypeOut])
def source_types(service: Service):
    return service.source_types()


@router.post("/milestones/{milestone_id}/runs", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def create_run(milestone_id: int, service: Service, body: RunCreate | None = None):
    try:
        return service.create_run(milestone_id, body.notes if body else None, body.base_run_id if body else None)
    except Errors as exc:
        raise http_error(exc)


@router.get("/milestones/{milestone_id}/runs", response_model=list[RunOut])
def list_runs(milestone_id: int, service: Service):
    try:
        return service.list_runs(milestone_id)
    except Errors as exc:
        raise http_error(exc)


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: int, service: Service):
    try:
        return service.get_run(run_id)
    except Errors as exc:
        raise http_error(exc)


@router.post("/runs/{run_id}/sources/identify", response_model=SourceIdentificationOut)
async def identify_source(run_id: int, service: Service, file: UploadFile = File(...),
                          source_type: str | None = Form(default=None)):
    """Dry run: detect source type, sheet and field mapping. Nothing is stored."""
    name, data = await read_upload(file, "source.xlsx")
    try:
        return service.identify_source(run_id, name, data, _type(source_type))
    except Errors as exc:
        raise http_error(exc)


@router.post("/runs/{run_id}/sources", response_model=RunSourceOut, status_code=status.HTTP_201_CREATED)
async def upload_source(run_id: int, service: Service, file: UploadFile = File(...),
                        source_type: str | None = Form(default=None),
                        document_date: str | None = Form(default=None),
                        revision: str | None = Form(default=None)):
    """Store the document immutably, identify it, extract it and check it against the locked scope.

    A document that cannot be identified or mapped is still recorded, with status FAILED and its issues.
    """
    name, data = await read_upload(file, "source.xlsx")
    try:
        return service.upload_source(run_id, name, data, _type(source_type), document_date, revision)
    except Errors as exc:
        raise http_error(exc)


@router.get("/runs/{run_id}/sources/{run_source_id}", response_model=RunSourceOut)
def get_source(run_id: int, run_source_id: int, service: Service):
    try:
        return service.get_run_source(run_id, run_source_id)
    except Errors as exc:
        raise http_error(exc)


@router.get("/runs/{run_id}/sources/{run_source_id}/rows", response_model=SourceRowsOut)
def source_rows(run_id: int, run_source_id: int, service: Service,
                offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)):
    try:
        return service.list_source_rows(run_id, run_source_id, offset, limit)
    except Errors as exc:
        raise http_error(exc)
