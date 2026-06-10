"""Severity Scoring — keyword-based, trả về 0–3."""

from __future__ import annotations

_SEVERITY_RULES: list[tuple[int, list[str]]] = [
    (3, [
        "chết người", "tử vong", "thiệt mạng", "nguy kịch",
        "tắc nghiêm trọng", "kẹt nhiều giờ", "tê liệt giao thông",
        "ùn tắc nghiêm trọng", "ách tắc toàn tuyến",
    ]),
    (2, [
        "ùn tắc kéo dài", "phương tiện dồn ứ", "ngập sâu",
        "kẹt xe dài", "ùn ứ kéo dài", "tắc đường dài",
        "ùn tắc hàng km", "cấm đường hoàn toàn",
    ]),
    (1, [
        "ùn ứ cục bộ", "lưu thông chậm", "di chuyển khó khăn",
        "lưu thông ảnh hưởng", "ùn nhẹ", "chậm lại",
        "phân luồng", "cấm một chiều",
    ]),
]


def score_severity(text: str) -> int:
    """Trả về severity 0–3 dựa trên keyword match.

    Ưu tiên mức cao nhất tìm được.
    """
    text_lower = text.lower()
    for level, keywords in _SEVERITY_RULES:
        if any(kw in text_lower for kw in keywords):
            return level
    return 0
