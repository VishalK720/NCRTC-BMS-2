from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import check_depot_access, get_current_user, require_role
from app.database import get_db
from app.models import (
    Duty,
    DutyStatus,
    Route,
    RouteStop,
    User,
    UserRole,
    Vehicle,
)
from app.schemas import (
    DutyCreate,
    DutyOut,
    RouteCreate,
    RouteOut,
    RouteStopOut,
    RouteUpdate,
    RosterCell,
    RosterOut,
    RosterRow,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


def _duty_to_out(duty: Duty, db: Session) -> DutyOut:
    route = db.query(Route).filter(Route.id == duty.route_id).first()
    vehicle = db.query(Vehicle).filter(Vehicle.id == duty.vehicle_id).first()
    return DutyOut(
        id=duty.id,
        date=duty.date,
        vehicle_id=duty.vehicle_id,
        driver_id=duty.driver_id,
        conductor_id=duty.conductor_id,
        route_id=duty.route_id,
        start_time=duty.start_time,
        end_time=duty.end_time,
        status=duty.status,
        ack_at=duty.ack_at,
        route_code=route.code if route else None,
        vehicle_reg_no=vehicle.reg_no if vehicle else None,
    )


def _route_to_out(route: Route, db: Session) -> RouteOut:
    stops = (
        db.query(RouteStop)
        .filter(RouteStop.route_id == route.id)
        .order_by(RouteStop.sequence.asc())
        .all()
    )
    return RouteOut(
        id=route.id,
        code=route.code,
        name=route.name,
        depot_id=route.depot_id,
        stops=[RouteStopOut.model_validate(s) for s in stops],
    )


def _load_route_or_404(route_id: int, db: Session) -> Route:
    route = db.query(Route).filter(Route.id == route_id).first()
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
    return route


@router.get("/routes", response_model=list[RouteOut])
def list_routes(
    depot_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Route)
    if depot_id is not None:
        if not check_depot_access(current_user, depot_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")
        query = query.filter(Route.depot_id == depot_id)
    elif current_user.role not in (UserRole.admin, UserRole.control_operator):
        if current_user.depot_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")
        query = query.filter(Route.depot_id == current_user.depot_id)
    routes = query.order_by(Route.code.asc()).all()
    return [_route_to_out(r, db) for r in routes]


@router.post("/routes", response_model=RouteOut, status_code=status.HTTP_201_CREATED)
def create_route(
    body: RouteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    if not check_depot_access(current_user, body.depot_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")

    route = Route(code=body.code, name=body.name, depot_id=body.depot_id)
    db.add(route)
    db.flush()
    for stop in body.stops:
        db.add(
            RouteStop(
                route_id=route.id,
                stop_id=stop.stop_id,
                sequence=stop.sequence,
                planned_offset_min=stop.planned_offset_min,
            )
        )
    db.commit()
    db.refresh(route)
    return _route_to_out(route, db)


@router.put("/routes/{route_id}", response_model=RouteOut)
def update_route(
    route_id: int,
    body: RouteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    route = _load_route_or_404(route_id, db)
    if not check_depot_access(current_user, route.depot_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")

    if body.code is not None:
        route.code = body.code
    if body.name is not None:
        route.name = body.name
    if body.depot_id is not None:
        if not check_depot_access(current_user, body.depot_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")
        route.depot_id = body.depot_id

    if body.stops is not None:
        db.query(RouteStop).filter(RouteStop.route_id == route.id).delete()
        for stop in body.stops:
            db.add(
                RouteStop(
                    route_id=route.id,
                    stop_id=stop.stop_id,
                    sequence=stop.sequence,
                    planned_offset_min=stop.planned_offset_min,
                )
            )

    db.commit()
    db.refresh(route)
    return _route_to_out(route, db)


@router.delete("/routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_route(
    route_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    route = _load_route_or_404(route_id, db)
    if not check_depot_access(current_user, route.depot_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")
    db.query(RouteStop).filter(RouteStop.route_id == route.id).delete()
    db.delete(route)
    db.commit()


@router.get("/scheduling/roster", response_model=RosterOut)
def get_roster(
    depot_id: int = Query(...),
    week_start: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not check_depot_access(current_user, depot_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")

    week_end = week_start + timedelta(days=6)
    drivers = (
        db.query(User)
        .filter(User.depot_id == depot_id, User.role == UserRole.driver)
        .order_by(User.full_name.asc())
        .all()
    )

    duties = (
        db.query(Duty)
        .join(Vehicle, Duty.vehicle_id == Vehicle.id)
        .filter(
            Vehicle.depot_id == depot_id,
            Duty.date >= week_start,
            Duty.date <= week_end,
        )
        .all()
    )
    duty_map: dict[tuple[int, date], Duty] = {(d.driver_id, d.date): d for d in duties}

    rows: list[RosterRow] = []
    for driver in drivers:
        cells: dict[str, RosterCell] = {}
        for offset in range(7):
            day = week_start + timedelta(days=offset)
            key = day.isoformat()
            duty = duty_map.get((driver.id, day))
            cells[key] = RosterCell(
                duty=_duty_to_out(duty, db) if duty else None,
            )
        rows.append(
            RosterRow(
                driver_id=driver.id,
                driver_name=driver.full_name,
                cells=cells,
            )
        )

    return RosterOut(
        depot_id=depot_id,
        week_start=week_start,
        week_end=week_end,
        rows=rows,
    )


@router.post("/scheduling/duties", response_model=DutyOut, status_code=status.HTTP_201_CREATED)
def create_duty(
    body: DutyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.depot_manager)),
):
    vehicle = db.query(Vehicle).filter(Vehicle.id == body.vehicle_id).first()
    route = db.query(Route).filter(Route.id == body.route_id).first()
    if vehicle is None or route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle or route not found")

    depot_id = vehicle.depot_id
    if route.depot_id != depot_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Route depot mismatch")
    if not check_depot_access(current_user, depot_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")

    duty = Duty(
        date=body.date,
        vehicle_id=body.vehicle_id,
        driver_id=body.driver_id,
        conductor_id=body.conductor_id,
        route_id=body.route_id,
        start_time=body.start_time,
        end_time=body.end_time,
        status=DutyStatus.draft,
    )
    db.add(duty)
    db.commit()
    db.refresh(duty)
    return _duty_to_out(duty, db)


@router.put("/scheduling/duties/{duty_id}/publish", response_model=DutyOut)
def publish_duty(
    duty_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.depot_manager)),
):
    duty = db.query(Duty).filter(Duty.id == duty_id).first()
    if duty is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Duty not found")

    vehicle = db.query(Vehicle).filter(Vehicle.id == duty.vehicle_id).first()
    if vehicle is None or not check_depot_access(current_user, vehicle.depot_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Depot access denied")

    duty.status = DutyStatus.published
    db.commit()
    db.refresh(duty)
    return _duty_to_out(duty, db)


@router.put("/scheduling/duties/{duty_id}/acknowledge", response_model=DutyOut)
def acknowledge_duty(
    duty_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.driver)),
):
    duty = db.query(Duty).filter(Duty.id == duty_id).first()
    if duty is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Duty not found")
    if duty.driver_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your duty")

    duty.status = DutyStatus.acknowledged
    duty.ack_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(duty)
    return _duty_to_out(duty, db)


@router.get("/scheduling/my-duty", response_model=Optional[DutyOut])
def my_duty(
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
        return None
    return _duty_to_out(duty, db)
