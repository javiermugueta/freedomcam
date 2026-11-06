"""Config flow: a guided setup of the storage, global options and one subentry per camera."""
from __future__ import annotations

import io
import re
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from PIL import Image

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import slugify

from . import ai
from .const import (
    AI_CLOUDFLARE,
    AI_NONE,
    CONF_ACCESS_KEY,
    CONF_ACCOUNT_ID,
    CONF_AI_ACCOUNT_ID,
    CONF_AI_MIN_SCORE,
    CONF_AI_PROVIDER,
    CONF_AI_TOKEN,
    CONF_APP_ACCESS_KEY,
    CONF_APP_SECRET_KEY,
    CONF_BUCKET,
    CONF_CAMERA_ENTITY,
    CONF_CAMERA_ID,
    CONF_ENDPOINT,
    CONF_INTERVAL,
    CONF_JURISDICTION,
    CONF_KIND,
    CONF_MANAGE_LIFECYCLE,
    CONF_MAX_PER_HOUR,
    CONF_MODE,
    CONF_MOTION_ENTITY,
    CONF_NAME,
    CONF_ONLY_WHEN_AWAY,
    CONF_PAUSE,
    CONF_PRESENCE_ENTITY,
    CONF_PROVIDER,
    CONF_REGION,
    CONF_RETENTION_DAYS,
    CONF_SECRET_KEY,
    CONF_SENSITIVITY,
    CONF_THUMBNAILS,
    CONF_VIRTUAL_HOST,
    DEFAULT_AI_MIN_SCORE,
    DEFAULT_INTERVAL,
    DEFAULT_MAX_PER_HOUR,
    DEFAULT_PAUSE,
    DEFAULT_RETENTION,
    DEFAULT_SENSITIVITY,
    DOMAIN,
    KIND_INDOOR,
    KIND_OUTDOOR,
    MODE_IMAGE,
    MODE_SENSOR,
    PROVIDERS,
    R2_JURISDICTIONS,
    SENSITIVITIES,
    SUBENTRY_CAMERA,
)
from .s3 import S3Error
from .storage import check_app_keys, check_bucket, client_from_config, endpoint_for

CAMERA_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
TEXT = TextSelector()
SECRET = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
URL = TextSelector(TextSelectorConfig(type=TextSelectorType.URL))


def _select(options: list[str], key: str, dropdown: bool = False) -> SelectSelector:
    return SelectSelector(SelectSelectorConfig(
        options=options, translation_key=key,
        mode=SelectSelectorMode.DROPDOWN if dropdown else SelectSelectorMode.LIST))


def _number(lo: float, hi: float, step: float = 1, unit: str | None = None) -> NumberSelector:
    config = NumberSelectorConfig(min=lo, max=hi, step=step, mode=NumberSelectorMode.BOX)
    if unit:
        config["unit_of_measurement"] = unit
    return NumberSelector(config)


def _keys_schema() -> dict:
    return {vol.Required(CONF_BUCKET): TEXT, vol.Required(CONF_ACCESS_KEY): TEXT,
            vol.Required(CONF_SECRET_KEY): SECRET}


def _storage_schema(provider: str) -> vol.Schema:
    if provider == "cloudflare_r2":
        fields = {vol.Required(CONF_ACCOUNT_ID): TEXT,
                  vol.Required(CONF_JURISDICTION, default="default"): _select(list(R2_JURISDICTIONS), "jurisdiction")}
    elif provider == "other":
        fields = {vol.Required(CONF_ENDPOINT): URL,
                  vol.Required(CONF_REGION, default=PROVIDERS["other"].default_region): TEXT,
                  vol.Required(CONF_VIRTUAL_HOST, default=False): BooleanSelector()}
    else:
        fields = {vol.Required(CONF_REGION, default=PROVIDERS[provider].default_region): TEXT}
    return vol.Schema(fields | _keys_schema())


def _test_jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (64, 64), (120, 120, 120)).save(out, "JPEG")
    return out.getvalue()


class FreedomCamConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return FreedomCamOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_CAMERA: CameraSubentryFlow}

    # ------------------------------------------------------------------ 1. provider
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data = {CONF_PROVIDER: user_input[CONF_PROVIDER]}
            return await self.async_step_storage()
        return self.async_show_form(step_id="user", data_schema=vol.Schema(
            {vol.Required(CONF_PROVIDER, default="cloudflare_r2"): _select(list(PROVIDERS), "provider")}))

    # ------------------------------------------------------------------ 2. bucket and keys
    async def async_step_storage(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """One form per provider (step ids are the provider keys, each with its own instructions)."""
        provider = self._data[CONF_PROVIDER]
        errors: dict[str, str] = {}
        if user_input is not None:
            data = self._data | {k: v.strip() if isinstance(v, str) else v for k, v in user_input.items()}
            endpoint, _, _ = endpoint_for(data)
            await self.async_set_unique_id(f"{endpoint}/{data[CONF_BUCKET]}".lower())
            self._abort_if_unique_id_configured()
            error = await check_bucket(client_from_config(async_get_clientsession(self.hass), data))
            if error is None:
                self._data = data
                return await self.async_step_retention()
            errors["base"] = error
        return self.async_show_form(
            step_id=provider, errors=errors,
            data_schema=self.add_suggested_values_to_schema(_storage_schema(provider), user_input or {}),
            description_placeholders={"help_url": PROVIDERS[provider].help_url})

    async_step_cloudflare_r2 = async_step_storage
    async_step_aws_s3 = async_step_storage
    async_step_backblaze_b2 = async_step_storage
    async_step_wasabi = async_step_storage
    async_step_other = async_step_storage

    # ------------------------------------------------------------------ 3. retention
    async def async_step_retention(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            days = int(user_input[CONF_RETENTION_DAYS])
            manage = user_input[CONF_MANAGE_LIFECYCLE]
            if manage:
                try:
                    await client_from_config(async_get_clientsession(self.hass), self._data).set_retention(days)
                except S3Error as err:
                    errors["base"] = "lifecycle_denied" if err.status in (401, 403) else "lifecycle_failed"
            if not errors:
                return self.async_create_entry(
                    title=self._data[CONF_BUCKET],
                    data=self._data | {CONF_RETENTION_DAYS: days, CONF_MANAGE_LIFECYCLE: manage},
                    options={CONF_PAUSE: DEFAULT_PAUSE, CONF_MAX_PER_HOUR: DEFAULT_MAX_PER_HOUR,
                             CONF_SENSITIVITY: DEFAULT_SENSITIVITY, CONF_THUMBNAILS: True,
                             CONF_AI_PROVIDER: AI_NONE})
        schema = vol.Schema({
            vol.Required(CONF_RETENTION_DAYS, default=DEFAULT_RETENTION): _number(0, 3650, unit="d"),
            vol.Required(CONF_MANAGE_LIFECYCLE, default=True): BooleanSelector(),
        })
        return self.async_show_form(step_id="retention", errors=errors,
                                    data_schema=self.add_suggested_values_to_schema(schema, user_input or {}))

    # ------------------------------------------------------------------ new keys
    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = dict(entry.data) | {k: v.strip() for k, v in user_input.items()}
            error = await check_bucket(client_from_config(async_get_clientsession(self.hass), data), create=False)
            if error is None:
                return self.async_update_reload_and_abort(entry, data=data)
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm", errors=errors,
            data_schema=vol.Schema({vol.Required(CONF_ACCESS_KEY): TEXT, vol.Required(CONF_SECRET_KEY): SECRET}),
            description_placeholders={"bucket": entry.data[CONF_BUCKET]})


class FreedomCamOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_AI_PROVIDER] == AI_CLOUDFLARE:
                account = user_input.get(CONF_AI_ACCOUNT_ID, "").strip()
                token = user_input.get(CONF_AI_TOKEN, "").strip()
                if not (account and token):
                    errors["base"] = "ai_missing"
                else:
                    try:
                        await ai.cloudflare_detect(async_get_clientsession(self.hass), account, token,
                                                   await self.hass.async_add_executor_job(_test_jpeg))
                    except ai.DetectionError:
                        errors["base"] = "ai_failed"
            if not errors:
                errors = await self._check_app_keys(user_input)
            if not errors:
                return self.async_create_entry(data=user_input)
        o = self.config_entry.options
        schema = vol.Schema({
            vol.Optional(CONF_PRESENCE_ENTITY): EntitySelector(EntitySelectorConfig(
                domain=["input_boolean", "binary_sensor", "person", "zone", "group", "device_tracker"])),
            vol.Required(CONF_PAUSE, default=DEFAULT_PAUSE): _number(1, 3600, unit="s"),
            vol.Required(CONF_MAX_PER_HOUR, default=DEFAULT_MAX_PER_HOUR): _number(1, 3600),
            vol.Required(CONF_SENSITIVITY, default=DEFAULT_SENSITIVITY): _select(list(SENSITIVITIES), "sensitivity"),
            vol.Required(CONF_THUMBNAILS, default=True): BooleanSelector(),
            vol.Required(CONF_AI_PROVIDER, default=AI_NONE): _select([AI_NONE, AI_CLOUDFLARE], "ai_provider"),
            vol.Optional(CONF_AI_ACCOUNT_ID): TEXT,
            vol.Optional(CONF_AI_TOKEN): SECRET,
            vol.Required(CONF_AI_MIN_SCORE, default=DEFAULT_AI_MIN_SCORE): _number(0.3, 0.99, 0.01),
            vol.Optional(CONF_APP_ACCESS_KEY): TEXT,
            vol.Optional(CONF_APP_SECRET_KEY): SECRET,
        })
        return self.async_show_form(step_id="init", errors=errors,
                                    data_schema=self.add_suggested_values_to_schema(schema, user_input or o))


    async def _check_app_keys(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Read-only keys for the iOS app (shown as a QR code). Both or none."""
        key = (user_input.get(CONF_APP_ACCESS_KEY) or "").strip()
        secret = (user_input.get(CONF_APP_SECRET_KEY) or "").strip()
        if not key and not secret:
            return {}
        if not (key and secret):
            return {"base": "app_keys_incomplete"}
        user_input[CONF_APP_ACCESS_KEY], user_input[CONF_APP_SECRET_KEY] = key, secret
        data = dict(self.config_entry.data) | {CONF_ACCESS_KEY: key, CONF_SECRET_KEY: secret}
        error = await check_app_keys(client_from_config(async_get_clientsession(self.hass), data))
        return {"base": error} if error else {}


class CameraSubentryFlow(ConfigSubentryFlow):
    """Add or edit one camera."""

    def _schema(self, editing: bool) -> vol.Schema:
        fields: dict = {vol.Required(CONF_CAMERA_ENTITY): EntitySelector(EntitySelectorConfig(domain="camera")),
                        vol.Required(CONF_NAME): TEXT}
        if not editing:
            fields[vol.Optional(CONF_CAMERA_ID)] = TEXT
        return vol.Schema(fields | {
            vol.Required(CONF_KIND, default=KIND_OUTDOOR): _select([KIND_OUTDOOR, KIND_INDOOR], "kind"),
            vol.Required(CONF_MODE, default=MODE_IMAGE): _select([MODE_IMAGE, MODE_SENSOR], "mode"),
            vol.Optional(CONF_MOTION_ENTITY): EntitySelector(EntitySelectorConfig(domain="binary_sensor")),
            vol.Required(CONF_INTERVAL, default=DEFAULT_INTERVAL): _number(2, 600, unit="s"),
            vol.Required(CONF_ONLY_WHEN_AWAY, default=False): BooleanSelector(),
        })

    def _validate(self, user_input: dict[str, Any], current_id: str | None) -> tuple[dict[str, Any], dict[str, str]]:
        data = dict(user_input)
        data[CONF_NAME] = data[CONF_NAME].strip()
        camera_id = current_id or (data.get(CONF_CAMERA_ID) or "").strip() or slugify(data[CONF_NAME]).replace("_", "-")
        data[CONF_CAMERA_ID] = camera_id
        errors: dict[str, str] = {}
        taken = {s.data.get(CONF_CAMERA_ID) for s in self._get_entry().subentries.values()} - {current_id}
        if not CAMERA_ID_RE.match(camera_id):
            errors[CONF_CAMERA_ID] = "invalid_camera_id"
        elif camera_id in taken:
            errors[CONF_CAMERA_ID] = "camera_id_taken"
        if data[CONF_MODE] == MODE_SENSOR and not data.get(CONF_MOTION_ENTITY):
            errors[CONF_MOTION_ENTITY] = "motion_entity_required"
        return data, errors

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = self._validate(user_input, None)
            if not errors:
                return self.async_create_entry(title=data[CONF_NAME], data=data)
        schema = self.add_suggested_values_to_schema(self._schema(False), user_input or {})
        return self.async_show_form(step_id="user", errors=errors, data_schema=schema)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = self._validate(user_input, subentry.data[CONF_CAMERA_ID])
            if not errors:
                return self.async_update_and_abort(self._get_entry(), subentry, title=data[CONF_NAME], data=data)
        return self.async_show_form(
            step_id="reconfigure", errors=errors,
            data_schema=self.add_suggested_values_to_schema(self._schema(True), user_input or subentry.data),
            description_placeholders={"camera_id": subentry.data[CONF_CAMERA_ID]})
