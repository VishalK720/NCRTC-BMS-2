from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.auth import check_depot_access, get_current_user
from app.database import get_db
from app.models import GpsPing, User, UserRole, Vehicle, VehicleStatus
from app.schemas import GpsPingOut, VehicleAvlsOut

router = APIRouter(dependencies=[Depends(get_current_user)])


def _enforce_depot_filter(user: User, depot_id: Optional[int]) -> Optional[int]:
    if depot_id is not None:
        if not check_depot_access(user, depot_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")
        return depot_id
    if user.role in (UserRole.admin, UserRole.control_operator):
        return None
    if user.depot_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")
    return user.depot_id


@router.get("/vehicles", response_model=list[VehicleAvlsOut])
def list_vehicles(
    depot_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    effective_depot = _enforce_depot_filter(current_user, depot_id)

    latest_ts_subq = (
        db.query(
            GpsPing.vehicle_id.label("vehicle_id"),
            func.max(GpsPing.ts).label("max_ts"),
        )
        .group_by(GpsPing.vehicle_id)
        .subquery()
    )

    query = (
        db.query(Vehicle, GpsPing)
        .filter(Vehicle.status == VehicleStatus.active)
        .outerjoin(
            latest_ts_subq,
            Vehicle.id == latest_ts_subq.c.vehicle_id,
        )
        .outerjoin(
            GpsPing,
            and_(
                GpsPing.vehicle_id == latest_ts_subq.c.vehicle_id,
                GpsPing.ts == latest_ts_subq.c.max_ts,
            ),
        )
    )

    if effective_depot is not None:
        query = query.filter(Vehicle.depot_id == effective_depot)

    results = []
    for vehicle, ping in query.all():
        results.append(
            VehicleAvlsOut(
                id=vehicle.id,
                reg_no=vehicle.reg_no,
                depot_id=vehicle.depot_id,
                status=vehicle.status,
                latest_ping=GpsPingOut.model_validate(ping) if ping else None,
            )
        )
    return results


@router.get("/vehicles/{vehicle_id}/pings", response_model=list[GpsPingOut])
def vehicle_recent_pings(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    if not check_depot_access(current_user, vehicle.depot_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")

    since = datetime.now(timezone.utc) - timedelta(minutes=30)
    pings = (
        db.query(GpsPing)
        .filter(GpsPing.vehicle_id == vehicle_id, GpsPing.ts >= since)
        .order_by(GpsPing.ts.asc())
        .all()
    )
    return [GpsPingOut.model_validate(p) for p in pings]


@router.get("/vehicles/{vehicle_id}/history", response_model=list[GpsPingOut])
def vehicle_history(
    vehicle_id: int,
    history_date: date = Query(..., alias="date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    if not check_depot_access(current_user, vehicle.depot_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")

    day_start = datetime.combine(history_date, datetime.min.time(), tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    pings = (
        db.query(GpsPing)
        .filter(
            GpsPing.vehicle_id == vehicle_id,
            GpsPing.ts >= day_start,
            GpsPing.ts < day_end,
        )
        .order_by(GpsPing.ts.asc())
        .all()
    )
    return [GpsPingOut.model_validate(p) for p in pings]
