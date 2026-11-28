from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.exception_handlers import APIException
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.admin_organization_application import (
    AdminApplicationDetailResponse,
    AdminApplicationQueueQuery,
    AdminApplicationQueueResponse,
)
from app.services.admin_organization_applications import (
    AdminApplicationNotFoundError,
    get_admin_application_detail,
    get_admin_document_content,
    list_admin_applications,
)

router = APIRouter(
    prefix="/admin/organization-applications",
    tags=["Admin Organization Applications"],
)

ApplicationId = Annotated[int, Path(gt=0, le=2**63 - 1)]
DocumentId = Annotated[int, Path(gt=0, le=2**63 - 1)]


@router.get(
    "",
    response_model=AdminApplicationQueueResponse,
)
def get_application_queue(
    filters: Annotated[AdminApplicationQueueQuery, Query()],
    current_admin: User = Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminApplicationQueueResponse:
    return list_admin_applications(db, filters)


@router.get(
    "/{application_id}",
    response_model=AdminApplicationDetailResponse,
)
def get_application_review_details(
    application_id: ApplicationId,
    current_admin: User = Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict:
    try:
        application = get_admin_application_detail(db, application_id)
    except AdminApplicationNotFoundError:
        raise APIException(
            status_code=404,
            code="NOT_FOUND",
            message="Organization application not found.",
        )

    return {"data": application}


@router.get(
    "/{application_id}/documents/{document_id}",
)
def download_application_document(
    application_id: ApplicationId,
    document_id: DocumentId,
    current_admin: User = Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> Response:
    try:
        document, content = get_admin_document_content(
            db,
            application_id,
            document_id,
        )
    except AdminApplicationNotFoundError:
        raise APIException(
            status_code=404,
            code="NOT_FOUND",
            message="Organization application document not found.",
        )

    filename = document.original_filename.replace("\r", "").replace("\n", "")
    ascii_filename = filename.encode("ascii", "ignore").decode("ascii")
    ascii_filename = ascii_filename.replace('"', "").replace("\\", "")
    if not ascii_filename:
        ascii_filename = "document"

    content_disposition = (
        f'attachment; filename="{ascii_filename}"; '
        f"filename*=UTF-8''{quote(filename, safe='')}"
    )

    return Response(
        content=content,
        media_type=document.content_type,
        headers={
            "Content-Disposition": content_disposition,
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )
