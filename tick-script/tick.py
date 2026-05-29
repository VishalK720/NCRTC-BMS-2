import math
import os
import random
import time
from datetime import datetime, timezone

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
TICK_INTERVAL_SECONDS = 8
STEP_DEGREES = 0.0005


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def fetch_vehicles_on_duty_today(conn):
    """Active vehicles with at least one duty scheduled for today."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT v.id, d.route_id
            FROM vehicle v
            INNER JOIN duty d ON d.vehicle_id = v.id AND d.date = CURRENT_DATE
            WHERE v.status = 'active'
            """
        )
        return cur.fetchall()


def fetch_route_stops(conn, route_id):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.lat, s.lng, rs.sequence
            FROM route_stop rs
            INNER JOIN stop s ON s.id = rs.stop_id
            WHERE rs.route_id = %s
            ORDER BY rs.sequence ASC
            """,
            (route_id,),
        )
        return [(row[0], row[1]) for row in cur.fetchall()]


def fetch_last_ping(conn, vehicle_id):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT lat, lng
            FROM gps_ping
            WHERE vehicle_id = %s
            ORDER BY ts DESC
            LIMIT 1
            """,
            (vehicle_id,),
        )
        row = cur.fetchone()
        return (row[0], row[1]) if row else None


def distance_sq(lat1, lng1, lat2, lng2):
    return (lat2 - lat1) ** 2 + (lng2 - lng1) ** 2


def next_stop_index(stops, lat, lng):
    """Pick the next stop in sequence after the closest stop to the current position."""
    if len(stops) == 1:
        return 0
    closest = min(range(len(stops)), key=lambda i: distance_sq(lat, lng, stops[i][0], stops[i][1]))
    return (closest + 1) % len(stops)


def move_toward(lat, lng, target_lat, target_lng, step=STEP_DEGREES):
    dlat = target_lat - lat
    dlng = target_lng - lng
    dist = math.sqrt(dlat * dlat + dlng * dlng)
    if dist <= step or dist == 0:
        return target_lat, target_lng
    ratio = step / dist
    return lat + dlat * ratio, lng + dlng * ratio


def insert_ping(conn, vehicle_id, lat, lng):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO gps_ping (vehicle_id, ts, lat, lng, speed_kmh, ignition_on)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                vehicle_id,
                datetime.now(timezone.utc),
                lat,
                lng,
                round(random.uniform(25, 55), 1),
                True,
            ),
        )
    conn.commit()


def tick(conn):
    updated = 0
    vehicles = fetch_vehicles_on_duty_today(conn)

    for vehicle_id, route_id in vehicles:
        stops = fetch_route_stops(conn, route_id)
        if not stops:
            continue

        position = fetch_last_ping(conn, vehicle_id)
        if position is None:
            lat, lng = stops[0][0], stops[0][1]
        else:
            lat, lng = position

        target_idx = next_stop_index(stops, lat, lng)
        target_lat, target_lng = stops[target_idx]
        new_lat, new_lng = move_toward(lat, lng, target_lat, target_lng)
        insert_ping(conn, vehicle_id, new_lat, new_lng)
        updated += 1

    print(f"Tick: updated {updated} vehicles", flush=True)
    return updated


def main():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")

    conn = get_connection()
    try:
        while True:
            tick(conn)
            time.sleep(TICK_INTERVAL_SECONDS)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
