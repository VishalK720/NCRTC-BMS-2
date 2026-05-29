import enum
import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class VehicleStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    maintenance = "maintenance"


class UserRole(str, enum.Enum):
    driver = "driver"
    conductor = "conductor"
    depot_manager = "depot_manager"
    control_operator = "control_operator"
    admin = "admin"


class DutyStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    acknowledged = "acknowledged"
    completed = "completed"


class IncidentType(str, enum.Enum):
    breakdown = "breakdown"
    accident = "accident"
    complaint = "complaint"
    other = "other"


class IncidentSeverity(str, enum.Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class IncidentStatus(str, enum.Enum):
    open = "open"
    acknowledged = "acknowledged"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


vehicle_status_enum = Enum(VehicleStatus, name="vehicle_status")
user_role_enum = Enum(UserRole, name="user_role")
duty_status_enum = Enum(DutyStatus, name="duty_status")
incident_type_enum = Enum(IncidentType, name="incident_type")
incident_severity_enum = Enum(IncidentSeverity, name="incident_severity")
incident_status_enum = Enum(IncidentStatus, name="incident_status")


class Depot(Base):
    __tablename__ = "depot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location_lat: Mapped[float] = mapped_column(Float, nullable=False)
    location_lng: Mapped[float] = mapped_column(Float, nullable=False)
    polygon_geojson: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="depot")
    users: Mapped[list["User"]] = relationship(back_populates="depot")
    routes: Mapped[list["Route"]] = relationship(back_populates="depot")
    incidents: Mapped[list["Incident"]] = relationship(back_populates="depot")

    __table_args__ = (
        Index(
            "ix_depot_polygon_geojson",
            "polygon_geojson",
            postgresql_using="gin",
        ),
    )


class Vehicle(Base):
    __tablename__ = "vehicle"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reg_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    depot_id: Mapped[int] = mapped_column(ForeignKey("depot.id"), nullable=False)
    status: Mapped[VehicleStatus] = mapped_column(
        vehicle_status_enum,
        nullable=False,
        default=VehicleStatus.active,
    )

    depot: Mapped["Depot"] = relationship(back_populates="vehicles")
    duties: Mapped[list["Duty"]] = relationship(back_populates="vehicle")
    gps_pings: Mapped[list["GpsPing"]] = relationship(back_populates="vehicle")
    incidents: Mapped[list["Incident"]] = relationship(back_populates="vehicle")


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(user_role_enum, nullable=False)
    depot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("depot.id"), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    depot: Mapped[Optional["Depot"]] = relationship(back_populates="users")
    driver_duties: Mapped[list["Duty"]] = relationship(
        back_populates="driver",
        foreign_keys="Duty.driver_id",
    )
    conductor_duties: Mapped[list["Duty"]] = relationship(
        back_populates="conductor",
        foreign_keys="Duty.conductor_id",
    )
    raised_incidents: Mapped[list["Incident"]] = relationship(
        back_populates="raised_by_user",
        foreign_keys="Incident.raised_by",
    )
    assigned_incidents: Mapped[list["Incident"]] = relationship(
        back_populates="assigned_to_user",
        foreign_keys="Incident.assigned_to",
    )
    incident_events: Mapped[list["IncidentEvent"]] = relationship(back_populates="actor")
    notices_created: Mapped[list["Notice"]] = relationship(back_populates="created_by_user")
    notice_reads: Mapped[list["NoticeRead"]] = relationship(back_populates="user")


class Stop(Base):
    __tablename__ = "stop"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)

    route_stops: Mapped[list["RouteStop"]] = relationship(back_populates="stop")


class Route(Base):
    __tablename__ = "route"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    depot_id: Mapped[int] = mapped_column(ForeignKey("depot.id"), nullable=False)

    depot: Mapped["Depot"] = relationship(back_populates="routes")
    route_stops: Mapped[list["RouteStop"]] = relationship(back_populates="route")
    duties: Mapped[list["Duty"]] = relationship(back_populates="route")


