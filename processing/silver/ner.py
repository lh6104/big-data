"""Named Entity Recognition — trích địa danh tiếng Việt."""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ── Dictionary-based: quận/huyện Hà Nội + TP.HCM ─────────────────────────────
_HANOI_DISTRICTS = [
    "Hoàn Kiếm", "Ba Đình", "Đống Đa", "Hai Bà Trưng", "Hoàng Mai",
    "Thanh Xuân", "Cầu Giấy", "Tây Hồ", "Long Biên", "Nam Từ Liêm",
    "Bắc Từ Liêm", "Hà Đông", "Sơn Tây", "Đan Phượng", "Hoài Đức",
    "Quốc Oai", "Thạch Thất", "Chương Mỹ", "Thanh Oai", "Thường Tín",
    "Phú Xuyên", "Ứng Hòa", "Mỹ Đức", "Mê Linh", "Sóc Sơn", "Đông Anh",
    "Gia Lâm", "Ba Vì",
]

_HCMC_DISTRICTS = [
    "Quận 1", "Quận 2", "Quận 3", "Quận 4", "Quận 5", "Quận 6",
    "Quận 7", "Quận 8", "Quận 9", "Quận 10", "Quận 11", "Quận 12",
    "Bình Thạnh", "Gò Vấp", "Phú Nhuận", "Tân Bình", "Tân Phú",
    "Bình Tân", "Thủ Đức", "Củ Chi", "Hóc Môn", "Bình Chánh",
    "Nhà Bè", "Cần Giờ",
]

_MAJOR_ROADS_HANOI = [
    "Nguyễn Trãi", "Khuất Duy Tiến", "Lê Văn Lương", "Tố Hữu",
    "Hoàng Quốc Việt", "Xuân Thủy", "Cầu Giấy", "Kim Mã", "Liễu Giai",
    "Đội Cấn", "Phan Đình Phùng", "Trần Phú", "Giải Phóng", "Đại La",
    "Minh Khai", "Trường Chinh", "Nguyễn Xiển", "Vành Đai 3",
    "Cầu Nhật Tân", "Cầu Long Biên", "Cầu Chương Dương", "Cầu Thăng Long",
    "Hầm Kim Liên", "Đường Vành Đai",
]

_MAJOR_ROADS_HCMC = [
    "Điện Biên Phủ", "Võ Văn Kiệt", "Hùng Vương", "Nguyễn Văn Linh",
    "Mai Chí Thọ", "Phạm Văn Đồng", "Xa Lộ Hà Nội", "Quốc lộ 1",
    "Đại lộ Đông Tây", "Nguyễn Hữu Thọ", "Lê Văn Việt",
    "Cầu Sài Gòn", "Hầm sông Sài Gòn", "Cầu Bình Triệu",
]

_ALL_LOCATIONS: list[str] = (
    _HANOI_DISTRICTS + _HCMC_DISTRICTS + _MAJOR_ROADS_HANOI + _MAJOR_ROADS_HCMC
)
# Sort dài trước để match greedy
_ALL_LOCATIONS.sort(key=len, reverse=True)

_CITY_KEYWORDS = {
    "Hà Nội": ["hà nội", "ha noi", "thủ đô"],
    "TP.HCM": ["tp.hcm", "tp hcm", "hcm", "thành phố hồ chí minh", "sài gòn", "saigon"],
}


def _dict_match(text: str) -> list[str]:
    """Tìm địa danh trong dict."""
    found = []
    for loc in _ALL_LOCATIONS:
        if loc.lower() in text.lower() and loc not in found:
            found.append(loc)
    return found


def _underthesea_ner(text: str) -> list[str]:
    """NER bằng underthesea, lấy entity loại LOC."""
    try:
        from underthesea import ner
        results = ner(text)
        locs = []
        for item in results:
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                word, _, tag = item[0], item[1], item[2]
                if "LOC" in tag:
                    locs.append(word)
        return locs
    except Exception as exc:
        logger.debug("underthesea NER error: %s", exc)
        return []


def detect_city(text: str) -> Optional[str]:
    """Phát hiện thành phố trong text."""
    text_lower = text.lower()
    for city, keywords in _CITY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return city
    return None


def extract_locations(text: str, city_hint: Optional[str] = None) -> list[str]:
    """Trích xuất địa danh từ văn bản (kết hợp NER + dictionary matcher).

    Returns:
        list[str] — danh sách địa danh, ghép city_hint nếu thiếu thành phố.
    """
    ner_locs = _underthesea_ner(text)
    dict_locs = _dict_match(text)

    # Merge, giữ thứ tự (NER ưu tiên)
    seen: set[str] = set()
    merged: list[str] = []
    for loc in ner_locs + dict_locs:
        if loc not in seen:
            merged.append(loc)
            seen.add(loc)

    if not merged:
        return []

    # Thêm city_hint vào entity đầu tiên nếu chưa có tên thành phố
    city = detect_city(text) or city_hint
    result: list[str] = []
    for loc in merged:
        loc_lower = loc.lower()
        has_city = any(
            kw in loc_lower
            for kws in _CITY_KEYWORDS.values()
            for kw in kws
        )
        if not has_city and city:
            result.append(f"{loc}, {city}")
        else:
            result.append(loc)
    return result


def primary_location(text: str, city_hint: Optional[str] = None) -> str:
    """Trả về địa danh đại diện (entity đầu tiên)."""
    locs = extract_locations(text, city_hint=city_hint)
    return locs[0] if locs else ""
