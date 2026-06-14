"""Road segment metadata endpoints."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Any, List, Optional
from datetime import datetime
import logging
import ast
import json
import math

from api.services.local_data import DataUnavailableError, latest_by_segment, normalize_city, synthetic_geojson_line, traffic_features

logger = logging.getLogger(__name__)

router = APIRouter()


DEMO_COVERAGE_TARGETS = {"hanoi": 720, "hcmc": 620}
DEMO_CORRIDORS: dict[str, list[dict[str, Any]]] = {
    "hanoi": [
        {"name": "Demo Ring Road 3", "points": [(21.0360, 105.7818), (21.0244, 105.7814), (21.0076, 105.7888), (20.9988, 105.7994), (20.9849, 105.7989)]},
        {"name": "Demo Nguyen Trai - Tran Phu", "points": [(21.0022, 105.8195), (20.9956, 105.8220), (20.9800, 105.7870), (20.9690, 105.7750)]},
        {"name": "Demo Giai Phong", "points": [(21.0062, 105.8460), (20.9940, 105.8424), (20.9761, 105.8410), (20.9588, 105.8208)]},
        {"name": "Demo Vo Chi Cong - Nhat Tan", "points": [(21.0521, 105.7852), (21.0600, 105.8100), (21.0905, 105.8178), (21.1210, 105.8200)]},
        {"name": "Demo Hoan Kiem River", "points": [(21.0397, 105.8847), (21.0276, 105.9002), (21.0005, 105.8917), (20.9990, 105.8798)]},
        {"name": "Demo Cau Giay Core", "points": [(21.0368, 105.7846), (21.0320, 105.8006), (21.0230, 105.8100), (21.0189, 105.8320)]},
        {"name": "Demo Tay Ho - Ba Dinh", "points": [(21.0645, 105.8355), (21.0524, 105.8373), (21.0372, 105.8146), (21.0280, 105.8340)]},
        {"name": "Demo Long Bien - Co Linh", "points": [(21.0470, 105.8760), (21.0397, 105.8847), (21.0276, 105.9002), (21.0005, 105.8917)]},
        {"name": "Demo Ha Dong - To Huu", "points": [(20.9731, 105.7816), (20.9953, 105.7857), (21.0030, 105.8010), (21.0142, 105.7939)]},
        {"name": "Demo Ring Road 2", "points": [(21.0670, 105.8200), (21.0450, 105.8050), (21.0180, 105.7900), (20.9950, 105.8070), (20.9880, 105.8500), (21.0000, 105.8830)]},
        {"name": "Demo Thang Long - Noi Bai", "points": [(21.0400, 105.7800), (21.0800, 105.7760), (21.1400, 105.7770), (21.2200, 105.7800)]},
        {"name": "Demo Bac Tu Liem - Tay Ho", "points": [(21.0800, 105.7600), (21.0700, 105.7900), (21.0650, 105.8250), (21.0600, 105.8550)]},
        {"name": "Demo Dong Anh - Soc Son", "points": [(21.1100, 105.8200), (21.1700, 105.8350), (21.2500, 105.8500), (21.3100, 105.8700)]},
        {"name": "Demo Gia Lam - Bac Ninh", "points": [(21.0300, 105.9400), (21.0600, 106.0200), (21.1000, 106.0900), (21.1850, 106.0760)]},
        {"name": "Demo Long Bien - Hai Duong", "points": [(21.0250, 105.9000), (20.9800, 106.0200), (20.9400, 106.1600), (20.9400, 106.3300)]},
        {"name": "Demo Hanoi - Hung Yen", "points": [(20.9950, 105.9000), (20.9300, 105.9700), (20.8500, 106.0400), (20.6500, 106.0600)]},
        {"name": "Demo Hanoi - Hai Phong", "points": [(21.0000, 105.9000), (20.9500, 106.1500), (20.9000, 106.3500), (20.8600, 106.6800)]},
        {"name": "Demo Hanoi - Vinh Phuc", "points": [(21.0500, 105.7600), (21.1800, 105.6300), (21.3000, 105.6000), (21.3600, 105.5500)]},
    ],
    "hcmc": [
        {"name": "Demo Vo Van Kiet", "points": [(10.7556, 106.6803), (10.7675, 106.7061), (10.7757, 106.7004), (10.7810, 106.7350)]},
        {"name": "Demo Dien Bien Phu - Hanoi Highway", "points": [(10.7904, 106.6975), (10.8015, 106.7148), (10.8230, 106.7600), (10.8621, 106.7948)]},
        {"name": "Demo Nguyen Van Linh", "points": [(10.7298, 106.7014), (10.7280, 106.7050), (10.7405, 106.7420), (10.7671, 106.7729)]},
        {"name": "Demo Cong Hoa - Truong Chinh", "points": [(10.8012, 106.6525), (10.8010, 106.6800), (10.7904, 106.6975), (10.8015, 106.7148)]},
        {"name": "Demo Nguyen Huu Canh - Mai Chi Tho", "points": [(10.7901, 106.7197), (10.7810, 106.7350), (10.7765, 106.7570), (10.8020, 106.7700)]},
        {"name": "Demo Cach Mang Thang Tam", "points": [(10.7769, 106.7009), (10.7890, 106.6820), (10.8012, 106.6525), (10.8230, 106.6280)]},
        {"name": "Demo Pham Van Dong", "points": [(10.8015, 106.7148), (10.8200, 106.7050), (10.8400, 106.6950), (10.8621, 106.6880)]},
        {"name": "Demo District 7 - Thu Thiem", "points": [(10.7298, 106.7014), (10.7450, 106.7180), (10.7650, 106.7350), (10.7901, 106.7197)]},
        {"name": "Demo Ring Road 2 HCMC", "points": [(10.8400, 106.6200), (10.8200, 106.6900), (10.8000, 106.7600), (10.7600, 106.7700), (10.7200, 106.7200)]},
        {"name": "Demo Binh Duong Connector", "points": [(10.8600, 106.7000), (10.9300, 106.7000), (11.0100, 106.6800), (11.0600, 106.6500)]},
        {"name": "Demo Dong Nai Connector", "points": [(10.8200, 106.7800), (10.9000, 106.8800), (10.9500, 106.9800), (10.9600, 107.1200)]},
        {"name": "Demo Long An Connector", "points": [(10.7250, 106.6400), (10.6600, 106.5600), (10.6000, 106.4800), (10.5400, 106.4100)]},
        {"name": "Demo Vung Tau Highway", "points": [(10.7800, 106.7600), (10.7500, 106.9000), (10.7000, 107.0500), (10.6200, 107.1800), (10.4200, 107.1300)]},
    ],
}

DEMO_LOCAL_GRIDS: dict[str, list[dict[str, Any]]] = {
    "hanoi": [
        {"name": "Hoan Kiem - Ba Dinh local roads", "bounds": (21.018, 21.055, 105.815, 105.875), "lat_lines": 9, "lon_lines": 12},
        {"name": "Cau Giay - Nam Tu Liem local roads", "bounds": (21.000, 21.055, 105.735, 105.815), "lat_lines": 10, "lon_lines": 13},
        {"name": "Thanh Xuan - Ha Dong local roads", "bounds": (20.955, 21.010, 105.750, 105.835), "lat_lines": 10, "lon_lines": 13},
        {"name": "Long Bien - Gia Lam local roads", "bounds": (20.995, 21.070, 105.870, 105.990), "lat_lines": 11, "lon_lines": 14},
        {"name": "Tay Ho - Bac Tu Liem local roads", "bounds": (21.055, 21.105, 105.745, 105.865), "lat_lines": 9, "lon_lines": 13},
        {"name": "Dong Anh local roads", "bounds": (21.090, 21.210, 105.770, 105.930), "lat_lines": 10, "lon_lines": 13},
        {"name": "Bac Ninh urban connectors", "bounds": (21.145, 21.225, 106.020, 106.125), "lat_lines": 8, "lon_lines": 11},
        {"name": "Hung Yen urban connectors", "bounds": (20.625, 20.705, 106.010, 106.110), "lat_lines": 8, "lon_lines": 10},
    ],
    "hcmc": [
        {"name": "District 1 - 3 - 10 local roads", "bounds": (10.760, 10.795, 106.675, 106.715), "lat_lines": 8, "lon_lines": 10},
        {"name": "Tan Binh - Tan Phu local roads", "bounds": (10.785, 10.840, 106.615, 106.675), "lat_lines": 10, "lon_lines": 12},
        {"name": "Thu Duc local roads", "bounds": (10.790, 10.890, 106.735, 106.855), "lat_lines": 11, "lon_lines": 13},
        {"name": "District 7 - Nha Be local roads", "bounds": (10.675, 10.755, 106.690, 106.780), "lat_lines": 10, "lon_lines": 12},
        {"name": "Binh Chanh - District 8 local roads", "bounds": (10.695, 10.760, 106.580, 106.675), "lat_lines": 9, "lon_lines": 12},
        {"name": "Binh Duong urban connectors", "bounds": (10.925, 11.050, 106.620, 106.750), "lat_lines": 10, "lon_lines": 12},
        {"name": "Bien Hoa urban connectors", "bounds": (10.900, 11.000, 106.800, 106.930), "lat_lines": 9, "lon_lines": 12},
        {"name": "Long An urban connectors", "bounds": (10.520, 10.650, 106.360, 106.500), "lat_lines": 9, "lon_lines": 12},
    ],
}

DEMO_CITY_MESH_BOUNDS: dict[str, tuple[float, float, float, float]] = {
    "hanoi": (20.92, 21.22, 105.70, 106.08),
    "hcmc": (10.58, 10.96, 106.48, 106.92),
}


class Segment(BaseModel):
    """Road segment details."""
    segment_id: str
    city: str
    road_class: str
    district: str
    length_m: float
    speed_limit: int
    lat: float
    lon: float
    timestamp: datetime


class SegmentGeoJSON(BaseModel):
    """GeoJSON feature for Leaflet mapping."""
    type: str = "FeatureCollection"
    features: List[dict]


class LiveMapSegment(BaseModel):
    """Clean road-level segment for the Live Map dashboard."""
    id: str
    name: str
    city: str
    roadType: str
    geometry: dict
    currentSpeed: float
    freeFlowSpeed: float
    speedRatio: float
    jamFactor: float
    congestionLevel: str
    travelTimeDelayMin: int
    source: str
    provider: str = "local"
    latestTimestamp: str = ""
    confidence: float = 1.0


class LiveMapSegmentsResponse(BaseModel):
    """Road segments returned for clean Live Map rendering."""
    segments: List[LiveMapSegment]


CURATED_LIVE_MAP_ROADS: dict[str, list[dict[str, Any]]] = {
    "hanoi": [
        {"id": "HN_CURATED_VANH_DAI_3", "name": "Vanh Dai 3", "roadType": "Highway", "points": [(21.0360, 105.7818), (21.0244, 105.7814), (21.0076, 105.7888), (20.9988, 105.7994), (20.9849, 105.7989)], "speed": (27, 60, 7.6)},
        {"id": "HN_CURATED_NGUYEN_TRAI", "name": "Nguyen Trai", "roadType": "Arterial", "points": [(21.0022, 105.8195), (20.9956, 105.8220), (20.9800, 105.7870), (20.9690, 105.7750)], "speed": (18, 45, 8.4)},
        {"id": "HN_CURATED_TRUONG_CHINH", "name": "Truong Chinh", "roadType": "Arterial", "points": [(21.0036, 105.8270), (21.0000, 105.8200), (20.9970, 105.8100), (20.9950, 105.7950)], "speed": (20, 42, 8.0)},
        {"id": "HN_CURATED_GIAI_PHONG", "name": "Giai Phong", "roadType": "Arterial", "points": [(21.0062, 105.8460), (20.9940, 105.8424), (20.9761, 105.8410), (20.9588, 105.8208)], "speed": (23, 48, 7.6)},
        {"id": "HN_CURATED_PHAM_VAN_DONG", "name": "Pham Van Dong", "roadType": "Highway", "points": [(21.0900, 105.7760), (21.0700, 105.7800), (21.0500, 105.7840), (21.0368, 105.7846)], "speed": (34, 65, 5.9)},
        {"id": "HN_CURATED_CAU_GIAY", "name": "Cau Giay", "roadType": "Arterial", "points": [(21.0368, 105.7846), (21.0320, 105.8006), (21.0230, 105.8100), (21.0189, 105.8320)], "speed": (26, 48, 7.2)},
        {"id": "HN_CURATED_LANG", "name": "Lang", "roadType": "Arterial", "points": [(21.0230, 105.8100), (21.0142, 105.8085), (21.0036, 105.8270), (20.9956, 105.8220)], "speed": (29, 45, 5.7)},
        {"id": "HN_CURATED_TRAN_DUY_HUNG", "name": "Tran Duy Hung", "roadType": "Arterial", "points": [(21.0142, 105.7939), (21.0090, 105.8000), (21.0050, 105.8085), (21.0030, 105.8170)], "speed": (25, 46, 6.8)},
        {"id": "HN_CURATED_NHAT_TAN", "name": "Vo Chi Cong - Nhat Tan", "roadType": "Highway", "points": [(21.0521, 105.7852), (21.0600, 105.8100), (21.0905, 105.8178), (21.1210, 105.8200)], "speed": (42, 70, 4.2)},
        {"id": "HN_CURATED_LONG_BIEN", "name": "Long Bien - Co Linh", "roadType": "Arterial", "points": [(21.0470, 105.8760), (21.0397, 105.8847), (21.0276, 105.9002), (21.0005, 105.8917)], "speed": (31, 52, 5.4)},
    ],
    "hcmc": [
        {"id": "HCM_CURATED_VO_VAN_KIET", "name": "Vo Van Kiet", "roadType": "Arterial", "points": [(10.7556, 106.6803), (10.7675, 106.7061), (10.7757, 106.7004), (10.7810, 106.7350)], "speed": (30, 55, 6.2)},
        {"id": "HCM_CURATED_DIEN_BIEN_PHU", "name": "Dien Bien Phu - Hanoi Highway", "roadType": "Highway", "points": [(10.7904, 106.6975), (10.8015, 106.7148), (10.8230, 106.7600), (10.8621, 106.7948)], "speed": (28, 65, 7.8)},
        {"id": "HCM_CURATED_NGUYEN_VAN_LINH", "name": "Nguyen Van Linh", "roadType": "Highway", "points": [(10.7298, 106.7014), (10.7280, 106.7050), (10.7405, 106.7420), (10.7671, 106.7729)], "speed": (37, 70, 5.4)},
        {"id": "HCM_CURATED_CONG_HOA", "name": "Cong Hoa - Truong Chinh", "roadType": "Arterial", "points": [(10.8012, 106.6525), (10.8010, 106.6800), (10.7904, 106.6975), (10.8015, 106.7148)], "speed": (24, 50, 7.2)},
        {"id": "HCM_CURATED_MAI_CHI_THO", "name": "Nguyen Huu Canh - Mai Chi Tho", "roadType": "Arterial", "points": [(10.7901, 106.7197), (10.7810, 106.7350), (10.7765, 106.7570), (10.8020, 106.7700)], "speed": (27, 55, 6.9)},
        {"id": "HCM_CURATED_CMT8", "name": "Cach Mang Thang Tam", "roadType": "Arterial", "points": [(10.7769, 106.7009), (10.7890, 106.6820), (10.8012, 106.6525), (10.8230, 106.6280)], "speed": (21, 45, 7.7)},
        {"id": "HCM_CURATED_PHAM_VAN_DONG", "name": "Pham Van Dong", "roadType": "Highway", "points": [(10.8015, 106.7148), (10.8200, 106.7050), (10.8400, 106.6950), (10.8621, 106.6880)], "speed": (43, 70, 4.6)},
        {"id": "HCM_CURATED_D7_THU_THIEM", "name": "District 7 - Thu Thiem", "roadType": "Arterial", "points": [(10.7298, 106.7014), (10.7450, 106.7180), (10.7650, 106.7350), (10.7901, 106.7197)], "speed": (32, 58, 5.7)},
    ],
}

CURATED_LIVE_MAP_ROADS["hanoi"].extend(
    [
        {"id": "HN_CURATED_VANH_DAI_2", "name": "Vanh Dai 2", "roadType": "Highway", "points": [(21.0670, 105.8200), (21.0450, 105.8050), (21.0180, 105.7900), (20.9950, 105.8070), (20.9880, 105.8500), (21.0000, 105.8830)]},
        {"id": "HN_CURATED_TRAN_PHU", "name": "Tran Phu", "roadType": "Arterial", "points": [(20.9800, 105.7870), (20.9828, 105.7945), (20.9868, 105.8030), (20.9956, 105.8220)]},
        {"id": "HN_CURATED_TAY_SON", "name": "Tay Son", "roadType": "Arterial", "points": [(21.0036, 105.8270), (21.0010, 105.8200), (20.9982, 105.8120), (20.9956, 105.8040)]},
        {"id": "HN_CURATED_CHUA_BOC", "name": "Chua Boc", "roadType": "Collector", "points": [(21.0122, 105.8280), (21.0070, 105.8240), (21.0036, 105.8270), (20.9990, 105.8290)]},
        {"id": "HN_CURATED_THAI_HA", "name": "Thai Ha", "roadType": "Collector", "points": [(21.0158, 105.8170), (21.0105, 105.8150), (21.0045, 105.8170), (20.9990, 105.8200)]},
        {"id": "HN_CURATED_XUAN_THUY", "name": "Xuan Thuy", "roadType": "Arterial", "points": [(21.0368, 105.7846), (21.0360, 105.7925), (21.0352, 105.8015), (21.0320, 105.8100)]},
        {"id": "HN_CURATED_HOANG_QUOC_VIET", "name": "Hoang Quoc Viet", "roadType": "Arterial", "points": [(21.0470, 105.7810), (21.0460, 105.7940), (21.0450, 105.8080), (21.0440, 105.8220)]},
        {"id": "HN_CURATED_HOANG_HOA_THAM", "name": "Hoang Hoa Tham", "roadType": "Collector", "points": [(21.0455, 105.8100), (21.0420, 105.8205), (21.0390, 105.8310), (21.0365, 105.8420)]},
        {"id": "HN_CURATED_KIM_MA", "name": "Kim Ma", "roadType": "Arterial", "points": [(21.0320, 105.8100), (21.0300, 105.8200), (21.0280, 105.8300), (21.0260, 105.8400)]},
        {"id": "HN_CURATED_NGUYEN_CHI_THANH", "name": "Nguyen Chi Thanh", "roadType": "Arterial", "points": [(21.0230, 105.8100), (21.0210, 105.8180), (21.0195, 105.8260), (21.0185, 105.8340)]},
        {"id": "HN_CURATED_LE_VAN_LUONG", "name": "Le Van Luong", "roadType": "Arterial", "points": [(21.0142, 105.7939), (21.0068, 105.8030), (21.0005, 105.8120), (20.9960, 105.8210)]},
        {"id": "HN_CURATED_DAI_CO_VIET", "name": "Dai Co Viet", "roadType": "Arterial", "points": [(21.0062, 105.8460), (21.0040, 105.8385), (21.0030, 105.8310), (21.0036, 105.8270)]},
        {"id": "HN_CURATED_MINH_KHAI", "name": "Minh Khai", "roadType": "Arterial", "points": [(21.0000, 105.8830), (20.9970, 105.8710), (20.9950, 105.8580), (20.9940, 105.8424)]},
        {"id": "HN_CURATED_BACH_MAI", "name": "Bach Mai", "roadType": "Collector", "points": [(21.0040, 105.8490), (20.9975, 105.8480), (20.9905, 105.8460), (20.9840, 105.8440)]},
        {"id": "HN_CURATED_PHO_HUE", "name": "Pho Hue", "roadType": "Collector", "points": [(21.0200, 105.8520), (21.0140, 105.8500), (21.0080, 105.8480), (21.0040, 105.8460)]},
        {"id": "HN_CURATED_BA_TRIEU", "name": "Ba Trieu", "roadType": "Collector", "points": [(21.0260, 105.8525), (21.0200, 105.8520), (21.0140, 105.8510), (21.0080, 105.8490)]},
        {"id": "HN_CURATED_NGUYEN_VAN_CU", "name": "Nguyen Van Cu", "roadType": "Arterial", "points": [(21.0397, 105.8847), (21.0300, 105.8870), (21.0180, 105.8900), (21.0005, 105.8917)]},
        {"id": "HN_CURATED_CHUONG_DUONG", "name": "Chuong Duong bridge corridor", "roadType": "Highway", "points": [(21.0320, 105.8550), (21.0350, 105.8700), (21.0397, 105.8847), (21.0450, 105.8950)]},
        {"id": "HN_CURATED_THANH_TRI", "name": "Thanh Tri bridge corridor", "roadType": "Highway", "points": [(20.9730, 105.8400), (20.9760, 105.8650), (20.9785, 105.8900), (20.9820, 105.9150)]},
        {"id": "HN_CURATED_VO_CHI_CONG", "name": "Vo Chi Cong", "roadType": "Highway", "points": [(21.0280, 105.7800), (21.0430, 105.7820), (21.0521, 105.7852), (21.0600, 105.8100)]},
        {"id": "HN_CURATED_LAC_LONG_QUAN", "name": "Lac Long Quan", "roadType": "Arterial", "points": [(21.0730, 105.8100), (21.0645, 105.8200), (21.0524, 105.8373), (21.0450, 105.8500)]},
        {"id": "HN_CURATED_AU_CO", "name": "Au Co", "roadType": "Arterial", "points": [(21.0700, 105.8400), (21.0600, 105.8450), (21.0500, 105.8500), (21.0397, 105.8847)]},
        {"id": "HN_CURATED_HANG_BAI", "name": "Hang Bai", "roadType": "Collector", "points": [(21.0260, 105.8535), (21.0225, 105.8538), (21.0188, 105.8542), (21.0148, 105.8544)]},
        {"id": "HN_CURATED_DINH_TIEN_HOANG", "name": "Dinh Tien Hoang", "roadType": "Collector", "points": [(21.0315, 105.8520), (21.0288, 105.8536), (21.0256, 105.8545), (21.0225, 105.8540)]},
        {"id": "HN_CURATED_TRAN_QUANG_KHAI", "name": "Tran Quang Khai", "roadType": "Arterial", "points": [(21.0397, 105.8847), (21.0340, 105.8710), (21.0290, 105.8620), (21.0235, 105.8580)]},
        {"id": "HN_CURATED_TRAN_NHAT_DUAT", "name": "Tran Nhat Duat", "roadType": "Arterial", "points": [(21.0435, 105.8585), (21.0397, 105.8847), (21.0340, 105.8710), (21.0290, 105.8620)]},
        {"id": "HN_CURATED_LY_THUONG_KIET", "name": "Ly Thuong Kiet", "roadType": "Collector", "points": [(21.0260, 105.8420), (21.0248, 105.8480), (21.0238, 105.8540), (21.0228, 105.8600)]},
        {"id": "HN_CURATED_HAI_BA_TRUNG", "name": "Hai Ba Trung", "roadType": "Collector", "points": [(21.0228, 105.8420), (21.0218, 105.8485), (21.0208, 105.8550), (21.0198, 105.8615)]},
        {"id": "HN_CURATED_TRAN_HUNG_DAO", "name": "Tran Hung Dao", "roadType": "Collector", "points": [(21.0208, 105.8400), (21.0198, 105.8480), (21.0188, 105.8560), (21.0178, 105.8640)]},
        {"id": "HN_CURATED_LE_DUAN", "name": "Le Duan", "roadType": "Arterial", "points": [(21.0290, 105.8410), (21.0210, 105.8420), (21.0120, 105.8430), (21.0040, 105.8440)]},
        {"id": "HN_CURATED_GIANG_VO", "name": "Giang Vo", "roadType": "Collector", "points": [(21.0300, 105.8120), (21.0280, 105.8220), (21.0260, 105.8320), (21.0240, 105.8420)]},
        {"id": "HN_CURATED_DE_LA_THANH", "name": "De La Thanh", "roadType": "Collector", "points": [(21.0200, 105.8060), (21.0175, 105.8160), (21.0145, 105.8260), (21.0120, 105.8360)]},
        {"id": "HN_CURATED_O_CHO_DUA", "name": "O Cho Dua", "roadType": "Collector", "points": [(21.0160, 105.8230), (21.0120, 105.8270), (21.0080, 105.8310), (21.0040, 105.8350)]},
        {"id": "HN_CURATED_NGUYEN_KHOAI", "name": "Nguyen Khoai", "roadType": "Collector", "points": [(21.0020, 105.8610), (20.9960, 105.8640), (20.9900, 105.8670), (20.9840, 105.8700)]},
    ]
)

CURATED_LIVE_MAP_ROADS["hcmc"].extend(
    [
        {"id": "HCM_CURATED_TRUONG_CHINH", "name": "Truong Chinh", "roadType": "Arterial", "points": [(10.8230, 106.6280), (10.8120, 106.6460), (10.8012, 106.6525), (10.7904, 106.6975)]},
        {"id": "HCM_CURATED_NAM_KY", "name": "Nam Ky Khoi Nghia", "roadType": "Arterial", "points": [(10.7920, 106.6880), (10.7840, 106.6940), (10.7769, 106.7009), (10.7680, 106.7070)]},
        {"id": "HCM_CURATED_NTMK", "name": "Nguyen Thi Minh Khai", "roadType": "Collector", "points": [(10.7825, 106.6860), (10.7815, 106.6960), (10.7805, 106.7060), (10.7790, 106.7160)]},
        {"id": "HCM_CURATED_XO_VIET", "name": "Xo Viet Nghe Tinh", "roadType": "Arterial", "points": [(10.7904, 106.6975), (10.7980, 106.7060), (10.8080, 106.7160), (10.8200, 106.7250)]},
        {"id": "HCM_CURATED_HANOI_HIGHWAY", "name": "Hanoi Highway", "roadType": "Highway", "points": [(10.8015, 106.7148), (10.8200, 106.7400), (10.8420, 106.7700), (10.8621, 106.7948)]},
        {"id": "HCM_CURATED_NGUYEN_HUU_THO", "name": "Nguyen Huu Tho", "roadType": "Arterial", "points": [(10.7298, 106.7014), (10.7420, 106.7040), (10.7560, 106.7080), (10.7680, 106.7120)]},
        {"id": "HCM_CURATED_NGUYEN_TAT_THANH", "name": "Nguyen Tat Thanh", "roadType": "Arterial", "points": [(10.7560, 106.7040), (10.7640, 106.7120), (10.7720, 106.7200), (10.7810, 106.7350)]},
        {"id": "HCM_CURATED_VO_NGUYEN_GIAP", "name": "Vo Nguyen Giap", "roadType": "Highway", "points": [(10.7901, 106.7197), (10.8020, 106.7480), (10.8230, 106.7780), (10.8621, 106.7948)]},
        {"id": "HCM_CURATED_NGUYEN_VAN_CU", "name": "Nguyen Van Cu", "roadType": "Arterial", "points": [(10.7650, 106.6750), (10.7600, 106.6860), (10.7556, 106.6950), (10.7500, 106.7050)]},
        {"id": "HCM_CURATED_LE_VAN_SY", "name": "Le Van Sy", "roadType": "Collector", "points": [(10.7980, 106.6600), (10.7900, 106.6700), (10.7820, 106.6800), (10.7740, 106.6900)]},
        {"id": "HCM_CURATED_HOANG_VAN_THU", "name": "Hoang Van Thu", "roadType": "Arterial", "points": [(10.8012, 106.6525), (10.7980, 106.6650), (10.7940, 106.6780), (10.7904, 106.6975)]},
        {"id": "HCM_CURATED_PASTEUR", "name": "Pasteur", "roadType": "Collector", "points": [(10.7900, 106.6900), (10.7840, 106.6950), (10.7780, 106.7000), (10.7700, 106.7060)]},
        {"id": "HCM_CURATED_HAI_BA_TRUNG", "name": "Hai Ba Trung", "roadType": "Collector", "points": [(10.7920, 106.7000), (10.7860, 106.7040), (10.7800, 106.7080), (10.7740, 106.7120)]},
        {"id": "HCM_CURATED_LE_DUAN", "name": "Le Duan", "roadType": "Collector", "points": [(10.7790, 106.6960), (10.7830, 106.7000), (10.7870, 106.7040), (10.7901, 106.7197)]},
        {"id": "HCM_CURATED_DONG_KHOI", "name": "Dong Khoi", "roadType": "Collector", "points": [(10.7790, 106.7030), (10.7755, 106.7045), (10.7720, 106.7060), (10.7685, 106.7075)]},
        {"id": "HCM_CURATED_NGUYEN_HUE", "name": "Nguyen Hue", "roadType": "Collector", "points": [(10.7769, 106.7009), (10.7740, 106.7025), (10.7715, 106.7040), (10.7688, 106.7055)]},
        {"id": "HCM_CURATED_LE_LOI", "name": "Le Loi", "roadType": "Collector", "points": [(10.7728, 106.6960), (10.7740, 106.7010), (10.7752, 106.7060), (10.7765, 106.7110)]},
        {"id": "HCM_CURATED_HAM_NGHI", "name": "Ham Nghi", "roadType": "Collector", "points": [(10.7700, 106.6965), (10.7712, 106.7015), (10.7724, 106.7065), (10.7735, 106.7115)]},
        {"id": "HCM_CURATED_TRAN_HUNG_DAO", "name": "Tran Hung Dao", "roadType": "Arterial", "points": [(10.7550, 106.6750), (10.7600, 106.6860), (10.7650, 106.6960), (10.7700, 106.7060)]},
        {"id": "HCM_CURATED_VO_THI_SAU", "name": "Vo Thi Sau", "roadType": "Collector", "points": [(10.7860, 106.6800), (10.7840, 106.6900), (10.7820, 106.7000), (10.7800, 106.7100)]},
        {"id": "HCM_CURATED_DIEN_BIEN_PHU_CORE", "name": "Dien Bien Phu core", "roadType": "Arterial", "points": [(10.7820, 106.6860), (10.7860, 106.6960), (10.7904, 106.6975), (10.8015, 106.7148)]},
        {"id": "HCM_CURATED_NGUYEN_DINH_CHIEU", "name": "Nguyen Dinh Chieu", "roadType": "Collector", "points": [(10.7820, 106.6750), (10.7810, 106.6860), (10.7800, 106.6970), (10.7790, 106.7080)]},
        {"id": "HCM_CURATED_3_THANG_2", "name": "3 Thang 2", "roadType": "Arterial", "points": [(10.7760, 106.6600), (10.7745, 106.6720), (10.7730, 106.6840), (10.7715, 106.6960)]},
        {"id": "HCM_CURATED_LY_THUONG_KIET", "name": "Ly Thuong Kiet", "roadType": "Arterial", "points": [(10.7800, 106.6500), (10.7785, 106.6620), (10.7770, 106.6740), (10.7755, 106.6860)]},
        {"id": "HCM_CURATED_BA_THANG_HAI", "name": "Ba Thang Hai", "roadType": "Arterial", "points": [(10.7760, 106.6500), (10.7745, 106.6640), (10.7730, 106.6780), (10.7715, 106.6920)]},
        {"id": "HCM_CURATED_TON_DUC_THANG", "name": "Ton Duc Thang", "roadType": "Collector", "points": [(10.7901, 106.7197), (10.7840, 106.7140), (10.7780, 106.7080), (10.7720, 106.7040)]},
    ]
)


def _geometry_coordinates(row) -> list[list[float]]:
    geometry = getattr(row, "geometry", None)
    if isinstance(geometry, str) and geometry:
        try:
            geometry = json.loads(geometry)
        except json.JSONDecodeError:
            try:
                geometry = ast.literal_eval(geometry)
            except (ValueError, SyntaxError):
                geometry = None
    if isinstance(geometry, dict):
        coords = geometry.get("coordinates") or []
        normalized = []
        for point in coords:
            if isinstance(point, dict):
                lat = point.get("latitude")
                lon = point.get("longitude")
                if lat is not None and lon is not None:
                    normalized.append([float(lon), float(lat)])
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                normalized.append([float(point[0]), float(point[1])])
        if len(normalized) >= 2:
            return normalized
    return synthetic_geojson_line(float(row.lat), float(row.lon))


def _real_geometry_coordinates(row) -> list[list[float]] | None:
    geometry = getattr(row, "geometry", None)
    if isinstance(geometry, str) and geometry:
        try:
            geometry = json.loads(geometry)
        except json.JSONDecodeError:
            try:
                geometry = ast.literal_eval(geometry)
            except (ValueError, SyntaxError):
                geometry = None
    if not isinstance(geometry, dict):
        return None
    coords = geometry.get("coordinates") or []
    normalized = []
    for point in coords:
        try:
            if isinstance(point, dict):
                lat = point.get("latitude")
                lon = point.get("longitude")
                if lat is not None and lon is not None:
                    normalized.append([float(lon), float(lat)])
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                lon = float(point[0])
                lat = float(point[1])
                if -180 <= lon <= 180 and -90 <= lat <= 90:
                    normalized.append([lon, lat])
        except (TypeError, ValueError):
            continue
    return normalized if len(normalized) >= 2 else None


def _congestion_from_speed(current_speed: float, free_flow_speed: float) -> tuple[float, str]:
    ratio = current_speed / free_flow_speed if free_flow_speed > 0 else 0.0
    if ratio >= 0.75:
        return ratio, "Free"
    if ratio >= 0.5:
        return ratio, "Slow"
    if ratio >= 0.3:
        return ratio, "Congested"
    return ratio, "Severe"


def _delay_minutes(speed_ratio: float, jam_factor: float) -> int:
    return max(0, round((1.0 - max(0.0, min(speed_ratio, 1.0))) * 18 + jam_factor * 0.6))


def _coords_from_latlon(points: list[tuple[float, float]]) -> list[list[float]]:
    return [[lon, lat] for lat, lon in points]


def _stable_hash(value: str) -> int:
    total = 0
    for char in value:
        total = (total * 31 + ord(char)) % 1_000_003
    return total


def _road_priority(road_type: str, name: str = "") -> int:
    normalized = road_type.lower()
    road_name = name.lower()
    if normalized == "highway" or "bridge" in road_name or "vanh dai" in road_name or "highway" in road_name:
        return 1
    if normalized == "arterial":
        return 2
    if normalized == "collector":
        return 3
    return 4


def _haversine_km(start: tuple[float, float], end: tuple[float, float]) -> float:
    lat1, lon1 = start
    lat2, lon2 = end
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _road_segment_chunks(points: list[tuple[float, float]], road_type: str, zoom: int) -> list[list[list[float]]]:
    target_km = 1.2 if zoom <= 12 else 0.85 if zoom <= 14 else 0.55
    if road_type == "Highway":
        target_km *= 1.25
    elif road_type == "Collector":
        target_km *= 0.85

    chunks: list[list[list[float]]] = []
    for start, end in zip(points, points[1:]):
        distance = _haversine_km(start, end)
        count = max(1, min(6, math.ceil(distance / target_km)))
        start_lat, start_lon = start
        end_lat, end_lon = end
        for idx in range(count):
            a = idx / count
            b = (idx + 1) / count
            lat1 = start_lat + (end_lat - start_lat) * a
            lon1 = start_lon + (end_lon - start_lon) * a
            lat2 = start_lat + (end_lat - start_lat) * b
            lon2 = start_lon + (end_lon - start_lon) * b
            chunks.append([[lon1, lat1], [lon2, lat2]])
    return chunks


def _curated_status(road_id: str, road_type: str, segment_idx: int) -> tuple[float, float, float]:
    is_peak = datetime.now().hour in {7, 8, 9, 16, 17, 18, 19}
    levels = (
        ["Free", "Free", "Free", "Slow", "Slow", "Slow", "Congested", "Congested", "Severe", "Free"]
        if is_peak
        else ["Free", "Free", "Free", "Free", "Slow", "Slow", "Slow", "Congested", "Congested", "Severe"]
    )
    level = levels[(_stable_hash(road_id) + segment_idx * 7) % len(levels)]
    free_flow = 65.0 if road_type == "Highway" else 48.0 if road_type == "Arterial" else 36.0
    ratio_by_level = {"Free": 0.82, "Slow": 0.62, "Congested": 0.42, "Severe": 0.25}
    jam_by_level = {"Free": 2.0, "Slow": 4.3, "Congested": 7.0, "Severe": 9.1}
    ratio = ratio_by_level[level]
    jitter = ((_stable_hash(f"{road_id}-{segment_idx}") % 9) - 4) * 0.01
    return max(5.0, free_flow * max(0.15, ratio + jitter)), free_flow, jam_by_level[level]


def _inside_bbox(coordinates: list[list[float]], bbox: tuple[float, float, float, float] | None) -> bool:
    if bbox is None:
        return True
    min_lon, min_lat, max_lon, max_lat = bbox
    return any(min_lon <= lon <= max_lon and min_lat <= lat <= max_lat for lon, lat in coordinates)


def _parse_bbox(raw_bbox: str | None) -> tuple[float, float, float, float] | None:
    if not raw_bbox:
        return None
    try:
        min_lon, min_lat, max_lon, max_lat = [float(part) for part in raw_bbox.split(",")]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="bbox must be minLon,minLat,maxLon,maxLat") from exc
    if min_lon >= max_lon or min_lat >= max_lat:
        raise HTTPException(status_code=422, detail="bbox min values must be lower than max values")
    return min_lon, min_lat, max_lon, max_lat


def _live_map_segment(
    *,
    segment_id: str,
    name: str,
    city: str,
    road_type: str,
    coordinates: list[list[float]],
    current_speed: float,
    free_flow_speed: float,
    jam_factor: float,
    source: str,
    provider: str = "local",
    latest_timestamp: str = "",
    confidence: float = 1.0,
) -> LiveMapSegment:
    speed_ratio, level = _congestion_from_speed(current_speed, free_flow_speed)
    return LiveMapSegment(
        id=segment_id,
        name=name,
        city=city,
        roadType=road_type,
        geometry={"type": "LineString", "coordinates": coordinates},
        currentSpeed=round(current_speed, 2),
        freeFlowSpeed=round(free_flow_speed, 2),
        speedRatio=round(speed_ratio, 3),
        jamFactor=round(jam_factor, 2),
        congestionLevel=level,
        travelTimeDelayMin=_delay_minutes(speed_ratio, jam_factor),
        source=source,
        provider=provider,
        latestTimestamp=latest_timestamp,
        confidence=round(confidence, 3),
    )


def _curated_live_map_segments(
    city: str,
    latest,
    bbox: tuple[float, float, float, float] | None,
    *,
    zoom: int = 13,
    density: str = "medium",
) -> list[LiveMapSegment]:
    candidates: list[tuple[int, int, LiveMapSegment]] = []
    allowed_priority = 2 if zoom <= 11 else 3 if zoom <= 13 else 4
    if density == "low":
        allowed_priority = min(allowed_priority, 2)
    elif density == "high" and zoom >= 13:
        allowed_priority = 4

    roads = sorted(
        CURATED_LIVE_MAP_ROADS.get(city, []),
        key=lambda road: (_road_priority(str(road["roadType"]), str(road["name"])), str(road["name"])),
    )
    for road in roads:
        road_type = str(road["roadType"])
        priority = _road_priority(road_type, str(road["name"]))
        if priority > allowed_priority:
            continue
        for segment_idx, coordinates in enumerate(_road_segment_chunks(road["points"], road_type, zoom), start=1):
            if not _inside_bbox(coordinates, bbox):
                continue
            current_speed, free_flow_speed, jam_factor = _curated_status(str(road["id"]), road_type, segment_idx)
            candidates.append(
                (
                    priority,
                    segment_idx,
                    _live_map_segment(
                    segment_id=f"{road['id']}_{segment_idx:03d}",
                    name=str(road["name"]),
                    city=city,
                    road_type=road_type,
                    coordinates=coordinates,
                    current_speed=current_speed,
                    free_flow_speed=free_flow_speed,
                    jam_factor=jam_factor,
                    source="curated_demo",
                    provider="manual_road_geometry",
                    ),
                )
            )
    if (density == "high" and zoom >= 14) or (density == "medium" and zoom >= 13):
        groups: dict[int, list[tuple[int, LiveMapSegment]]] = {}
        for priority, segment_idx, segment in candidates:
            groups.setdefault(priority, []).append((segment_idx, segment))
        for group in groups.values():
            group.sort(key=lambda item: item[0])
        ordered: list[LiveMapSegment] = []
        priority_cycle = (1, 2, 2, 3, 4) if density == "high" else (1, 2, 2, 3)
        while any(groups.values()):
            for priority in priority_cycle:
                group = groups.get(priority)
                if group:
                    ordered.append(group.pop(0)[1])
        return ordered
    return [segment for _, _, segment in sorted(candidates, key=lambda item: (item[0], item[1], item[2].name))]


def _line_chunks(points: list[tuple[float, float]], chunks_per_leg: int = 6) -> list[list[list[float]]]:
    chunks: list[list[list[float]]] = []
    for start, end in zip(points, points[1:]):
        start_lat, start_lon = start
        end_lat, end_lon = end
        for idx in range(chunks_per_leg):
            a = idx / chunks_per_leg
            b = (idx + 1) / chunks_per_leg
            lat1 = start_lat + (end_lat - start_lat) * a
            lon1 = start_lon + (end_lon - start_lon) * a
            lat2 = start_lat + (end_lat - start_lat) * b
            lon2 = start_lon + (end_lon - start_lon) * b
            chunks.append([[lon1, lat1], [lon2, lat2]])
    return chunks


def _status_template(latest, idx: int) -> tuple[float, float, float]:
    if latest.empty:
        return 35.0, 45.0, 2.0
    row = latest.iloc[idx % len(latest)]
    current = float(row.get("currentSpeed", 35.0))
    free_flow = float(row.get("freeFlowSpeed", max(current, 45.0)))
    jam = float(row.get("jamFactor", 2.0))
    return current, free_flow, jam


def _demo_coverage_features(city: str, existing_ids: set[str], latest) -> list[dict]:
    target = DEMO_COVERAGE_TARGETS.get(city, 0)
    needed = max(0, target - len(existing_ids))
    if needed <= 0:
        return []

    features: list[dict] = []
    corridors = DEMO_CORRIDORS.get(city, [])
    for corridor_idx, corridor in enumerate(corridors, start=1):
        for chunk_idx, coordinates in enumerate(_line_chunks(corridor["points"]), start=1):
            if len(features) >= needed:
                return features
            segment_id = f"{city.upper()}_DEMO_{corridor_idx:02d}_{chunk_idx:02d}"
            if segment_id in existing_ids:
                continue
            current, free_flow, jam = _status_template(latest, len(features))
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coordinates},
                    "properties": {
                        "segment_id": segment_id,
                        "jam_factor": round(jam, 2),
                        "current_speed": round(current, 2),
                        "free_flow_speed": round(free_flow, 2),
                        "city": city,
                        "coverage_source": "demo_coverage_interpolated",
                        "is_demo_coverage": True,
                        "segment_name": corridor["name"],
                        "road_type": "Highway" if "Connector" in corridor["name"] or "Ring" in corridor["name"] else "Arterial",
                    },
                }
            )
    for grid_idx, grid in enumerate(DEMO_LOCAL_GRIDS.get(city, []), start=1):
        min_lat, max_lat, min_lon, max_lon = grid["bounds"]
        lat_steps = max(2, int(grid["lat_lines"]))
        lon_steps = max(2, int(grid["lon_lines"]))
        lines: list[list[list[float]]] = []
        for idx in range(lat_steps):
            lat = min_lat + (max_lat - min_lat) * idx / (lat_steps - 1)
            lines.append([[min_lon, lat], [max_lon, lat]])
        for idx in range(lon_steps):
            lon = min_lon + (max_lon - min_lon) * idx / (lon_steps - 1)
            lines.append([[lon, min_lat], [lon, max_lat]])
        for line_idx, coordinates in enumerate(lines, start=1):
            if len(features) >= needed:
                return features
            segment_id = f"{city.upper()}_LOCAL_{grid_idx:02d}_{line_idx:02d}"
            if segment_id in existing_ids:
                continue
            current, free_flow, jam = _status_template(latest, len(features))
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coordinates},
                    "properties": {
                        "segment_id": segment_id,
                        "jam_factor": round(jam, 2),
                        "current_speed": round(current, 2),
                        "free_flow_speed": round(free_flow, 2),
                        "city": city,
                        "coverage_source": "demo_local_road_grid",
                        "is_demo_coverage": True,
                        "segment_name": grid["name"],
                        "road_type": "Local",
                    },
                }
            )
    if len(features) < needed and city in DEMO_CITY_MESH_BOUNDS:
        min_lat, max_lat, min_lon, max_lon = DEMO_CITY_MESH_BOUNDS[city]
        mesh_idx = 1
        lat_lines = 18 if city == "hanoi" else 16
        lon_lines = 22 if city == "hanoi" else 18
        mesh_lines: list[list[list[float]]] = []
        for idx in range(lat_lines):
            lat = min_lat + (max_lat - min_lat) * idx / (lat_lines - 1)
            mesh_lines.append([[min_lon, lat], [max_lon, lat]])
        for idx in range(lon_lines):
            lon = min_lon + (max_lon - min_lon) * idx / (lon_lines - 1)
            mesh_lines.append([[lon, min_lat], [lon, max_lat]])
        while len(features) < needed:
            for coordinates in mesh_lines:
                if len(features) >= needed:
                    break
                current, free_flow, jam = _status_template(latest, len(features))
                lane_offset = (mesh_idx % 9 - 4) * 0.0012
                shifted = [[lon + lane_offset, lat - lane_offset] for lon, lat in coordinates]
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": shifted},
                        "properties": {
                            "segment_id": f"{city.upper()}_MESH_{mesh_idx:03d}",
                            "jam_factor": round(jam, 2),
                            "current_speed": round(current, 2),
                            "free_flow_speed": round(free_flow, 2),
                            "city": city,
                            "coverage_source": "demo_citywide_local_mesh",
                            "is_demo_coverage": True,
                            "segment_name": "Citywide local road mesh",
                            "road_type": "Local",
                        },
                    }
                )
                mesh_idx += 1
    return features


def _geojson_for_city(city: str, include_demo_coverage: bool, latest_all) -> list[dict]:
    latest = latest_by_segment(latest_all, city)
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": _geometry_coordinates(row),
            },
            "properties": {
                "segment_id": str(row.segment_id),
                "jam_factor": round(float(row.jamFactor), 2),
                "current_speed": round(float(row.currentSpeed), 2),
                "free_flow_speed": round(float(row.freeFlowSpeed), 2),
                "city": str(row.city),
                "coverage_source": "local_gold",
                "is_demo_coverage": False,
                "segment_name": str(getattr(row, "segment_name", row.segment_id)),
                "source": str(getattr(row, "source", "unknown")),
                "provider": str(getattr(row, "provider", "unknown")),
                "latest_timestamp": str(getattr(row, "timestamp", "")),
                "confidence": round(float(getattr(row, "confidence", 1.0)), 3)
                if getattr(row, "confidence", None) == getattr(row, "confidence", None)
                else 1.0,
                "road_type": "Arterial",
            },
        }
        for row in latest.head(250).itertuples(index=False)
    ]
    if include_demo_coverage:
        existing_ids = {str(feature["properties"]["segment_id"]) for feature in features}
        features.extend(_demo_coverage_features(city, existing_ids, latest))
    return features


@router.get("/geojson", response_model=SegmentGeoJSON)
def get_segments_geojson(
    city: str = Query("hanoi", description="City code"),
    include_demo_coverage: bool = Query(False, description="Add clearly marked interpolated demo coverage lines"),
):
    """Get segments as GeoJSON for Leaflet map rendering.

    Args:
        city: City code

    Returns:
        GeoJSON FeatureCollection with segment polylines
    """
    city = normalize_city(city)
    try:
        all_features = traffic_features()
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if city == "all":
        features = []
        for city_code in ("hanoi", "hcmc"):
            features.extend(_geojson_for_city(city_code, include_demo_coverage, all_features))
    else:
        features = _geojson_for_city(city or "hanoi", include_demo_coverage, all_features)

    return SegmentGeoJSON(features=features)


@router.get("/live-map", response_model=LiveMapSegmentsResponse)
def get_live_map_segments(
    city: str = Query("hanoi", description="City code: hanoi, hcmc, or all"),
    bbox: Optional[str] = Query(None, description="Optional viewport bbox as minLon,minLat,maxLon,maxLat"),
    limit: int = Query(120, ge=1, le=250, description="Maximum visible road segments"),
    density: str = Query("medium", pattern="^(low|medium|high)$", description="Coverage density"),
    zoom: int = Query(13, ge=5, le=20, description="Leaflet zoom level for road hierarchy filtering"),
):
    """Get clean road-level segments for Live Map rendering.

    This endpoint intentionally does not use generated grids, city meshes, or
    interpolated coverage lines. It returns real stored LineString geometry when
    available and falls back only to a small curated road-corridor set.
    """
    city = normalize_city(city)
    parsed_bbox = _parse_bbox(bbox)
    try:
        all_features = traffic_features()
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    city_codes = ("hanoi", "hcmc") if city == "all" else (city or "hanoi",)
    segments: list[LiveMapSegment] = []
    for city_code in city_codes:
        latest = latest_by_segment(all_features, city_code)
        real_segments: list[LiveMapSegment] = []
        for row in latest.itertuples(index=False):
            coordinates = _real_geometry_coordinates(row)
            if not coordinates or not _inside_bbox(coordinates, parsed_bbox):
                continue
            current_speed = float(getattr(row, "currentSpeed", 0.0))
            free_flow_speed = float(getattr(row, "freeFlowSpeed", max(current_speed, 1.0)))
            real_segments.append(
                _live_map_segment(
                    segment_id=str(row.segment_id),
                    name=str(getattr(row, "segment_name", row.segment_id)),
                    city=str(getattr(row, "city", city_code)),
                    road_type=str(getattr(row, "road_type", "Arterial") or "Arterial").title(),
                    coordinates=coordinates,
                    current_speed=current_speed,
                    free_flow_speed=free_flow_speed,
                    jam_factor=float(getattr(row, "jamFactor", 0.0)),
                    source=str(getattr(row, "source", "local_gold") or "local_gold"),
                    provider=str(getattr(row, "provider", "local") or "local"),
                    latest_timestamp=str(getattr(row, "timestamp", "")),
                    confidence=float(getattr(row, "confidence", 1.0))
                    if getattr(row, "confidence", None) == getattr(row, "confidence", None)
                    else 1.0,
                )
            )

        segments.extend(real_segments[:limit])
        existing_ids = {segment.id for segment in segments}
        for curated in _curated_live_map_segments(city_code, latest, parsed_bbox, zoom=zoom, density=density):
            if curated.id not in existing_ids:
                segments.append(curated)
                existing_ids.add(curated.id)
            if len(segments) >= limit:
                break

    return LiveMapSegmentsResponse(segments=segments[:limit])


@router.get("/{segment_id}", response_model=Segment)
def get_segment_details(segment_id: str):
    """Get detailed information for a segment.

    Args:
        segment_id: Segment ID

    Returns:
        Segment details
    """
    try:
        latest = latest_by_segment(traffic_features())
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    rows = latest[latest["segment_id"].astype(str) == segment_id]
    if rows.empty:
        raise HTTPException(status_code=404, detail=f"Segment '{segment_id}' was not found in local data")
    row = rows.iloc[0]
    return Segment(
        segment_id=segment_id,
        city=str(row.get("city", "unknown")),
        road_class=str(row.get("road_class_encoded", "unknown")),
        district=str(row.get("district", "unknown")),
        length_m=float(row.get("length_m", 0.0)),
        speed_limit=int(row.get("speed_limit_encoded", 0)),
        lat=float(row.get("lat", 0.0)),
        lon=float(row.get("lon", 0.0)),
        timestamp=row["timestamp"].to_pydatetime(),
    )


@router.get("/{segment_id}/upstream")
def get_upstream_sensors(segment_id: str):
    """Get upstream sensor chain for Live Corridor Tracking.

    Args:
        segment_id: Segment ID

    Returns:
        List of upstream segments feeding into this one
    """
    try:
        latest = latest_by_segment(traffic_features())
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    rows = latest.sort_values("jamFactor", ascending=False).head(4)
    chain = []
    for row in rows.itertuples(index=False):
        speed = float(row.currentSpeed)
        status = "congested" if float(row.jamFactor) >= 6 else "slow" if float(row.jamFactor) >= 3 else "free"
        chain.append(
            {
                "id": str(row.segment_id),
                "segment_id": str(row.segment_id),
                "name": str(getattr(row, "segment_name", row.segment_id)),
                "road_class": str(getattr(row, "road_class_encoded", "unknown")),
                "speed_kmh": round(speed, 2),
                "current_speed": round(speed, 2),
                "status": status,
                "distance_m": (len(chain) + 1) * 500,
            }
        )

    return {
        "segment_id": segment_id,
        "updated_at": datetime.utcnow().isoformat(),
        "chain": chain,
        "upstream_segments": chain,
    }
