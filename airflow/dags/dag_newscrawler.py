"""Airflow DAG: dag_newscrawler

Schedule:
  - RSS sources  : */10 * * * *  (mỗi 10 phút)
  - HTML sources : */30 * * * *  (mỗi 30 phút)

Pipeline per source:
  fetch → parse → dedup → nlp_extract → geocode → produce_to_kafka
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Thêm project root vào sys.path khi chạy trong Airflow worker
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import yaml
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup

logger = logging.getLogger(__name__)

# ── Defaults ───────────────────────────────────────────────────────────────────

_DEFAULT_ARGS = {
    "owner": "newscrawler",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(minutes=5),
}

SOURCES_YAML = _PROJECT_ROOT / "sources.yaml"


# ── Task functions ─────────────────────────────────────────────────────────────

def _load_sources(**ctx) -> list[dict]:
    with open(SOURCES_YAML) as f:
        data = yaml.safe_load(f)
    sources = [s for s in data["sources"] if s.get("enabled", True)]
    ctx["ti"].xcom_push(key="sources", value=sources)
    logger.info("Loaded %d enabled sources", len(sources))
    return sources


def _fetch_source(source: dict, **ctx) -> list[dict]:
    """Fetch bài từ một source (rss hoặc html)."""
    import asyncio

    from ingestion.producers.rss_fetcher import fetch_rss
    from ingestion.producers.html_scraper import fetch_html, scrape_article_links
    from ingestion.producers.article_parser import extract_content

    source_name = source["name"]
    source_type = source["type"]
    articles: list[dict] = []

    if source_type == "rss":
        entries, _, _ = fetch_rss(source["url"])
        for e in entries:
            articles.append({
                "external_id": e["external_id"],
                "source": source_name,
                "source_type": "rss",
                "title": e["title"],
                "summary": e.get("summary", ""),
                "content": "",
                "link": e["link"],
                "published_at": e["published_at"].isoformat() if e.get("published_at") else None,
                "city_hint": source.get("city_hint"),
                "html_raw": "",
            })

    elif source_type == "html":
        links = asyncio.run(
            scrape_article_links(
                source["url"],
                article_selector=source.get("article_selector", "article"),
                link_selector=source.get("link_selector", "a"),
            )
        )
        for link in links[:20]:   # giới hạn 20 bài/lần
            html_bytes = asyncio.run(fetch_html(link))
            if not html_bytes:
                continue
            content = extract_content(html_bytes, url=link) or ""
            eid = hashlib.sha1(link.encode()).hexdigest()
            articles.append({
                "external_id": eid,
                "source": source_name,
                "source_type": "html",
                "title": "",
                "summary": "",
                "content": content,
                "link": link,
                "published_at": None,
                "city_hint": source.get("city_hint"),
                "html_raw": html_bytes.decode("utf-8", errors="replace"),
            })

    ctx["ti"].xcom_push(key=f"articles_{source_name}", value=articles)
    logger.info("Fetched %d articles from %s", len(articles), source_name)
    return articles


def _parse_articles(source_name: str, **ctx) -> list[dict]:
    """Lấy nội dung đầy đủ cho bài RSS (chỉ có summary)."""
    import asyncio
    from ingestion.producers.html_scraper import fetch_html
    from ingestion.producers.article_parser import extract_content

    articles: list[dict] = ctx["ti"].xcom_pull(key=f"articles_{source_name}")
    if not articles:
        return []

    enriched = []
    for art in articles:
        if art["source_type"] == "rss" and not art["content"] and art.get("link"):
            html_bytes = asyncio.run(fetch_html(art["link"]))
            if html_bytes:
                art["content"] = extract_content(html_bytes, url=art["link"]) or ""
                art["html_raw"] = html_bytes.decode("utf-8", errors="replace")
        enriched.append(art)

    ctx["ti"].xcom_push(key=f"parsed_{source_name}", value=enriched)
    return enriched


def _dedup(source_name: str, **ctx) -> list[dict]:
    from processing.silver.deduplicator import Deduplicator

    articles: list[dict] = ctx["ti"].xcom_pull(key=f"parsed_{source_name}") or []
    dedup = Deduplicator()
    unique: list[dict] = []

    for art in articles:
        is_dup, orig_id = dedup.check(
            url=art["link"],
            title=art["title"],
            content=art["content"],
            doc_id=art["external_id"],
            source=art["source"],
        )
        if not is_dup:
            dedup.register(art["link"], art["title"], art["content"], art["external_id"])
            unique.append(art)
        else:
            logger.debug("Dup detected: %s (orig=%s)", art["external_id"], orig_id)

    ctx["ti"].xcom_push(key=f"unique_{source_name}", value=unique)
    logger.info("Dedup %s: %d/%d unique", source_name, len(unique), len(articles))
    return unique


def _nlp_extract(source_name: str, **ctx) -> list[dict]:
    from processing.silver.preprocessor import preprocess
    from processing.silver.classifier import classify
    from processing.silver.ner import detect_city, extract_locations
    from processing.silver.severity import score_severity
    from models.event import City

    articles: list[dict] = ctx["ti"].xcom_pull(key=f"unique_{source_name}") or []
    enriched = []

    for art in articles:
        text = preprocess(f"{art['title']} {art['summary']} {art['content']}")
        event_type = classify(text)
        locations = extract_locations(text, city_hint=art.get("city_hint"))
        location_entity = locations[0] if locations else ""
        severity = score_severity(text)

        detected_city = detect_city(text) or art.get("city_hint", "")
        if "hà nội" in detected_city.lower() or "ha noi" in detected_city.lower():
            city = City.ha_noi.value
        elif any(k in detected_city.lower() for k in ("hcm", "hồ chí minh", "sài gòn")):
            city = City.ho_chi_minh.value
        else:
            city = City.unknown.value

        art.update({
            "event_type": event_type.value,
            "severity": severity,
            "location_entity": location_entity,
            "city": city,
        })
        enriched.append(art)

    ctx["ti"].xcom_push(key=f"nlp_{source_name}", value=enriched)
    return enriched


def _geocode(source_name: str, **ctx) -> list[dict]:
    from processing.silver.geocoder import geocode_with_confidence

    articles: list[dict] = ctx["ti"].xcom_pull(key=f"nlp_{source_name}") or []
    enriched = []

    for art in articles:
        loc = art.get("location_entity", "")
        if loc:
            lat, lon, conf, status = geocode_with_confidence(
                loc,
                city_hint=art.get("city_hint"),
                num_mirrors=len(art.get("mirrored_sources", [])),
            )
            art.update({
                "lat": lat,
                "lon": lon,
                "event_confidence": conf,
                "geocode_status": status,
            })
        else:
            art.update({"geocode_status": "skipped", "event_confidence": 0.0})
        enriched.append(art)

    ctx["ti"].xcom_push(key=f"geo_{source_name}", value=enriched)
    return enriched


def _produce_to_kafka(source_name: str, **ctx) -> None:
    import uuid
    from datetime import datetime, timezone

    from ingestion.kafka.producer import KafkaProducer
    from models.event import NewsEvent, EventType, City, GeocodeStatus

    articles: list[dict] = ctx["ti"].xcom_pull(key=f"geo_{source_name}") or []
    if not articles:
        return

    producer = KafkaProducer()
    try:
        for art in articles:
            try:
                published_at = None
                if art.get("published_at"):
                    from dateutil.parser import parse as parse_dt
                    published_at = parse_dt(art["published_at"])

                event = NewsEvent(
                    event_id=f"ev_{datetime.now(timezone.utc).strftime('%Y%m%d%H')}_{art['external_id'][:6]}",
                    source=art["source"],
                    source_url=art["link"],
                    published_at=published_at,
                    title=art.get("title", ""),
                    content=art.get("content", ""),
                    event_type=EventType(art.get("event_type", "other")),
                    severity=art.get("severity", 0),
                    location_entity=art.get("location_entity", ""),
                    lat=art.get("lat"),
                    lon=art.get("lon"),
                    event_confidence=art.get("event_confidence", 0.0),
                    geocode_status=GeocodeStatus(art.get("geocode_status", "skipped")),
                    city=City(art.get("city", "unknown")),
                    mirrored_sources=art.get("mirrored_sources", []),
                )
                producer.send(event.to_kafka_dict())
            except Exception as exc:
                logger.error("Failed to produce event %s: %s", art.get("external_id"), exc)
    finally:
        producer.close()

    logger.info("Produced %d events from %s to Kafka", len(articles), source_name)


def _emit_metrics(**ctx) -> None:
    """Log summary metrics (stub — extend với Prometheus push gateway nếu cần)."""
    logger.info("DAG run complete at %s", datetime.now(timezone.utc).isoformat())


# ── DAG definition ─────────────────────────────────────────────────────────────

def _build_dag(dag_id: str, schedule: str, source_type_filter: str) -> DAG:
    with DAG(
        dag_id=dag_id,
        default_args=_DEFAULT_ARGS,
        schedule_interval=schedule,
        start_date=datetime(2026, 1, 1),
        catchup=False,
        max_active_runs=1,
        tags=["newscrawler", source_type_filter],
    ) as dag:

        load_task = PythonOperator(
            task_id="load_sources_yaml",
            python_callable=_load_sources,
        )

        emit_task = PythonOperator(
            task_id="emit_metrics",
            python_callable=_emit_metrics,
        )

        # Đọc sources tĩnh để tạo task graph (Airflow cần biết task lúc parse time)
        try:
            with open(SOURCES_YAML) as f:
                _all_sources = [
                    s for s in yaml.safe_load(f)["sources"]
                    if s.get("enabled", True) and s["type"] == source_type_filter
                ]
        except Exception:
            _all_sources = []

        prev_group = load_task
        for source in _all_sources:
            sname = source["name"]
            with TaskGroup(group_id=f"source_{sname}") as tg:
                fetch = PythonOperator(
                    task_id="fetch",
                    python_callable=_fetch_source,
                    op_kwargs={"source": source},
                )
                parse = PythonOperator(
                    task_id="parse",
                    python_callable=_parse_articles,
                    op_kwargs={"source_name": sname},
                )
                dedup = PythonOperator(
                    task_id="dedup",
                    python_callable=_dedup,
                    op_kwargs={"source_name": sname},
                )
                nlp = PythonOperator(
                    task_id="nlp_extract",
                    python_callable=_nlp_extract,
                    op_kwargs={"source_name": sname},
                )
                geo = PythonOperator(
                    task_id="geocode",
                    python_callable=_geocode,
                    op_kwargs={"source_name": sname},
                )
                produce = PythonOperator(
                    task_id="produce",
                    python_callable=_produce_to_kafka,
                    op_kwargs={"source_name": sname},
                )
                fetch >> parse >> dedup >> nlp >> geo >> produce

            prev_group >> tg >> emit_task

        if not _all_sources:
            load_task >> emit_task

    return dag


dag_newscrawler_rss = _build_dag(
    dag_id="dag_newscrawler_rss",
    schedule="*/10 * * * *",
    source_type_filter="rss",
)

dag_newscrawler_html = _build_dag(
    dag_id="dag_newscrawler_html",
    schedule="*/30 * * * *",
    source_type_filter="html",
)
