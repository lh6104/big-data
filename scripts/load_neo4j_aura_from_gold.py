#!/usr/bin/env python3
"""Load local Gold traffic segments into Neo4j AuraDB for cloud graph evidence."""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from neo4j import GraphDatabase

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.services.local_data import PROJECT_ROOT, latest_by_segment, traffic_features
from scripts.check_neo4j_aura import load_dotenv, read_cypher


def _coordinates(row: pd.Series) -> list[tuple[float, float]]:
    geometry = row.get("geometry")
    if isinstance(geometry, str) and geometry:
        try:
            geometry = json.loads(geometry)
        except json.JSONDecodeError:
            try:
                geometry = ast.literal_eval(geometry)
            except (ValueError, SyntaxError):
                geometry = None
    coords: list[tuple[float, float]] = []
    if isinstance(geometry, dict):
        for point in geometry.get("coordinates") or []:
            if isinstance(point, dict):
                lat = point.get("latitude")
                lon = point.get("longitude")
                if lat is not None and lon is not None:
                    coords.append((float(lat), float(lon)))
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                lon, lat = point[:2]
                coords.append((float(lat), float(lon)))
    if len(coords) >= 2:
        return coords
    lat = float(row.get("lat", 0.0))
    lon = float(row.get("lon", 0.0))
    return [(lat - 0.003, lon - 0.003), (lat + 0.003, lon + 0.003)]


def _clean_text(value: Any, default: str) -> str:
    if value is None or value != value:
        return default
    text = str(value).strip()
    return text or default


def _apply_schema(session) -> None:
    for filename in ["constraints.cypher", "indexes.cypher"]:
        for statement in read_cypher(PROJECT_ROOT / "infra" / "neo4j-aura" / filename):
            session.run(statement).consume()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--apply-schema", action="store_true")
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / args.env_file)
    uri = os.getenv("NEO4J_URI", "")
    username = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    if not uri or not password:
        raise SystemExit("Neo4j AuraDB is not configured.")

    latest = latest_by_segment(traffic_features())
    if latest.empty:
        raise SystemExit("No local Gold traffic features available.")
    latest = latest.sort_values("jamFactor", ascending=False).head(args.limit).copy()

    driver = GraphDatabase.driver(uri, auth=(username, password))
    loaded_segments = 0
    loaded_relationships = 0
    with driver.session(database=database) as session:
        if args.apply_schema:
            _apply_schema(session)
        for _, row in latest.iterrows():
            segment_id = _clean_text(row.get("segment_id"), "unknown_segment")
            city = _clean_text(row.get("city"), "unknown")
            district = _clean_text(row.get("district"), "unknown")
            segment_name = _clean_text(row.get("segment_name"), segment_id)
            coords = _coordinates(row)
            start_lat, start_lon = coords[0]
            end_lat, end_lon = coords[-1]
            start_id = f"{segment_id}:start"
            end_id = f"{segment_id}:end"
            params = {
                "segment_id": segment_id,
                "segment_name": segment_name,
                "city": city,
                "district": district,
                "road_class": _clean_text(row.get("road_class_encoded"), "unknown"),
                "length_m": float(row.get("length_m", 0.0) or 0.0),
                "current_speed": float(row.get("currentSpeed", 0.0) or 0.0),
                "free_flow_speed": float(row.get("freeFlowSpeed", 0.0) or 0.0),
                "current_jam_factor": float(row.get("jamFactor", 0.0) or 0.0),
                "risk_score": min(100.0, max(0.0, float(row.get("jamFactor", 0.0) or 0.0) * 10.0)),
                "start_id": start_id,
                "end_id": end_id,
                "start_lat": start_lat,
                "start_lon": start_lon,
                "end_lat": end_lat,
                "end_lon": end_lon,
            }
            session.run(
                """
                MERGE (d:District {city: $city, name: $district})
                MERGE (a:Intersection {node_id: $start_id})
                SET a.lat = $start_lat, a.lon = $start_lon, a.city = $city
                MERGE (b:Intersection {node_id: $end_id})
                SET b.lat = $end_lat, b.lon = $end_lon, b.city = $city
                MERGE (s:RoadSegment {segment_id: $segment_id})
                SET s.name = $segment_name,
                    s.city = $city,
                    s.district = $district,
                    s.road_class = $road_class,
                    s.length_m = $length_m,
                    s.current_speed = $current_speed,
                    s.free_flow_speed = $free_flow_speed,
                    s.current_jam_factor = $current_jam_factor,
                    s.risk_score = $risk_score,
                    s.updated_at = datetime()
                MERGE (s)-[:LOCATED_IN]->(d)
                MERGE (s)-[:STARTS_AT]->(a)
                MERGE (s)-[:ENDS_AT]->(b)
                """,
                params,
            ).consume()
            loaded_segments += 1

        for city, group in latest.groupby("city"):
            ordered = group.sort_values("jamFactor", ascending=False)["segment_id"].astype(str).tolist()
            for upstream, downstream in zip(ordered, ordered[1:]):
                session.run(
                    """
                    MATCH (u:RoadSegment {segment_id: $upstream})
                    MATCH (d:RoadSegment {segment_id: $downstream})
                    MERGE (u)-[:UPSTREAM_OF {city: $city}]->(d)
                    """,
                    {"upstream": upstream, "downstream": downstream, "city": str(city)},
                ).consume()
                loaded_relationships += 1

        totals = session.run(
            """
            MATCH (n)
            WITH count(n) AS nodes
            MATCH ()-[r]->()
            RETURN nodes, count(r) AS relationships
            """
        ).single()

    driver.close()
    print(
        f"Loaded Neo4j AuraDB graph: segments={loaded_segments}, "
        f"upstream_relationships={loaded_relationships}, "
        f"nodes_total={totals['nodes']}, relationships_total={totals['relationships']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
