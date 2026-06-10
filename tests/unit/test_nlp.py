"""Unit tests cho NLP pipeline — classifier, NER, severity."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import patch

from models.event import EventType
from nlp.classifier import _rule_classify
from nlp.severity import score_severity
from nlp.preprocessor import clean_html, normalize_unicode, preprocess


# ── Test samples (50+ câu) ────────────────────────────────────────────────────

ACCIDENT_SAMPLES = [
    ("Tai nạn nghiêm trọng trên cầu Nhật Tân", EventType.accident),
    ("Va chạm giữa xe tải và xe máy trên đường Giải Phóng", EventType.accident),
    ("Xe ôtô lật xe trên cầu Chương Dương", EventType.accident),
    ("Hai xe máy đâm vào nhau tại ngã tư", EventType.accident),
    ("Xe tải tông vào dải phân cách", EventType.accident),
    ("Vụ đụng nhau làm tắc đường Nguyễn Trãi", EventType.accident),
    ("Tai nạn giao thông khiến 3 người bị thương", EventType.accident),
    ("Ôtô húc vào xe máy trên đường Trường Chinh", EventType.accident),
]

FLOOD_SAMPLES = [
    ("Ngập sâu tại quận Bình Thạnh sau cơn mưa lớn", EventType.flood),
    ("Mưa lớn gây ngập nhiều tuyến đường ở TP.HCM", EventType.flood),
    ("Ngập lụt nghiêm trọng ở đường Nguyễn Hữu Cảnh", EventType.flood),
    ("Triều cường ngập đường Trần Xuân Soạn", EventType.flood),
    ("Nước ngập sâu 0.5m tại quận 7", EventType.flood),
    ("Ngập úng toàn bộ tuyến đường vành đai", EventType.flood),
]

ROAD_WORK_SAMPLES = [
    ("Cấm đường Lê Văn Lương để thi công metro", EventType.road_work),
    ("Sửa đường Nguyễn Trãi từ ngày 1/6", EventType.road_work),
    ("Rào chắn thi công hầm chui Kim Liên", EventType.road_work),
    ("Phân luồng giao thông trên đường Khuất Duy Tiến", EventType.road_work),
    ("Thi công nâng cấp cầu Bình Triệu giai đoạn 2", EventType.road_work),
    ("Đào đường Hoàng Quốc Việt lắp đặt cáp ngầm", EventType.road_work),
]

EVENT_SAMPLES = [
    ("Lễ hội đường phố khiến nhiều tuyến đường bị phong tỏa", EventType.event),
    ("Hội chợ xuân tại công viên Thống Nhất", EventType.event),
    ("Countdown năm mới tại hồ Hoàn Kiếm gây ùn tắc", EventType.event),
    ("Marathon Hà Nội cấm đường nhiều tuyến phố trung tâm", EventType.event),
    ("Lễ khai mạc SEA Games 32 khiến phố bị chặn", EventType.event),
]

WEATHER_SAMPLES = [
    ("Bão số 3 đổ bộ gây gió mạnh ảnh hưởng giao thông", EventType.weather),
    ("Gió mạnh cấp 8 làm đổ cây trên nhiều tuyến đường", EventType.weather),
    ("Sương mù dày đặc khiến xe đi chậm trên quốc lộ 1", EventType.weather),
    ("Áp thấp nhiệt đới mang mưa lớn vào đất liền", EventType.weather),
]

OTHER_SAMPLES = [
    ("Top 10 nhà hàng ngon tại Hà Nội", EventType.other),
    ("Kết quả bóng đá Việt Nam thắng Thái Lan", EventType.other),
    ("Giá vàng hôm nay tăng mạnh", EventType.other),
    ("Phim hay nhất tuần này tại rạp", EventType.other),
]

ALL_SAMPLES = (
    ACCIDENT_SAMPLES + FLOOD_SAMPLES + ROAD_WORK_SAMPLES +
    EVENT_SAMPLES + WEATHER_SAMPLES + OTHER_SAMPLES
)


class TestRuleClassifier:
    @pytest.mark.parametrize("text,expected", ACCIDENT_SAMPLES)
    def test_accident(self, text, expected):
        assert _rule_classify(text) == expected

    @pytest.mark.parametrize("text,expected", FLOOD_SAMPLES)
    def test_flood(self, text, expected):
        assert _rule_classify(text) == expected

    @pytest.mark.parametrize("text,expected", ROAD_WORK_SAMPLES)
    def test_road_work(self, text, expected):
        assert _rule_classify(text) == expected

    @pytest.mark.parametrize("text,expected", EVENT_SAMPLES)
    def test_event(self, text, expected):
        assert _rule_classify(text) == expected

    @pytest.mark.parametrize("text,expected", WEATHER_SAMPLES)
    def test_weather(self, text, expected):
        assert _rule_classify(text) == expected

    @pytest.mark.parametrize("text,expected", OTHER_SAMPLES)
    def test_other(self, text, expected):
        assert _rule_classify(text) == expected

    def test_precision_over_85_percent(self):
        correct = sum(1 for text, exp in ALL_SAMPLES if _rule_classify(text) == exp)
        precision = correct / len(ALL_SAMPLES)
        assert precision >= 0.85, f"Precision {precision:.2%} < 85%"


class TestSeverityScoring:
    def test_severity_3_keywords(self):
        assert score_severity("Vụ tai nạn làm chết người trên cầu") == 3
        assert score_severity("Tắc nghiêm trọng kéo dài nhiều giờ") == 3

    def test_severity_2_keywords(self):
        assert score_severity("Ùn tắc kéo dài trên đường Nguyễn Trãi") == 2
        assert score_severity("Ngập sâu tại nhiều khu vực") == 2

    def test_severity_1_keywords(self):
        assert score_severity("Lưu thông chậm trên đường vành đai") == 1
        assert score_severity("Ùn ứ cục bộ tại nút giao Khuất Duy Tiến") == 1

    def test_severity_0_no_keyword(self):
        assert score_severity("Thời tiết hôm nay đẹp") == 0

    def test_severity_higher_priority(self):
        # Khi có cả severity 3 và 2, trả về 3
        assert score_severity("Tắc nghiêm trọng kéo dài gây chết người") == 3


class TestPreprocessor:
    def test_clean_html_strips_tags(self):
        result = clean_html("<p>Tai <b>nạn</b> giao thông</p>")
        assert "<" not in result
        assert "Tai" in result and "nạn" in result

    def test_clean_html_decodes_entities(self):
        result = clean_html("Đường &amp; phố")
        assert "&amp;" not in result
        assert "&" in result

    def test_normalize_unicode_nfc(self):
        # NFD form (decomposed) should be converted to NFC
        import unicodedata
        nfd = unicodedata.normalize("NFD", "Hà Nội")
        result = normalize_unicode(nfd)
        assert unicodedata.is_normalized("NFC", result)

    def test_preprocess_pipeline(self):
        raw = "<div>Tai &lt;nạn&gt; xe máy <br/> ở Hà Nội</div>"
        result = preprocess(raw)
        assert "<" not in result
        assert "Tai" in result
