"""Constants for freedomCam."""
from __future__ import annotations

from dataclasses import dataclass

DOMAIN = "freedomcam"
FORMAT_VERSION = 1

# Config entry (storage)
CONF_PROVIDER = "provider"
CONF_ACCOUNT_ID = "account_id"
CONF_JURISDICTION = "jurisdiction"
CONF_ENDPOINT = "endpoint"
CONF_REGION = "region"
CONF_BUCKET = "bucket"
CONF_ACCESS_KEY = "access_key_id"
CONF_SECRET_KEY = "secret_access_key"
CONF_VIRTUAL_HOST = "virtual_host"
CONF_RETENTION_DAYS = "retention_days"
CONF_MANAGE_LIFECYCLE = "manage_lifecycle"

# Options
CONF_PRESENCE_ENTITY = "presence_entity"
CONF_PAUSE = "pause_seconds"
CONF_MAX_PER_HOUR = "max_per_hour"
CONF_SENSITIVITY = "sensitivity"
CONF_THUMBNAILS = "thumbnails"
CONF_AI_PROVIDER = "ai_provider"
CONF_AI_ACCOUNT_ID = "ai_account_id"
CONF_AI_TOKEN = "ai_token"
CONF_AI_MIN_SCORE = "ai_min_score"
CONF_APP_ACCESS_KEY = "app_access_key_id"
CONF_APP_SECRET_KEY = "app_secret_access_key"

# Camera subentry
SUBENTRY_CAMERA = "camera"
CONF_CAMERA_ENTITY = "camera_entity"
CONF_CAMERA_ID = "camera_id"
CONF_NAME = "name"
CONF_KIND = "kind"
CONF_MODE = "mode"
CONF_MOTION_ENTITY = "motion_entity"
CONF_INTERVAL = "interval_seconds"
CONF_ONLY_WHEN_AWAY = "only_when_away"

KIND_INDOOR, KIND_OUTDOOR = "indoor", "outdoor"
MODE_IMAGE, MODE_SENSOR = "image", "sensor"
AI_NONE, AI_CLOUDFLARE = "none", "cloudflare"

DEFAULT_PAUSE = 30
DEFAULT_MAX_PER_HOUR = 60
DEFAULT_INTERVAL = 10
DEFAULT_RETENTION = 30
DEFAULT_AI_MIN_SCORE = 0.7
SENSITIVITIES = {"low": 0.03, "medium": 0.01, "high": 0.005}   # fraction of changed pixels
DEFAULT_SENSITIVITY = "medium"

# States of the presence entity that mean "nobody at home"
AWAY_STATES = ("off", "not_home", "away", "0")

MANIFEST_KEY = "freedomcam.json"
THUMB_WIDTH = 320
INDEX_FLUSH_SECONDS = 60

LABELS = ("person", "car", "motorcycle", "bicycle", "dog", "cat")
INDOOR_LABELS = ("person", "dog", "cat")
VEHICLE_LABELS = ("car", "motorcycle", "bicycle")


@dataclass(frozen=True)
class Provider:
    """How to reach one storage provider."""

    key: str
    endpoint: str              # "{account}", "{region}" and "{jurisdiction}" are filled in
    region: str | None = None  # fixed region, or None = asked to the user
    virtual_host: bool = False
    default_region: str = ""
    help_url: str = ""


PROVIDERS: dict[str, Provider] = {
    "cloudflare_r2": Provider("cloudflare_r2", "https://{account}{jurisdiction}.r2.cloudflarestorage.com",
                              region="auto",
                              help_url="https://developers.cloudflare.com/r2/api/tokens/"),
    "aws_s3": Provider("aws_s3", "https://s3.{region}.amazonaws.com", virtual_host=True,
                       default_region="eu-west-1",
                       help_url="https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html"),
    "backblaze_b2": Provider("backblaze_b2", "https://s3.{region}.backblazeb2.com",
                             default_region="eu-central-003",
                             help_url="https://www.backblaze.com/docs/cloud-storage-create-and-manage-app-keys"),
    "wasabi": Provider("wasabi", "https://s3.{region}.wasabisys.com", default_region="eu-central-1",
                       help_url="https://docs.wasabi.com/docs/creating-a-user-account-and-access-key"),
    "other": Provider("other", "", default_region="us-east-1"),
}

R2_JURISDICTIONS = {"default": "", "eu": ".eu", "fedramp": ".fedramp"}
