"""Outlet registry: schema, validation and lookup (``docs/corpus_supply/INDEX.md`` §4).

The registry is a tracked JSON file under ``config/`` and is the source of truth for which outlets
exist. An id is assigned there by review and never derived from a display name at run time.

``registration_status`` separates what was *proposed* (for instance by the legacy import) from
what is *registered*. Only a registered outlet resolves: code that accepts an ``outlet_id``
calls :meth:`Registry.resolve` and gets a refusal for anything else.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from . import naming
from .identity import IdentityError, OutletUrlRules, is_channel_id, normalise_origin

REGISTRY_SCHEMA = naming.schema_id("outlet-registry", 1)

UNKNOWN = "unknown"
NOT_APPLICABLE = "not_applicable"

REGISTRATION_STATUSES = ("proposed", "registered")
OUTLET_TYPES = (
    "national_reference",
    "popular_tabloid",
    "regional",
    "digital_native",
    "state_official",
    "news_agency",
    "broadcaster_website",
    UNKNOWN,
)
ACCESS_MODELS = ("open", "metered", "hard_paywall", UNKNOWN)
MEDIA = ("print_and_web", "web_only", UNKNOWN)
CHANNEL_KINDS = ("rss", "atom", "sitemap", "sitemap_index", "section_page", "archive", UNKNOWN)
MAPPING_STATUSES = ("hypothesis", "human_audited")

_OUTLET_FIELDS = {
    "outlet_id", "country_id", "registration_status", "display_names", "outlet_type",
    "outlet_group", "city", "region", "scope", "access_model", "medium", "editions",
    "web_origins", "timezone", "same_outlet_basis", "url_rules", "channels", "legacy_aliases",
    "legacy_observed", "review_notes",
}
_OPTIONAL_OUTLET_FIELDS = {"orientation"}
_CHANNEL_FIELDS = {"channel_id", "kind", "url_history", "legacy_observed"}
_ALIAS_FIELDS = {"country_code", "slug", "observed_in", "mapping_status"}
_URL_RULE_FIELDS = {"version", "significant_query_params", "strip_path_prefixes", "strip_path_suffixes"}
_TIMEZONE = re.compile(r"[A-Za-z_]+(?:/[A-Za-z0-9_+-]+)+|UTC")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class RegistryError(ValueError):
    """The registry file does not satisfy its schema."""


class UnregisteredOutlet(LookupError):
    """The id is unknown to the registry, or only proposed."""


@dataclass(frozen=True)
class Registry:
    outlets: Mapping[str, Mapping[str, Any]]

    def resolve(self, outlet_id: str) -> Mapping[str, Any]:
        """The registered outlet, or a refusal. The lexical form of an id proves nothing."""
        outlet = self.outlets.get(outlet_id)
        if outlet is None:
            raise UnregisteredOutlet(f"unknown outlet_id: {outlet_id!r}")
        if outlet["registration_status"] != "registered":
            raise UnregisteredOutlet(f"{outlet_id} is {outlet['registration_status']}, not registered")
        return outlet

    def url_rules(self, outlet_id: str) -> OutletUrlRules:
        """The URL rules of a registered outlet, for the canonical URL key."""
        outlet = self.resolve(outlet_id)
        rules = outlet["url_rules"]
        return OutletUrlRules(
            outlet_id=outlet_id,
            web_origins=tuple(outlet["web_origins"]),
            version=rules["version"],
            significant_query_params=tuple(rules["significant_query_params"]),
            strip_path_prefixes=tuple(rules["strip_path_prefixes"]),
            strip_path_suffixes=tuple(rules["strip_path_suffixes"]),
        )

    def legacy_alias(self, country_code: str, slug: str) -> list[str]:
        """Every outlet (registered or proposed) that lists this legacy name, exactly as observed.

        A list, because the registry does not hide an ambiguous legacy name behind a first match.
        """
        return sorted(
            outlet_id
            for outlet_id, outlet in self.outlets.items()
            if any(a["country_code"] == country_code and a["slug"] == slug for a in outlet["legacy_aliases"])
        )


def propose_slug(name: str) -> str:
    """An ASCII slug *proposal* for a registration (``El País`` → ``el_pais``).

    A helper for the person registering an outlet; never used to derive an id at run time. Returns
    an empty string when nothing usable is left.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    ascii_text = ascii_text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")


