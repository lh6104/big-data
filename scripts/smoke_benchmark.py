#!/usr/bin/env python3
"""Measure local demo endpoint latency and write benchmark reports."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ENDPOINTS = [
    "/health",
    "/dashboard/summary?city=hanoi",
    "/segments/geojson?city=hanoi",
    "/segments/geojson?city=hcmc",
    "/segments/geojson?city=hcmc&include_demo_coverage=true",
    "/traffic/segments?city=hanoi",
    "/traffic/predict/HN_005?horizon=15m",
    "/traffic/predict/HN_005?horizon=60m",
    "/hotspots/predicted?city=hanoi&horizon=15m",
    "/traffic/model/status?load_models=true",
    "/system/status",
]


def _round_or_none(value: float | None, digits: int = 2) -> float | None:
    return round(value, digits) if value is not None else None


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def request_once(base_url: str, endpoint: str, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + endpoint, timeout=timeout) as response:
            body = response.read()
            return {
                "ok": 200 <= response.status < 400,
                "status_code": response.status,
                "latency_ms": (time.perf_counter() - started) * 1000.0,
                "payload_size_kb": len(body) / 1024.0,
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read()
        return {
            "ok": False,
            "status_code": exc.code,
            "latency_ms": (time.perf_counter() - started) * 1000.0,
            "payload_size_kb": len(body) / 1024.0 if body else 0.0,
            "error": str(exc),
        }
    except Exception as exc:
        return {"ok": False, "status_code": None, "latency_ms": None, "payload_size_kb": 0.0, "error": str(exc)}


def benchmark(base_url: str, runs: int, timeout: float) -> dict[str, Any]:
    endpoint_reports = []
    for endpoint in ENDPOINTS:
        results = [request_once(base_url, endpoint, timeout) for _ in range(runs)]
        successes = [item for item in results if item["ok"] and item["latency_ms"] is not None]
        latencies = [float(item["latency_ms"]) for item in successes]
        payloads = [float(item["payload_size_kb"]) for item in successes]
        endpoint_reports.append(
            {
                "endpoint": endpoint,
                "runs": runs,
                "success_count": len(successes),
                "success_rate": len(successes) / runs if runs else 0.0,
                "status_codes": sorted({item["status_code"] for item in results if item["status_code"] is not None}),
                "p50_ms": round(percentile(latencies, 0.50), 2) if latencies else None,
                "p95_ms": round(percentile(latencies, 0.95), 2) if latencies else None,
                "avg_ms": round(statistics.mean(latencies), 2) if latencies else None,
                "payload_size_kb": round(statistics.mean(payloads), 2) if payloads else None,
                "error": next((item["error"] for item in results if item["error"]), None),
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "runs": runs,
        "endpoints": endpoint_reports,
        "extra_metrics": collect_extra_metrics(base_url, timeout),
    }


def _measure_model_runtime() -> dict[str, Any]:
    try:
        from api.services import model_inference
        from api.services.model_inference import load_model, predict_for_segment
    except Exception as exc:
        return {"status": "NOT MEASURED", "error": str(exc)}

    load_times: dict[str, float] = {}
    inference_times: dict[str, float] = {}
    try:
        model_inference._load_model_cached.cache_clear()
        for horizon in ("15m", "60m"):
            started = time.perf_counter()
            load_model(horizon)
            load_times[horizon] = (time.perf_counter() - started) * 1000.0
        for horizon in ("15m", "60m"):
            started = time.perf_counter()
            predict_for_segment("HN_005", horizon)
            inference_times[horizon] = (time.perf_counter() - started) * 1000.0
    except Exception as exc:
        return {"status": "NOT MEASURED", "error": str(exc)}

    return {
        "status": "measured_in_benchmark_process",
        "model_load_time_ms": {key: round(value, 2) for key, value in load_times.items()},
        "model_inference_time_ms": {key: round(value, 2) for key, value in inference_times.items()},
    }


def _read_process_rss_mb(pid: str) -> float | None:
    try:
        status = Path("/proc") / pid / "status"
        for line in status.read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                parts = line.split()
                return int(parts[1]) / 1024.0
    except Exception:
        return None
    return None


def _api_process_memory_mb() -> dict[str, Any]:
    proc_root = Path("/proc")
    if not proc_root.exists():
        return {"status": "NOT MEASURED", "reason": "/proc is unavailable"}
    matches: list[dict[str, Any]] = []
    for entry in proc_root.iterdir():
        if not entry.name.isdigit() or entry.name == str(os.getpid()):
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", errors="ignore")
        except Exception:
            continue
        if "uvicorn" not in cmdline or "api.main:app" not in cmdline:
            continue
        rss = _read_process_rss_mb(entry.name)
        matches.append({"pid": int(entry.name), "rss_mb": _round_or_none(rss), "cmd": cmdline[:160]})
    if not matches:
        return {"status": "NOT MEASURED", "reason": "no local uvicorn api.main:app process found"}
    total = sum(item["rss_mb"] or 0.0 for item in matches)
    return {"status": "measured_from_procfs", "total_rss_mb": round(total, 2), "processes": matches}


def _frontend_build_time_from_smoke_report() -> dict[str, Any]:
    report_path = DOCS_DIR / "demo_smoke_report.json"
    if not report_path.exists():
        return {"status": "NOT MEASURED", "reason": "run make demo-check first"}
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "NOT MEASURED", "reason": str(exc)}
    build = next((check for check in report.get("checks", []) if check.get("check") == "Frontend build"), None)
    if not build:
        return {"status": "NOT MEASURED", "reason": "frontend build check missing"}
    return {"status": build.get("status"), "detail": build.get("detail")}


def collect_extra_metrics(base_url: str, timeout: float) -> dict[str, Any]:
    # Ensure model endpoints have been hit before reading API RSS where possible.
    request_once(base_url, "/traffic/model/status?load_models=true", timeout)
    return {
        "model_runtime": _measure_model_runtime(),
        "api_memory_after_model_load": _api_process_memory_mb(),
        "frontend_build": _frontend_build_time_from_smoke_report(),
    }


def write_reports(report: dict[str, Any]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "performance_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Performance Report",
        "",
        f"Generated at: {report['generated_at']}",
        f"Base URL: `{report['base_url']}`",
        f"Runs per endpoint: `{report['runs']}`",
        "",
        "| Endpoint | Success rate | p50 ms | p95 ms | Avg ms | Payload KB | Status |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in report["endpoints"]:
        status = "PASS" if item["success_rate"] == 1.0 else "FAIL" if item["success_rate"] == 0 else "PARTIAL"
        lines.append(
            f"| `{item['endpoint']}` | {item['success_rate'] * 100:.0f}% | "
            f"{item['p50_ms'] if item['p50_ms'] is not None else 'NOT MEASURED'} | "
            f"{item['p95_ms'] if item['p95_ms'] is not None else 'NOT MEASURED'} | "
            f"{item['avg_ms'] if item['avg_ms'] is not None else 'NOT MEASURED'} | "
            f"{item['payload_size_kb'] if item['payload_size_kb'] is not None else 'NOT MEASURED'} | {status} |"
        )
    critical_success = all(item["success_rate"] == 1.0 for item in report["endpoints"][:8])
    lines.extend(
        [
            "",
            "## Notes",
            "",
            f"- Suitable for local demo: {'yes' if critical_success else 'no'}",
            "- Production-ready: no",
            "- Bottlenecks: `/hotspots/predicted` uses short-TTL cache for demo responsiveness; cold path still needs precomputed/batch risk scoring before scale-out.",
        ]
    )
    extra = report.get("extra_metrics", {})
    model_runtime = extra.get("model_runtime", {})
    api_memory = extra.get("api_memory_after_model_load", {})
    frontend_build = extra.get("frontend_build", {})
    lines.extend(
        [
            "",
            "## Extra Metrics",
            "",
            f"- Model load time: `{model_runtime.get('model_load_time_ms', 'NOT MEASURED')}` ({model_runtime.get('status', 'NOT MEASURED')})",
            f"- Model inference time: `{model_runtime.get('model_inference_time_ms', 'NOT MEASURED')}` ({model_runtime.get('status', 'NOT MEASURED')})",
            f"- API memory after model load: `{api_memory.get('total_rss_mb', 'NOT MEASURED')}` MB ({api_memory.get('status', 'NOT MEASURED')})",
            f"- Frontend build time: {frontend_build.get('detail', 'NOT MEASURED')} ({frontend_build.get('status', 'NOT MEASURED')})",
        ]
    )
    (DOCS_DIR / "performance_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    report = benchmark(args.base_url, max(args.runs, 1), args.timeout)
    write_reports(report)
    print("Wrote docs/performance_report.md and docs/performance_report.json")
    return 1 if any(item["success_rate"] == 0 for item in report["endpoints"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