class RouteStop(Base):
    __tablename__ = "route_stop"

    route_id: Mapped[int] = mapped_column(ForeignKey("route.id"), primary_key=True)
    stop_id: Mapped[int] = mapped_column(ForeignKey("stop.id"), primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_offset_min: Mapped[int] = mapped_column(Integer, nullable=False)

    route: Mapped["Route"] = relationship(back_populates="route_stops")
    stop: Mapped["Stop"] = relationship(back_populates="route_stops")


class Duty(Base):
    __tablename__ = "duty"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicle.id"), nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    conductor_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    route_id: Mapped[int] = mapped_column(ForeignKey("route.id"), nullable=False)
    start_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    status: Mapped[DutyStatus] = mapped_column(
        duty_status_enum,
        nullable=False,
        default=DutyStatus.draft,
    )
    ack_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    vehicle: Mapped["Vehicle"] = relationship(back_populates="duties")
    driver: Mapped["User"] = relationship(
        back_populates="driver_duties",
        foreign_keys=[driver_id],
    )
    conductor: Mapped["User"] = relationship(
        back_populates="conductor_duties",
        foreign_keys=[conductor_id],
    )
    route: Mapped["Route"] = relationship(back_populates="duties")

    __table_args__ = (
        Index("ix_duty_date_depot_id", "date", "route_id"),
    )


class GpsPing(Base):
    __tablename__ = "gps_ping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicle.id"), nullable=False)
    ts: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    speed_kmh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ignition_on: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    vehicle: Mapped["Vehicle"] = relationship(back_populates="gps_pings")

    __table_args__ = (
        Index(
            "ix_gps_ping_vehicle_ts",
            "vehicle_id",
            ts.desc(),
        ),
    )


class Incident(Base):
    __tablename__ = "incident"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[IncidentType] = mapped_column(incident_type_enum, nullable=False)
    severity: Mapped[IncidentSeverity] = mapped_column(incident_severity_enum, nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(
        incident_status_enum,
        nullable=False,
        default=IncidentStatus.open,
    )
    raised_by: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    assigned_to: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    vehicle_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vehicle.id"), nullable=True)
    depot_id: Mapped[int] = mapped_column(ForeignKey("depot.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    raised_by_user: Mapped["User"] = relationship(
        back_populates="raised_incidents",
        foreign_keys=[raised_by],
    )
    assigned_to_user: Mapped[Optional["User"]] = relationship(
        back_populates="assigned_incidents",
        foreign_keys=[assigned_to],
    )
    vehicle: Mapped[Optional["Vehicle"]] = relationship(back_populates="incidents")
    depot: Mapped["Depot"] = relationship(back_populates="incidents")
    events: Mapped[list["IncidentEvent"]] = relationship(back_populates="incident")

    __table_args__ = (
        Index("ix_incident_status_depot_id", "status", "depot_id"),
    )


class IncidentEvent(Base):
    __tablename__ = "incident_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incident.id"), nullable=False)
    ts: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    from_status: Mapped[Optional[IncidentStatus]] = mapped_column(incident_status_enum, nullable=True)
    to_status: Mapped[IncidentStatus] = mapped_column(incident_status_enum, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    incident: Mapped["Incident"] = relationship(back_populates="events")
    actor: Mapped["User"] = relationship(back_populates="incident_events")


class Notice(Base):
    __tablename__ = "notice"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    audience_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    publish_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)

    created_by_user: Mapped["User"] = relationship(back_populates="notices_created")
    reads: Mapped[list["NoticeRead"]] = relationship(back_populates="notice")


class NoticeRead(Base):
    __tablename__ = "notice_read"

    notice_id: Mapped[int] = mapped_column(ForeignKey("notice.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), primary_key=True)
    read_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    notice: Mapped["Notice"] = relationship(back_populates="reads")
    user: Mapped["User"] = relationship(back_populates="notice_reads")
