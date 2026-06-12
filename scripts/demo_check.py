#!/usr/bin/env python3
"""Run local demo smoke checks and write reproducibility evidence."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"


def fetch_json(base_url: str, endpoint: str, timeout: float = 10.0) -> tuple[int | None, Any, str | None, float | None]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + endpoint, timeout=timeout) as response:
            body = response.read()
            return response.status, json.loads(body.decode("utf-8")), None, (time.perf_counter() - started) * 1000.0
    except urllib.error.HTTPError as exc:
        return exc.code, None, str(exc), (time.perf_counter() - started) * 1000.0
    except Exception as exc:
        return None, None, str(exc), None


def item(name: str, status: str, detail: str) -> dict[str, str]:
    return {"check": name, "status": status, "detail": detail}


def run_endpoint_checks(base_url: str) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    specs = [
        ("API health", "/health", lambda payload: "status" in payload, "200 OK"),
        ("Dashboard summary", "/dashboard/summary?city=hanoi", lambda payload: payload.get("monitored_segments", 0) >= 0, "summary returned"),
        ("GeoJSON Hanoi real", "/segments/geojson?city=hanoi", lambda payload: len(payload.get("features", [])) >= 50, "hanoi real features >= 50"),
        ("GeoJSON HCMC real", "/segments/geojson?city=hcmc", lambda payload: len(payload.get("features", [])) >= 50, "hcmc real features >= 50"),
        (
            "GeoJSON HCMC expanded",
            "/segments/geojson?city=hcmc&include_demo_coverage=true",
            lambda payload: len(payload.get("features", [])) >= 120,
            "hcmc expanded features >= 120",
        ),
        ("Traffic segments", "/traffic/segments?city=hanoi", lambda payload: isinstance(payload, list) and len(payload) > 0, "segments > 0"),
        ("Forecast 15m", "/traffic/predict/HN_005?horizon=15m", lambda payload: "predicted_speed" in payload, "forecast returned"),
        ("Forecast 60m", "/traffic/predict/HN_005?horizon=60m", lambda payload: "predicted_speed" in payload, "forecast returned"),
        ("Predicted hotspots", "/hotspots/predicted?city=hanoi&horizon=15m", lambda payload: isinstance(payload, list), "risk list returned"),
        ("Model status", "/traffic/model/status?load_models=true", lambda payload: "horizons" in payload, "model status returned"),
        ("System status", "/system/status", lambda payload: "api" in payload and "data" in payload, "system status returned"),
    ]
    for name, endpoint, validator, detail in specs:
        code, payload, error, elapsed = fetch_json(base_url, endpoint)
        if code and 200 <= code < 400 and payload is not None and validator(payload):
            if name.startswith("GeoJSON"):
                detail = f"{len(payload.get('features', []))} features"
            elif name.startswith("Forecast"):
                detail = (
                    f"model={payload.get('model_name')}, "
                    f"coverage={payload.get('available_feature_count')}/{payload.get('required_feature_count')}, "
                    f"latency_ms={round(elapsed or 0, 1)}"
                )
            checks.append(item(name, "PASS", detail))
        else:
            checks.append(item(name, "FAIL", f"{code or 'NO_RESPONSE'} {error or 'invalid response'}"))
    return checks


def run_frontend_build() -> dict[str, str]:
    command = [shutil.which("bun") or "", "run", "build"]
    label = "bun run build"
    if not command[0]:
        npm = shutil.which("npm")
        if not npm:
            return item("Frontend build", "SKIPPED", "bun and npm are not installed")
        command = [npm, "run", "build"]
        label = "npm run build"
    started = time.perf_counter()
    proc = subprocess.run(command, cwd=PROJECT_ROOT / "frontend", text=True, capture_output=True)
    elapsed = round(time.perf_counter() - started, 2)
    if proc.returncode == 0:
        return item("Frontend build", "PASS", f"{label} completed in {elapsed}s")
    message = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ["build failed"]
    return item("Frontend build", "FAIL", message[0][:240])


def write_reports(report: dict[str, Any]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "demo_smoke_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Demo Smoke Report",
        "",
        f"Generated at: {report['generated_at']}",
        f"Base URL: `{report['base_url']}`",
        "",
        "| Check | Status | Detail |",
        "|---|---|---|",
    ]
    for check in report["checks"]:
        lines.append(f"| {check['check']} | {check['status']} | {check['detail']} |")
    lines.extend(
        [
            "",
            f"Overall status: **{report['overall_status']}**",
            "",
            "Endpoint failures are real demo blockers. Optional local dependencies such as Bun may be marked SKIPPED.",
        ]
    )
    (DOCS_DIR / "demo_smoke_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    checks = run_endpoint_checks(args.base_url)
    checks.append(run_frontend_build())
    required_failed = [check for check in checks if check["status"] == "FAIL" and check["check"] != "Frontend build"]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "checks": checks,
        "overall_status": "FAIL" if required_failed else "PASS",
    }
    write_reports(report)
    print("Wrote docs/demo_smoke_report.md and docs/demo_smoke_report.json")
    return 1 if required_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
