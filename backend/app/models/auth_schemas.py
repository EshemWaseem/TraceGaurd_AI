from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr


class UserSignup(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=255)
    org_name: Optional[str] = Field(default=None, max_length=255)


class UserLogin(BaseModel):
    email: str
    password: str


class OrgOut(BaseModel):
    id: str
    name: str
    slug: str
    role: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime


class CurrentUserResponse(BaseModel):
    user: UserOut
    organizations: List[OrgOut]
    active_organization_id: Optional[str]


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    organizations: List[OrgOut]
    active_organization_id: str


# ==============================================================================
# Incident Schemas for Database Operations
# ==============================================================================

class IncidentCreate(BaseModel):
    organization_id: Optional[str] = None
    title: str
    filename: str
    file_format: str
    summary_json: dict
    anomalies_json: list = []
    hypotheses_json: list = []
    events_json: list = []
    raw_content_preview: Optional[str] = None
    # Phase 2 fields (optional — backwards-compatible)
    investigation_report_json: Optional[dict] = None
    engine_version: Optional[str] = None
    ai_was_used: bool = False


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    raw_content_preview: Optional[str] = None


class IncidentListItem(BaseModel):
    id: str
    organization_id: str
    created_by_user_id: Optional[str]
    title: str
    filename: str
    file_format: str
    total_lines: int
    error_count: int
    anomalies_flagged: int
    created_at: datetime


class IncidentDetail(BaseModel):
    id: str
    organization_id: str
    created_by_user_id: Optional[str]
    title: str
    filename: str
    file_format: str
    summary_json: dict
    anomalies_json: list
    hypotheses_json: list
    events_json: list
    raw_content_preview: Optional[str]
    # Phase 2 fields
    investigation_report_json: Optional[dict] = None
    engine_version: Optional[str] = None
    ai_was_used: bool = False
    created_at: datetime
    updated_at: datetime


class IncidentStats(BaseModel):
    total_incidents: int
    total_errors: int
    total_anomalies: int
    by_format: dict[str, int] = {}
    recent_incidents: List[IncidentListItem] = []