def load_registry(path: Path) -> Registry:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RegistryError(f"registry is not readable JSON: {error}") from error
    return validate_registry(document)


def validate_registry(document: Any) -> Registry:
    """Check a registry document completely and return it indexed by ``outlet_id``."""
    if not isinstance(document, dict) or set(document) != {"schema", "outlets"}:
        raise RegistryError("a registry has exactly the keys 'schema' and 'outlets'")
    if document["schema"] != REGISTRY_SCHEMA:
        raise RegistryError(f"schema is {document['schema']!r}, expected {REGISTRY_SCHEMA!r}")
    if not isinstance(document["outlets"], list):
        raise RegistryError("'outlets' is a list")
    outlets: dict[str, Mapping[str, Any]] = {}
    channels: set[str] = set()
    for outlet in document["outlets"]:
        _validate_outlet(outlet)
        if outlet["outlet_id"] in outlets:
            raise RegistryError(f"outlet_id assigned twice: {outlet['outlet_id']}")
        outlets[outlet["outlet_id"]] = outlet
        for channel in outlet["channels"]:
            if channel["channel_id"] in channels:
                raise RegistryError(f"channel_id assigned twice: {channel['channel_id']}")
            channels.add(channel["channel_id"])
    if list(outlets) != sorted(outlets):
        raise RegistryError("outlets are listed in outlet_id order, so that a diff shows one change")
    return Registry(outlets)


