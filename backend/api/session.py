from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile, status

from backend.api.errors import http_error, read_upload
from backend.models.schemas import ScopeValidationReport, SessionOut
from backend.services.milestones import ConflictError, InvalidInputError, NotFoundError, ScopeRejectedError
from backend.services.session import SessionService

router = APIRouter(prefix="/api/session", tags=["session"])


def get_service(request: Request) -> SessionService:
    return request.app.state.session_service


Service = Annotated[SessionService, Depends(get_service)]
Errors = (NotFoundError, ConflictError, InvalidInputError, ScopeRejectedError)


@router.get("", response_model=SessionOut | None)
def current(service: Service):
    """The current session (locked scope + its run), or null before a scope has been loaded."""
    return service.current()


@router.post("/scope/validate", response_model=ScopeValidationReport)
async def validate_scope(service: Service, file: UploadFile = File(...)):
    """Dry run: validate a scope workbook. Nothing is stored and the current session is untouched."""
    name, data = await read_upload(file, "scope.xlsx")
    return service.validate_scope(name, data)


@router.post("/scope", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def start(service: Service, file: UploadFile = File(...)):
    """Start a new session from a scope workbook (validated, imported and locked). Replaces the previous
    session entirely. Rejected with 422 and the validation report when the workbook has errors."""
    name, data = await read_upload(file, "scope.xlsx")
    try:
        return service.start(name, data)
    except Errors as exc:
        raise http_error(exc)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def reset(service: Service):
    """Discard the session: scope, documents and results."""
    service.reset()
