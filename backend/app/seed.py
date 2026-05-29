import random
from datetime import date, datetime, time, timedelta, timezone

from faker import Faker
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import SessionLocal
from app.models import (
    Depot,
    Duty,
    DutyStatus,
    GpsPing,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
    Notice,
    NoticeRead,
    Route,
    RouteStop,
    Stop,
    User,
    UserRole,
    Vehicle,
    VehicleStatus,
)

fake = Faker("en_IN")

DEPOTS = [
    {"code": "NOIDA37", "name": "Noida Sec-37", "lat": 28.5355, "lng": 77.3910},
    {"code": "AVHAR", "name": "Anand Vihar", "lat": 28.6469, "lng": 77.3152},
    {"code": "GZB", "name": "Ghaziabad", "lat": 28.6692, "lng": 77.4538},
    {"code": "GGN", "name": "Gurugram", "lat": 28.4595, "lng": 77.0266},
]

STOPS = [
    ("Rajiv Chowk", 28.6328, 77.2197),
    ("Kashmere Gate", 28.6675, 77.2280),
    ("Central Secretariat", 28.6150, 77.2120),
    ("Huda City Centre", 28.4590, 77.0726),
    ("Sector 18 Noida", 28.5708, 77.3261),
    ("Botanic Garden", 28.5642, 77.3340),
    ("Yamuna Bank", 28.6233, 77.2685),
    ("Anand Vihar ISBT", 28.6469, 77.3160),
    ("Dwarka Sector 21", 28.5523, 77.0559),
    ("Janakpuri West", 28.6297, 77.0776),
    ("Rithala", 28.7215, 77.1072),
    ("Mundka", 28.6824, 77.0289),
    ("ITO", 28.6289, 77.2405),
    ("Nehru Place", 28.5494, 77.2512),
    ("Saket", 28.5245, 77.2066),
    ("Vaishali", 28.6501, 77.3378),
    ("Kaushambi", 28.6562, 77.3264),
    ("Dilshad Garden", 28.6759, 77.3215),
    ("Rohini West", 28.7150, 77.1158),
    ("Netaji Subhash Place", 28.6956, 77.1524),
    ("Mandi House", 28.6258, 77.2345),
    ("AIIMS", 28.5683, 77.2090),
    ("Chandni Chowk", 28.6567, 77.2307),
    ("New Delhi", 28.6431, 77.2197),
    ("Shivaji Stadium", 28.6289, 77.2075),
    ("Dhaula Kuan", 28.5918, 77.1615),
    ("IGI Airport", 28.5562, 77.1000),
    ("Sikandarpur", 28.4815, 77.0930),
    ("MG Road", 28.4795, 77.0800),
    ("IFFCO Chowk", 28.4724, 77.0720),
]


def square_polygon(lat: float, lng: float, delta: float = 0.01) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [lng - delta, lat - delta],
                [lng + delta, lat - delta],
                [lng + delta, lat + delta],
                [lng - delta, lat + delta],
                [lng - delta, lat - delta],
            ]
        ],
    }


