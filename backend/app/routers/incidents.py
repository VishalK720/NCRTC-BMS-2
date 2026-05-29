from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import check_depot_access, get_current_user, require_role
from app.database import get_db
from app.models import (
    Duty,
    GpsPing,
    Incident,
    IncidentEvent,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
    User,
    UserRole,
    Vehicle,
)
from app.schemas import (
    IncidentAssign,
    IncidentCreate,
    IncidentDetailOut,
    IncidentEventOut,
    IncidentOut,
    IncidentStatusUpdate,
)

router = APIRouter(dependencies=[Depends(get_current_user)])

VALID_TRANSITIONS: dict[IncidentStatus, IncidentStatus] = {
    IncidentStatus.open: IncidentStatus.acknowledged,
    IncidentStatus.acknowledged: IncidentStatus.in_progress,
    IncidentStatus.in_progress: IncidentStatus.resolved,
    IncidentStatus.resolved: IncidentStatus.closed,
}


def _incident_to_out(incident: Incident) -> IncidentOut:
    return IncidentOut.model_validate(incident)


@router.post("", response_model=IncidentOut, status_code=status.HTTP_201_CREATED)
def raise_incident(
    body: IncidentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not check_depot_access(current_user, body.depot_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")

    now = datetime.now(timezone.utc)
    incident = Incident(
        type=body.type,
        severity=body.severity,
        status=IncidentStatus.open,
        raised_by=current_user.id,
        assigned_to=None,
        vehicle_id=body.vehicle_id,
        depot_id=body.depot_id,
        description=body.description,
        created_at=now,
        resolved_at=None,
    )
    db.add(incident)
    db.flush()
    db.add(
        IncidentEvent(
            incident_id=incident.id,
            ts=now,
            actor_id=current_user.id,
            from_status=None,
            to_status=IncidentStatus.open,
            note="Incident raised",
        )
    )
    db.commit()
    db.refresh(incident)
    return _incident_to_out(incident)


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    status: Optional[IncidentStatus] = Query(None),
    severity: Optional[IncidentSeverity] = Query(None),
    depot_id: Optional[int] = Query(None),
    mine: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Incident)

    if mine:
        query = query.filter(
            (Incident.raised_by == current_user.id)
            | (Incident.assigned_to == current_user.id)
        )
    else:
        if depot_id is not None:
            if not check_depot_access(current_user, depot_id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")
            query = query.filter(Incident.depot_id == depot_id)
        elif current_user.role not in (UserRole.admin, UserRole.control_operator):
            if current_user.depot_id is None:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")
            query = query.filter(Incident.depot_id == current_user.depot_id)

    if status is not None:
        query = query.filter(Incident.status == status)
    if severity is not None:
        query = query.filter(Incident.severity == severity)

    incidents = query.order_by(Incident.created_at.desc()).all()
    return [_incident_to_out(i) for i in incidents]


@router.post("/panic", response_model=IncidentOut, status_code=status.HTTP_201_CREATED)
def panic_incident(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.driver)),
):
    today = date.today()
    duty = (
        db.query(Duty)
        .filter(Duty.driver_id == current_user.id, Duty.date == today)
        .order_by(Duty.start_time.asc())
        .first()
    )
    if duty is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No duty assigned for today")

    vehicle = db.query(Vehicle).filter(Vehicle.id == duty.vehicle_id).first()
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vehicle not found")

    last_ping = (
        db.query(GpsPing)
        .filter(GpsPing.vehicle_id == vehicle.id)
        .order_by(GpsPing.ts.desc())
        .first()
    )
    loc_note = "Location unknown"
    if last_ping:
        loc_note = f"Last known location: lat={last_ping.lat}, lng={last_ping.lng}"

    now = datetime.now(timezone.utc)
    incident = Incident(
        type=IncidentType.breakdown,
        severity=IncidentSeverity.P1,
        status=IncidentStatus.open,
        raised_by=current_user.id,
        assigned_to=None,
        vehicle_id=vehicle.id,
        depot_id=vehicle.depot_id,
        description=f"PANIC alert from driver {current_user.full_name}. {loc_note}",
        created_at=now,
        resolved_at=None,
    )
    db.add(incident)
    db.flush()
    db.add(
        IncidentEvent(
            incident_id=incident.id,
            ts=now,
            actor_id=current_user.id,
            from_status=None,
            to_status=IncidentStatus.open,
            note="Panic button triggered",
        )
    )
    db.commit()
    db.refresh(incident)
    return _incident_to_out(incident)


@router.get("/{incident_id}", response_model=IncidentDetailOut)
def get_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    if not check_depot_access(current_user, incident.depot_id) and incident.raised_by != current_user.id:
        if incident.assigned_to != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")

    events = (
        db.query(IncidentEvent)
        .filter(IncidentEvent.incident_id == incident_id)
        .order_by(IncidentEvent.ts.asc())
        .all()
    )
    return IncidentDetailOut(
        **_incident_to_out(incident).model_dump(),
        events=[IncidentEventOut.model_validate(e) for e in events],
    )


@router.put("/{incident_id}/status", response_model=IncidentOut)
def update_incident_status(
    incident_id: int,
    body: IncidentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    if not check_depot_access(current_user, incident.depot_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")

    expected = VALID_TRANSITIONS.get(incident.status)
    if expected is None or body.to_status != expected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transition from {incident.status.value} to {body.to_status.value}",
        )

    now = datetime.now(timezone.utc)
    from_status = incident.status
    incident.status = body.to_status
    if body.to_status == IncidentStatus.resolved:
        incident.resolved_at = now

    db.add(
        IncidentEvent(
            incident_id=incident.id,
            ts=now,
            actor_id=current_user.id,
            from_status=from_status,
            to_status=body.to_status,
            note=body.note,
        )
    )
    db.commit()
    db.refresh(incident)
    return _incident_to_out(incident)


@router.put("/{incident_id}/assign", response_model=IncidentOut)
def assign_incident(
    incident_id: int,
    body: IncidentAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.depot_manager, UserRole.control_operator, UserRole.admin)
    ),
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    if not check_depot_access(current_user, incident.depot_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")

    assignee = db.query(User).filter(User.id == body.assigned_to).first()
    if assignee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found")

    incident.assigned_to = body.assigned_to
    db.commit()
    db.refresh(incident)
    return _incident_to_out(incident)
