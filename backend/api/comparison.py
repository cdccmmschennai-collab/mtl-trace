from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from backend.api.errors import http_error
from backend.models.schemas import ComparisonOut
from backend.services.comparison import ComparisonService
from backend.services.milestones import ConflictError, InvalidInputError, NotFoundError

router = APIRouter(prefix="/api/runs", tags=["comparison"])


def get_service(request: Request) -> ComparisonService:
    return request.app.state.comparison_service


Service = Annotated[ComparisonService, Depends(get_service)]
Errors = (NotFoundError, ConflictError, InvalidInputError)


@router.post("/{run_id}/compare", response_model=ComparisonOut, status_code=status.HTTP_201_CREATED)
def compare(run_id: int, service: Service):
    """Compare the run's consolidated dataset once, under the run's rules version, and generate the comparison
    workbook. Download it through /api/runs/{run_id}/outputs/{output_id}/download."""
    try:
        return service.compare(run_id)
    except Errors as exc:
        raise http_error(exc)


@router.get("/{run_id}/comparison", response_model=ComparisonOut)
def get_comparison(run_id: int, service: Service):
    try:
        return service.get_comparison(run_id)
    except Errors as exc:
        raise http_error(exc)
