from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, asc, or_

from ..analysis.sanitizer import sanitize_message
from ..core.deps import get_current_user, verify_organization_access
from ..db.session import get_db
from ..models.db import User, Incident, OrganizationMember
from ..models.auth_schemas import (
    IncidentCreate,
    IncidentUpdate,
    IncidentListItem,
    IncidentDetail,
    IncidentStats,
)

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])

MAX_RAW_PREVIEW_BYTES = 20 * 1024  # 20 KB bound for raw log preview


@router.post("", response_model=IncidentDetail, status_code=status.HTTP_201_CREATED)
async def create_incident(
    payload: IncidentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IncidentDetail:
    """Save an analyzed incident for the user's organization."""
    # Determine organization
    org_id = payload.organization_id
    if not org_id:
        first_membership = db.scalar(
            select(OrganizationMember).where(OrganizationMember.user_id == current_user.id)
        )
        if not first_membership:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User does not belong to any organization. Please join or create one.",
            )
        org_id = first_membership.organization_id

    # Verify authorization (anti-IDOR)
    verify_organization_access(org_id, current_user, db)

    # Bound and sanitize raw content preview to prevent credential leakage
    raw_preview = payload.raw_content_preview
    if raw_preview:
        raw_preview = sanitize_message(raw_preview)
        if len(raw_preview.encode("utf-8")) > MAX_RAW_PREVIEW_BYTES:
            raw_preview = raw_preview.encode("utf-8")[:MAX_RAW_PREVIEW_BYTES].decode("utf-8", errors="ignore")

    incident = Incident(
        organization_id=org_id,
        created_by_user_id=current_user.id,
        title=payload.title,
        filename=payload.filename,
        file_format=payload.file_format,
        summary_json=payload.summary_json,
        anomalies_json=payload.anomalies_json,
        hypotheses_json=payload.hypotheses_json,
        events_json=payload.events_json,
        raw_content_preview=raw_preview,
        investigation_report_json=payload.investigation_report_json,
        engine_version=payload.engine_version,
        ai_was_used=payload.ai_was_used,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    return IncidentDetail(
        id=incident.id,
        organization_id=incident.organization_id,
        created_by_user_id=incident.created_by_user_id,
        title=incident.title,
        filename=incident.filename,
        file_format=incident.file_format,
        summary_json=incident.summary_json,
        anomalies_json=incident.anomalies_json,
        hypotheses_json=incident.hypotheses_json,
        events_json=incident.events_json,
        raw_content_preview=incident.raw_content_preview,
        investigation_report_json=incident.investigation_report_json,
        engine_version=incident.engine_version,
        ai_was_used=incident.ai_was_used or False,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
    )


@router.get("", response_model=List[IncidentListItem])
async def list_incidents(
    org_id: Optional[str] = Query(None, description="Filter incidents by organization ID"),
    search: Optional[str] = Query(None, description="Search by title or filename"),
    format: Optional[str] = Query(None, description="Filter by file format"),
    sort: Optional[str] = Query("desc", description="Sort order: asc or desc"),
    limit: Optional[int] = Query(None, ge=1, le=200, description="Max incidents to return"),
    offset: Optional[int] = Query(None, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[IncidentListItem]:
    """List incidents accessible to the current user with optional filtering, search, and pagination."""
    if org_id:
        verify_organization_access(org_id, current_user, db)
        query = select(Incident).where(Incident.organization_id == org_id)
    else:
        user_org_ids = db.scalars(
            select(OrganizationMember.organization_id).where(
                OrganizationMember.user_id == current_user.id
            )
        ).all()
        if not user_org_ids:
            return []
        query = select(Incident).where(Incident.organization_id.in_(user_org_ids))

    if search:
        search_term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Incident.title.ilike(search_term),
                Incident.filename.ilike(search_term),
            )
        )

    if format:
        query = query.where(Incident.file_format == format.strip())

    if sort == "asc":
        query = query.order_by(asc(Incident.created_at))
    else:
        query = query.order_by(desc(Incident.created_at))

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    incidents = db.scalars(query).all()

    items = []
    for inc in incidents:
        summary = inc.summary_json or {}
        items.append(
            IncidentListItem(
                id=inc.id,
                organization_id=inc.organization_id,
                created_by_user_id=inc.created_by_user_id,
                title=inc.title,
                filename=inc.filename,
                file_format=inc.file_format,
                total_lines=summary.get("total_lines", 0),
                error_count=summary.get("error_count", 0),
                anomalies_flagged=summary.get("anomalies_flagged", len(inc.anomalies_json or [])),
                created_at=inc.created_at,
            )
        )
    return items


@router.get("/stats", response_model=IncidentStats)
async def get_incident_stats(
    org_id: Optional[str] = Query(None, description="Filter stats by organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IncidentStats:
    """Retrieve aggregate incident metrics for the dashboard, scoped to authorized organization(s)."""
    if org_id:
        verify_organization_access(org_id, current_user, db)
        query = select(Incident).where(Incident.organization_id == org_id)
    else:
        user_org_ids = db.scalars(
            select(OrganizationMember.organization_id).where(
                OrganizationMember.user_id == current_user.id
            )
        ).all()
        if not user_org_ids:
            return IncidentStats(
                total_incidents=0,
                total_errors=0,
                total_anomalies=0,
                by_format={},
                recent_incidents=[],
            )
        query = select(Incident).where(Incident.organization_id.in_(user_org_ids))

    all_incidents = db.scalars(query.order_by(desc(Incident.created_at))).all()

    total_incidents = len(all_incidents)
    total_errors = 0
    total_anomalies = 0
    by_format: dict[str, int] = {}
    recent_items: List[IncidentListItem] = []

    for idx, inc in enumerate(all_incidents):
        fmt = inc.file_format or "unknown"
        by_format[fmt] = by_format.get(fmt, 0) + 1

        summary = inc.summary_json or {}
        total_errors += summary.get("error_count", 0)
        anomalies_count = summary.get("anomalies_flagged", len(inc.anomalies_json or []))
        total_anomalies += anomalies_count

        if idx < 5:
            recent_items.append(
                IncidentListItem(
                    id=inc.id,
                    organization_id=inc.organization_id,
                    created_by_user_id=inc.created_by_user_id,
                    title=inc.title,
                    filename=inc.filename,
                    file_format=inc.file_format,
                    total_lines=summary.get("total_lines", 0),
                    error_count=summary.get("error_count", 0),
                    anomalies_flagged=anomalies_count,
                    created_at=inc.created_at,
                )
            )

    return IncidentStats(
        total_incidents=total_incidents,
        total_errors=total_errors,
        total_anomalies=total_anomalies,
        by_format=by_format,
        recent_incidents=recent_items,
    )


@router.get("/{incident_id}", response_model=IncidentDetail)
async def get_incident(
    incident_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IncidentDetail:
    """Retrieve full incident details, strictly enforcing multi-tenant isolation."""
    incident = db.scalar(select(Incident).where(Incident.id == incident_id))
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found.",
        )

    # Multi-tenant authorization check (anti-IDOR)
    verify_organization_access(incident.organization_id, current_user, db)

    return IncidentDetail(
        id=incident.id,
        organization_id=incident.organization_id,
        created_by_user_id=incident.created_by_user_id,
        title=incident.title,
        filename=incident.filename,
        file_format=incident.file_format,
        summary_json=incident.summary_json,
        anomalies_json=incident.anomalies_json,
        hypotheses_json=incident.hypotheses_json,
        events_json=incident.events_json,
        raw_content_preview=incident.raw_content_preview,
        investigation_report_json=incident.investigation_report_json,
        engine_version=incident.engine_version,
        ai_was_used=incident.ai_was_used or False,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
    )


@router.delete("/{incident_id}")
async def delete_incident(
    incident_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Delete an incident. Requires organization membership; creator or owner/admin role."""
    incident = db.scalar(select(Incident).where(Incident.id == incident_id))
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found.",
        )

    membership = verify_organization_access(incident.organization_id, current_user, db)

    # Members can only delete incidents they created; admins/owners can delete any in org
    if membership.role not in ("owner", "admin") and incident.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete this incident.",
        )

    db.delete(incident)
    db.commit()
    return {"status": "ok", "message": "Incident deleted successfully.", "id": incident_id}


@router.patch("/{incident_id}", response_model=IncidentDetail)
async def update_incident(
    incident_id: str,
    payload: IncidentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IncidentDetail:
    """Update an incident. Enforces multi-tenant isolation and role restrictions."""
    incident = db.scalar(select(Incident).where(Incident.id == incident_id))
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found.",
        )

    membership = verify_organization_access(incident.organization_id, current_user, db)

    # Members can only edit incidents they created; admins/owners can edit any in org
    if membership.role not in ("owner", "admin") and incident.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update this incident.",
        )

    if payload.title is not None:
        clean_title = payload.title.strip()
        if not clean_title:
            raise HTTPException(
                status_code=422,
                detail="Incident title cannot be blank.",
            )
        incident.title = clean_title

    if payload.raw_content_preview is not None:
        raw_preview = sanitize_message(payload.raw_content_preview)
        if len(raw_preview.encode("utf-8")) > MAX_RAW_PREVIEW_BYTES:
            raw_preview = raw_preview.encode("utf-8")[:MAX_RAW_PREVIEW_BYTES].decode("utf-8", errors="ignore")
        incident.raw_content_preview = raw_preview

    db.commit()
    db.refresh(incident)

    return IncidentDetail(
        id=incident.id,
        organization_id=incident.organization_id,
        created_by_user_id=incident.created_by_user_id,
        title=incident.title,
        filename=incident.filename,
        file_format=incident.file_format,
        summary_json=incident.summary_json,
        anomalies_json=incident.anomalies_json,
        hypotheses_json=incident.hypotheses_json,
        events_json=incident.events_json,
        raw_content_preview=incident.raw_content_preview,
        investigation_report_json=incident.investigation_report_json,
        engine_version=incident.engine_version,
        ai_was_used=incident.ai_was_used or False,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
    )
