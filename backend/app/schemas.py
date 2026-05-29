from datetime import date, datetime, time
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    DutyStatus,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
    UserRole,
    VehicleStatus,
)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: UserRole
    depot_id: Optional[int]
    full_name: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class GpsPingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: int
    ts: datetime
    lat: float
    lng: float
    speed_kmh: Optional[float]
    ignition_on: bool


class VehicleAvlsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reg_no: str
    depot_id: int
    status: VehicleStatus
    latest_ping: Optional[GpsPingOut] = None


class RouteStopIn(BaseModel):
    stop_id: int
    sequence: int
    planned_offset_min: int


class RouteStopOut(RouteStopIn):
    model_config = ConfigDict(from_attributes=True)


class RouteCreate(BaseModel):
    code: str
    name: str
    depot_id: int
    stops: list[RouteStopIn] = Field(default_factory=list)


class RouteUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    depot_id: Optional[int] = None
    stops: Optional[list[RouteStopIn]] = None


class RouteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    depot_id: int
    stops: list[RouteStopOut] = Field(default_factory=list)


class DutyCreate(BaseModel):
    date: date
    vehicle_id: int
    driver_id: int
    conductor_id: int
    route_id: int
    start_time: time
    end_time: time


class DutyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    vehicle_id: int
    driver_id: int
    conductor_id: int
    route_id: int
    start_time: time
    end_time: time
    status: DutyStatus
    ack_at: Optional[datetime] = None
    route_code: Optional[str] = None
    vehicle_reg_no: Optional[str] = None


class RosterCell(BaseModel):
    duty: Optional[DutyOut] = None


class RosterRow(BaseModel):
    driver_id: int
    driver_name: str
    cells: dict[str, RosterCell]


class RosterOut(BaseModel):
    depot_id: int
    week_start: date
    week_end: date
    rows: list[RosterRow]


class IncidentCreate(BaseModel):
    type: IncidentType
    severity: IncidentSeverity
    description: str
    vehicle_id: Optional[int] = None
    depot_id: int


class IncidentStatusUpdate(BaseModel):
    to_status: IncidentStatus
    note: Optional[str] = None


class IncidentAssign(BaseModel):
    assigned_to: int


class IncidentEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    ts: datetime
    actor_id: int
    from_status: Optional[IncidentStatus]
    to_status: IncidentStatus
    note: Optional[str]


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: IncidentType
    severity: IncidentSeverity
    status: IncidentStatus
    raised_by: int
    assigned_to: Optional[int]
    vehicle_id: Optional[int]
    depot_id: int
    description: str
    created_at: datetime
    resolved_at: Optional[datetime]


class IncidentDetailOut(IncidentOut):
    events: list[IncidentEventOut] = Field(default_factory=list)


class NoticeCreate(BaseModel):
    title: str
    body: str
    audience_json: dict[str, Any]
    publish_at: Optional[datetime] = None


class NoticeReadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notice_id: int
    user_id: int
    read_at: datetime
    username: Optional[str] = None
    full_name: Optional[str] = None


class NoticeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    audience_json: dict[str, Any]
    publish_at: datetime
    created_by: int


class NoticeDetailOut(NoticeOut):
    reads: list[NoticeReadOut] = Field(default_factory=list)
