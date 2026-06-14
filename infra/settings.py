import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Settings:
    """Application configuration"""
    pass


BASE_DIR = Path(__file__).resolve().parent.parent

# Redis
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DEDUP_URL_TTL: int = 30 * 86400       # 30 ngày
DEDUP_GEOCODE_TTL: int = 30 * 86400

# Kafka
KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_EVENTS: str = os.getenv("KAFKA_TOPIC_EVENTS", "events.news")
SCHEMA_REGISTRY_URL: str = os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:8081")

# Nominatim (self-hosted)
NOMINATIM_URL: str = os.getenv("NOMINATIM_URL", "http://localhost:8080")
NOMINATIM_PUBLIC_URL: str = "https://nominatim.openstreetmap.org"
NOMINATIM_PUBLIC_RATE: float = 1.0    # req/s

# AWS S3 lakehouse
AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION: str = os.getenv("AWS_REGION", "ap-southeast-1")
S3_BUCKET: str = os.getenv("S3_BUCKET", "cognitive-traffic-lakehouse")
S3_WAREHOUSE: str = os.getenv("S3_WAREHOUSE", f"s3a://{S3_BUCKET}/warehouse")
S3_ENDPOINT: str = os.getenv("S3_ENDPOINT", "")

# MinIO / S3-compatible local fallback
MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET_BRONZE: str = "warehouse"
BRONZE_PREFIX: str = "bronze/events_raw"

# Neo4j AuraDB
NEO4J_URI: str = os.getenv("NEO4J_URI", "")
NEO4J_USERNAME: str = os.getenv("NEO4J_USERNAME", os.getenv("NEO4J_USER", "neo4j"))
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")

# Crawler
CRAWLER_USER_AGENT: str = (
    "NewsCrawlerBot/1.0 (Traffic Analytics Research; "
    "contact: woangchan5@gmail.com)"
)
DOMAIN_RATE_LIMIT: float = 1.5        # req/s per domain
HTTP_TIMEOUT: int = 15
HTTP_MAX_RETRIES: int = 3

# Sources config
SOURCES_YAML: Path = BASE_DIR / "sources.yaml"

# NLP
PHOBERT_CHECKPOINT: str = os.getenv("PHOBERT_CHECKPOINT", "")  # rỗng = dùng rule-based
PHOBERT_BASE_MODEL: str = "vinai/phobert-base"
NLP_MAX_LENGTH: int = 256

# Snap-to-road confidence thresholds (metres)
SNAP_HIGH_M: float = 50.0
SNAP_MID_M: float = 200.0
SNAP_CONF_HIGH: float = 1.0
SNAP_CONF_MID: float = 0.7
SNAP_CONF_LOW: float = 0.4

# Dedup
MINHASH_NUM_PERM: int = 128
MINHASH_THRESHOLD: float = 0.8
SIMHASH_WINDOW: int = 1000


# Create settings instance for easy import
class _SettingsInstance:
    """Settings singleton instance"""
    def __init__(self):
        self.REDIS_URL = REDIS_URL
        self.DEDUP_URL_TTL = DEDUP_URL_TTL
        self.DEDUP_GEOCODE_TTL = DEDUP_GEOCODE_TTL
        self.KAFKA_BOOTSTRAP_SERVERS = KAFKA_BOOTSTRAP_SERVERS
        self.KAFKA_TOPIC_EVENTS = KAFKA_TOPIC_EVENTS
        self.SCHEMA_REGISTRY_URL = SCHEMA_REGISTRY_URL
        self.NOMINATIM_URL = NOMINATIM_URL
        self.NOMINATIM_PUBLIC_URL = NOMINATIM_PUBLIC_URL
        self.NOMINATIM_PUBLIC_RATE = NOMINATIM_PUBLIC_RATE
        self.MINIO_ENDPOINT = MINIO_ENDPOINT
        self.MINIO_ACCESS_KEY = MINIO_ACCESS_KEY
        self.MINIO_SECRET_KEY = MINIO_SECRET_KEY
        self.MINIO_BUCKET_BRONZE = MINIO_BUCKET_BRONZE
        self.BRONZE_PREFIX = BRONZE_PREFIX
        self.AWS_ACCESS_KEY_ID = AWS_ACCESS_KEY_ID
        self.AWS_SECRET_ACCESS_KEY = AWS_SECRET_ACCESS_KEY
        self.AWS_REGION = AWS_REGION
        self.S3_BUCKET = S3_BUCKET
        self.S3_WAREHOUSE = S3_WAREHOUSE
        self.S3_ENDPOINT = S3_ENDPOINT
        self.NEO4J_URI = NEO4J_URI
        self.NEO4J_USERNAME = NEO4J_USERNAME
        self.NEO4J_PASSWORD = NEO4J_PASSWORD
        self.NEO4J_DATABASE = NEO4J_DATABASE
        self.CRAWLER_USER_AGENT = CRAWLER_USER_AGENT
        self.DOMAIN_RATE_LIMIT = DOMAIN_RATE_LIMIT
        self.HTTP_TIMEOUT = HTTP_TIMEOUT
        self.HTTP_MAX_RETRIES = HTTP_MAX_RETRIES
        self.SOURCES_YAML = SOURCES_YAML
        self.PHOBERT_CHECKPOINT = PHOBERT_CHECKPOINT
        self.PHOBERT_BASE_MODEL = PHOBERT_BASE_MODEL
        self.NLP_MAX_LENGTH = NLP_MAX_LENGTH
        self.SNAP_HIGH_M = SNAP_HIGH_M
        self.SNAP_MID_M = SNAP_MID_M
        self.SNAP_CONF_HIGH = SNAP_CONF_HIGH
        self.SNAP_CONF_MID = SNAP_CONF_MID
        self.SNAP_CONF_LOW = SNAP_CONF_LOW
        self.MINHASH_NUM_PERM = MINHASH_NUM_PERM
        self.MINHASH_THRESHOLD = MINHASH_THRESHOLD
        self.SIMHASH_WINDOW = SIMHASH_WINDOW


# Export settings instance
settings = _SettingsInstance()
