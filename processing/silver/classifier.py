"""Event Classifier — rule-based (mặc định) + PhoBERT wrapper (khi có checkpoint)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from models.event import EventType
from infra.settings import settings

logger = logging.getLogger(__name__)

# ── Rule-based keyword dictionary ─────────────────────────────────────────────

_RULES: dict[EventType, list[str]] = {
    EventType.accident: [
        "tai nạn", "va chạm", "lật xe", "đâm vào", "đụng nhau",
        "tai nạn giao thông", "xe máy đâm", "ôtô đâm", "xe tải đâm",
        "húc vào", "tông vào", "tông nhau", "lao vào",
    ],
    EventType.flood: [
        "ngập", "ngập lụt", "ngập sâu", "mưa lớn gây ngập",
        "nước ngập", "ngập úng", "triều cường ngập",
    ],
    EventType.road_work: [
        "sửa đường", "thi công", "rào chắn", "cấm đường",
        "phân luồng", "nâng cấp đường", "mở rộng đường",
        "xây dựng cầu", "thi công hầm", "cải tạo đường",
        "đào đường", "láng nhựa",
    ],
    EventType.event: [
        "lễ hội", "hội chợ", "sự kiện", "biểu diễn", "countdown",
        "lễ kỷ niệm", "đại hội", "marathon", "giải chạy",
        "chương trình biểu diễn", "lễ khai mạc",
    ],
    EventType.weather: [
        "bão", "gió mạnh", "sương mù dày", "mưa lớn", "mưa đá",
        "lũ lụt", "lốc xoáy", "áp thấp nhiệt đới",
    ],
}

# Thứ tự ưu tiên khi match nhiều loại
_PRIORITY = [
    EventType.accident,
    EventType.flood,
    EventType.road_work,
    EventType.event,
    EventType.weather,
]


def _rule_classify(text: str) -> EventType:
    text_lower = text.lower()
    for etype in _PRIORITY:
        for kw in _RULES[etype]:
            if kw in text_lower:
                return etype
    return EventType.other


# ── PhoBERT wrapper ────────────────────────────────────────────────────────────

_phobert_pipeline = None


def _load_phobert(checkpoint: str):
    """Load PhoBERT classifier pipeline từ local checkpoint."""
    global _phobert_pipeline
    if _phobert_pipeline is not None:
        return _phobert_pipeline
    try:
        from transformers import pipeline as hf_pipeline
        logger.info("Loading PhoBERT from %s", checkpoint)
        _phobert_pipeline = hf_pipeline(
            "text-classification",
            model=checkpoint,
            tokenizer=checkpoint,
            device=-1,                   # CPU; dùng device=0 nếu có GPU
            max_length=settings.NLP_MAX_LENGTH,
            truncation=True,
        )
        logger.info("PhoBERT loaded successfully")
        return _phobert_pipeline
    except Exception as exc:
        logger.error("Cannot load PhoBERT: %s — falling back to rule-based", exc)
        return None


# Mapping label PhoBERT → EventType (phụ thuộc vào cách gán nhãn lúc fine-tune)
_PHOBERT_LABEL_MAP: dict[str, EventType] = {
    "LABEL_0": EventType.accident,
    "LABEL_1": EventType.flood,
    "LABEL_2": EventType.road_work,
    "LABEL_3": EventType.event,
    "LABEL_4": EventType.weather,
    "LABEL_5": EventType.other,
    # Nếu fine-tune với tên nhãn rõ ràng:
    "accident": EventType.accident,
    "flood": EventType.flood,
    "road_work": EventType.road_work,
    "event": EventType.event,
    "weather": EventType.weather,
    "other": EventType.other,
}


def classify(text: str) -> EventType:
    """Phân loại sự kiện.

    Dùng PhoBERT nếu checkpoint được cấu hình và tồn tại, ngược lại dùng rule-based.
    """
    checkpoint = settings.PHOBERT_CHECKPOINT
    if checkpoint and (Path(checkpoint).exists() or not checkpoint.startswith("/")):
        pipe = _load_phobert(checkpoint)
        if pipe is not None:
            try:
                result = pipe(text[:512])[0]
                label = result.get("label", "")
                return _PHOBERT_LABEL_MAP.get(label, EventType.other)
            except Exception as exc:
                logger.warning("PhoBERT inference error: %s — using rule-based", exc)

    return _rule_classify(text)