def seed(db: Session) -> None:
    if db.query(User).count() > 0:
        return

    today = date.today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    now = datetime.now(timezone.utc)

    depots: list[Depot] = []
    for spec in DEPOTS:
        depot = Depot(
            code=spec["code"],
            name=spec["name"],
            location_lat=spec["lat"],
            location_lng=spec["lng"],
            polygon_geojson=square_polygon(spec["lat"], spec["lng"]),
        )
        db.add(depot)
        depots.append(depot)
    db.flush()

    vehicles: list[Vehicle] = []
    reg_counters = {d.id: 1 for d in depots}
    for _ in range(50):
        depot = random.choice(depots)
        digits = reg_counters[depot.id]
        reg_counters[depot.id] += 1
        vehicle = Vehicle(
            reg_no=f"DL-{depot.code}-{digits:04d}",
            depot_id=depot.id,
            status=VehicleStatus.active,
        )
        db.add(vehicle)
        vehicles.append(vehicle)
    db.flush()

    stops: list[Stop] = []
    for name, lat, lng in STOPS:
        stop = Stop(name=name, lat=lat, lng=lng)
        db.add(stop)
        stops.append(stop)
    db.flush()

    routes: list[Route] = []
    route_stops_by_route: dict[int, list[RouteStop]] = {}
    stop_idx = 0
    for i in range(12):
        depot = depots[i % len(depots)]
        route = Route(
            code=f"R{i + 1:02d}",
            name=f"Route {i + 1} — {depot.name}",
            depot_id=depot.id,
        )
        db.add(route)
        routes.append(route)
    db.flush()

    for i, route in enumerate(routes):
        route_stop_rows: list[RouteStop] = []
        for seq in range(8):
            stop = stops[(stop_idx + seq) % len(stops)]
            route_stop = RouteStop(
                route_id=route.id,
                stop_id=stop.id,
                sequence=seq + 1,
                planned_offset_min=seq * 5,
            )
            db.add(route_stop)
            route_stop_rows.append(route_stop)
        route_stops_by_route[route.id] = route_stop_rows
        stop_idx += 8
    db.flush()

    users: list[User] = []
    password = hash_password("password")

    for username in ("admin1", "admin2"):
        users.append(
            User(
                username=username,
                password_hash=password,
                full_name=fake.name(),
                role=UserRole.admin,
                depot_id=None,
                phone=fake.phone_number()[:15],
            )
        )

    for i, depot in enumerate(depots, start=1):
        users.append(
            User(
                username=f"manager{i}",
                password_hash=password,
                full_name=fake.name(),
                role=UserRole.depot_manager,
                depot_id=depot.id,
                phone=fake.phone_number()[:15],
            )
        )

    for i in range(1, 5):
        users.append(
            User(
                username=f"operator{i}",
                password_hash=password,
                full_name=fake.name(),
                role=UserRole.control_operator,
                depot_id=None,
                phone=fake.phone_number()[:15],
            )
        )

    for n in range(1, 71):
        depot = depots[(n - 1) % len(depots)]
        users.append(
            User(
                username=f"driver{n}",
                password_hash=password,
                full_name=fake.name(),
                role=UserRole.driver,
                depot_id=depot.id,
                phone=fake.phone_number()[:15],
            )
        )

    for user in users:
        db.add(user)
    db.flush()

    drivers_by_depot: dict[int, list[User]] = {d.id: [] for d in depots}
    for user in users:
        if user.role == UserRole.driver and user.depot_id is not None:
            drivers_by_depot[user.depot_id].append(user)

    routes_by_depot: dict[int, list[Route]] = {d.id: [] for d in depots}
    for route in routes:
        routes_by_depot[route.depot_id].append(route)

    vehicles_by_depot: dict[int, list[Vehicle]] = {d.id: [] for d in depots}
    for vehicle in vehicles:
        vehicles_by_depot[vehicle.depot_id].append(vehicle)

    duty_plan = [
        (yesterday, 2, DutyStatus.completed),
        (today, 3, DutyStatus.published),
        (tomorrow, 2, DutyStatus.draft),
    ]

    for depot in depots:
        depot_drivers = drivers_by_depot[depot.id]
        depot_routes = routes_by_depot[depot.id]
        depot_vehicles = vehicles_by_depot[depot.id]
        duty_idx = 0
        for duty_date, count, duty_status in duty_plan:
            for _ in range(count):
                driver = depot_drivers[duty_idx % len(depot_drivers)]
                conductor = depot_drivers[(duty_idx + 1) % len(depot_drivers)]
                route = depot_routes[duty_idx % len(depot_routes)]
                vehicle = depot_vehicles[duty_idx % len(depot_vehicles)]
                duty = Duty(
                    date=duty_date,
                    vehicle_id=vehicle.id,
                    driver_id=driver.id,
                    conductor_id=conductor.id,
                    route_id=route.id,
                    start_time=time(6 + (duty_idx % 4), 0),
                    end_time=time(14 + (duty_idx % 4), 0),
                    status=duty_status,
                    ack_at=None,
                )
                db.add(duty)
                duty_idx += 1
    db.flush()

    gps_vehicles = vehicles[:10]
    base_ts = datetime.combine(yesterday, time(8, 0), tzinfo=timezone.utc)
    for vehicle in gps_vehicles:
        depot_routes = routes_by_depot[vehicle.depot_id]
        if not depot_routes:
            continue
        route = depot_routes[0]
        route_stops = sorted(route_stops_by_route[route.id], key=lambda rs: rs.sequence)
        if not route_stops:
            continue
        stop_coords = []
        for rs in route_stops:
            stop = next(s for s in stops if s.id == rs.stop_id)
            stop_coords.append((stop.lat, stop.lng))

        for ping_i in range(40):
            coord = stop_coords[ping_i % len(stop_coords)]
            db.add(
                GpsPing(
                    vehicle_id=vehicle.id,
                    ts=base_ts + timedelta(seconds=60 * ping_i),
                    lat=coord[0],
                    lng=coord[1],
                    speed_kmh=round(random.uniform(15, 45), 1),
                    ignition_on=True,
                )
            )

    admin = next(u for u in users if u.username == "admin1")
    operator = next(u for u in users if u.username == "operator1")
    all_drivers = [u for u in users if u.role == UserRole.driver]

    incidents_data = [
        (IncidentType.breakdown, IncidentSeverity.P1, IncidentStatus.open, depots[0]),
        (IncidentType.accident, IncidentSeverity.P1, IncidentStatus.open, depots[1]),
        (IncidentType.complaint, IncidentSeverity.P2, IncidentStatus.in_progress, depots[2]),
        (IncidentType.other, IncidentSeverity.P3, IncidentStatus.resolved, depots[3]),
        (IncidentType.breakdown, IncidentSeverity.P3, IncidentStatus.resolved, depots[0]),
    ]
    for inc_type, severity, inc_status, depot in incidents_data:
        depot_vehicle = vehicles_by_depot[depot.id][0]
        resolved_at = now - timedelta(hours=2) if inc_status == IncidentStatus.resolved else None
        db.add(
            Incident(
                type=inc_type,
                severity=severity,
                status=inc_status,
                raised_by=admin.id,
                assigned_to=operator.id if inc_status != IncidentStatus.open else None,
                vehicle_id=depot_vehicle.id,
                depot_id=depot.id,
                description=fake.sentence(nb_words=12),
                created_at=now - timedelta(days=1),
                resolved_at=resolved_at,
            )
        )
    db.flush()

    notice_all = Notice(
        title="All-driver safety briefing",
        body="Mandatory safety briefing for all drivers this week.",
        audience_json={"roles": ["driver"]},
        publish_at=now - timedelta(days=1),
        created_by=admin.id,
    )
    notice_depot = Notice(
        title="Depot operations update",
        body="Updated reporting times for all depot staff.",
        audience_json={"depot_ids": [d.id for d in depots]},
        publish_at=now - timedelta(hours=12),
        created_by=admin.id,
    )
    notice_reads_notice = Notice(
        title="New timetable effective Monday",
        body="Review the updated timetable before your next duty.",
        audience_json={"roles": ["driver"]},
        publish_at=now - timedelta(hours=6),
        created_by=admin.id,
    )
    db.add(notice_all)
    db.add(notice_depot)
    db.add(notice_reads_notice)
    db.flush()

    for driver in random.sample(all_drivers, 5):
        db.add(
            NoticeRead(
                notice_id=notice_reads_notice.id,
                user_id=driver.id,
                read_at=now - timedelta(hours=2),
            )
        )


def main() -> None:
    db = SessionLocal()
    try:
        with db.begin():
            seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