def _validate_outlet(outlet: Any) -> None:
    if not isinstance(outlet, dict):
        raise RegistryError("an outlet is an object")
    name = outlet.get("outlet_id")
    if not naming.is_outlet_id(name):
        raise RegistryError(f"not an outlet_id: {name!r}")
    keys = set(outlet)
    if not (_OUTLET_FIELDS <= keys <= _OUTLET_FIELDS | _OPTIONAL_OUTLET_FIELDS):
        missing, extra = sorted(_OUTLET_FIELDS - keys), sorted(keys - _OUTLET_FIELDS - _OPTIONAL_OUTLET_FIELDS)
        raise RegistryError(f"{name}: missing fields {missing}, unknown fields {extra}")
    if outlet["country_id"] != naming.outlet_country(name):
        raise RegistryError(f"{name}: country_id {outlet['country_id']!r} is not the id's country")
    _one_of(name, outlet, "registration_status", REGISTRATION_STATUSES)
    _one_of(name, outlet, "outlet_type", OUTLET_TYPES)
    _one_of(name, outlet, "access_model", ACCESS_MODELS)
    _one_of(name, outlet, "medium", MEDIA)
    for field in ("outlet_group", "city", "region", "scope", "same_outlet_basis"):
        _text(name, outlet, field)
    if outlet["timezone"] != UNKNOWN and (
        not isinstance(outlet["timezone"], str) or _TIMEZONE.fullmatch(outlet["timezone"]) is None
    ):
        raise RegistryError(f"{name}: timezone is an IANA zone name or 'unknown'")

    _list(name, outlet, "display_names")
    if not outlet["display_names"]:
        raise RegistryError(f"{name}: at least one display name")
    for entry in outlet["display_names"]:
        if not isinstance(entry, dict) or set(entry) != {"name", "valid_from", "valid_to"}:
            raise RegistryError(f"{name}: a display name has name, valid_from, valid_to")
        if not isinstance(entry["name"], str) or not entry["name"].strip():
            raise RegistryError(f"{name}: empty display name")
        for bound in ("valid_from", "valid_to"):
            if entry[bound] not in (UNKNOWN, NOT_APPLICABLE) and (
                not isinstance(entry[bound], str) or _DATE.fullmatch(entry[bound]) is None
            ):
                raise RegistryError(f"{name}: {bound} is a date, 'unknown' or 'not_applicable'")

    for field in ("editions", "review_notes"):
        _list(name, outlet, field)
        if not all(isinstance(item, str) and item for item in outlet[field]):
            raise RegistryError(f"{name}: {field} is a list of non-empty strings")

    _list(name, outlet, "web_origins")
    try:
        normalised = [normalise_origin(origin) for origin in outlet["web_origins"]]
    except IdentityError as error:
        raise RegistryError(f"{name}: {error}") from error
    if normalised != outlet["web_origins"] or len(set(normalised)) != len(normalised):
        raise RegistryError(f"{name}: web_origins are normalised, distinct 'scheme://host[:port]' values")

    rules = outlet["url_rules"]
    if not isinstance(rules, dict) or set(rules) != _URL_RULE_FIELDS:
        raise RegistryError(f"{name}: url_rules has exactly {sorted(_URL_RULE_FIELDS)}")
    if outlet["web_origins"]:
        try:
            OutletUrlRules(
                name, tuple(outlet["web_origins"]), rules["version"],
                tuple(rules["significant_query_params"]),
                tuple(rules["strip_path_prefixes"]), tuple(rules["strip_path_suffixes"]),
            )
        except (IdentityError, TypeError) as error:
            raise RegistryError(f"{name}: {error}") from error

    _list(name, outlet, "channels")
    for channel in outlet["channels"]:
        if not isinstance(channel, dict) or set(channel) != _CHANNEL_FIELDS:
            raise RegistryError(f"{name}: a channel has exactly {sorted(_CHANNEL_FIELDS)}")
        identifier = channel["channel_id"]
        if not is_channel_id(identifier) or not identifier.startswith(f"{name}:ch:"):
            raise RegistryError(f"{name}: not a channel_id of this outlet: {identifier!r}")
        _one_of(identifier, channel, "kind", CHANNEL_KINDS)
        history = channel["url_history"]
        if not isinstance(history, list) or not history:
            raise RegistryError(f"{identifier}: url_history holds at least the current URL")
        for entry in history:
            if not isinstance(entry, dict) or set(entry) != {"url", "valid_from"}:
                raise RegistryError(f"{identifier}: a url_history entry has url and valid_from")
            if not isinstance(entry["url"], str) or not entry["url"].strip():
                raise RegistryError(f"{identifier}: empty channel URL")
            if entry["valid_from"] != UNKNOWN and (
                not isinstance(entry["valid_from"], str) or _DATE.fullmatch(entry["valid_from"]) is None
            ):
                raise RegistryError(f"{identifier}: valid_from is a date or 'unknown'")
        if not isinstance(channel["legacy_observed"], dict):
            raise RegistryError(f"{identifier}: legacy_observed is an object (empty when not from legacy)")

    _list(name, outlet, "legacy_aliases")
    seen = set()
    for alias in outlet["legacy_aliases"]:
        if not isinstance(alias, dict) or set(alias) != _ALIAS_FIELDS:
            raise RegistryError(f"{name}: a legacy alias has exactly {sorted(_ALIAS_FIELDS)}")
        for field in ("country_code", "slug", "observed_in"):
            if not isinstance(alias[field], str) or not alias[field]:
                raise RegistryError(f"{name}: legacy alias field {field} is a non-empty string")
        _one_of(name, alias, "mapping_status", MAPPING_STATUSES)
        key = (alias["country_code"], alias["slug"], alias["observed_in"])
        if key in seen:
            raise RegistryError(f"{name}: legacy alias listed twice: {key}")
        seen.add(key)
    if not isinstance(outlet["legacy_observed"], dict):
        raise RegistryError(f"{name}: legacy_observed is an object (empty when not from legacy)")

    if outlet["registration_status"] == "registered":
        if not outlet["web_origins"]:
            raise RegistryError(f"{name}: a registered outlet has at least one web origin")
        if outlet["review_notes"]:
            raise RegistryError(f"{name}: a registered outlet has no open review notes")


def _one_of(owner: str, record: Mapping[str, Any], field: str, allowed: tuple[str, ...]) -> None:
    if record[field] not in allowed:
        raise RegistryError(f"{owner}: {field}={record[field]!r} is not one of {allowed}")


def _text(owner: str, record: Mapping[str, Any], field: str) -> None:
    if not isinstance(record[field], str) or not record[field].strip():
        raise RegistryError(f"{owner}: {field} is a non-empty string ('unknown' when not known)")


def _list(owner: str, record: Mapping[str, Any], field: str) -> None:
    if not isinstance(record[field], list):
        raise RegistryError(f"{owner}: {field} is a list")
