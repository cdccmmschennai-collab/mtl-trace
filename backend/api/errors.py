from fastapi import HTTPException, UploadFile, status

from backend.models.schemas import ScopeValidationReport
from backend.services.milestones import ConflictError, InvalidInputError, NotFoundError, ScopeRejectedError

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, ScopeRejectedError):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {
            "message": str(exc),
            "report": ScopeValidationReport.model_validate(exc.report).model_dump(mode="json"),
        })
    if isinstance(exc, InvalidInputError):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))
    raise exc


async def read_upload(file: UploadFile, default_name: str) -> tuple[str, bytes]:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File exceeds 50 MB.")
    return file.filename or default_name, data
