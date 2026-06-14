#!/usr/bin/env python3
"""Check Neo4j AuraDB connectivity and required graph constraints."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def read_cypher(path: Path) -> list[str]:
    if not path.exists():
        return []
    statements: list[str] = []
    current: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        current.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(current).rstrip(";"))
            current = []
    if current:
        statements.append("\n".join(current))
    return statements


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=".env", help="Optional env file to load before checking")
    parser.add_argument("--apply-schema", action="store_true", help="Apply constraints and indexes after connectivity check")
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / args.env_file)
    uri = os.getenv("NEO4J_URI", "")
    username = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    if not uri or "replace-with" in uri or not password or "replace-with" in password:
        print("Neo4j AuraDB is not configured. Set NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE.")
        return 2

    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("Missing dependency: install `neo4j` from requirements.txt.")
        return 2

    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            result = session.run("RETURN 1 AS ok").single()
            if not result or result["ok"] != 1:
                print("Neo4j query check failed.")
                return 1
            if args.apply_schema:
                for filename in ["constraints.cypher", "indexes.cypher"]:
                    for statement in read_cypher(PROJECT_ROOT / "infra" / "neo4j-aura" / filename):
                        session.run(statement).consume()
        print(f"Neo4j AuraDB connectivity OK: {uri} database={database}")
        return 0
    except Exception as exc:
        print(f"Neo4j AuraDB connectivity failed: {exc}")
        return 1
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())
