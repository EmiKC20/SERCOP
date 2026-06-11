"""Client utilities for SERCOP's public OCDS API."""

from __future__ import annotations

import logging
import re
import time
from datetime import date
from typing import Any

import pandas as pd
import requests
import streamlit as st
from dateutil.parser import parse as parse_date

LOGGER = logging.getLogger(__name__)

BASE_URL = "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA"
SEARCH_ENDPOINT = f"{BASE_URL}/api/search_ocds"
RECORD_ENDPOINT = f"{BASE_URL}/api/record"
PROCESS_URL = f"{BASE_URL}/ocds"
SOCE_SEARCH_URL = "https://www.compraspublicas.gob.ec/ProcesoContratacion/compras/PC/buscarProcesoRE.cpe"


class SercopAPIError(RuntimeError):
    """Raised when SERCOP's API cannot be queried successfully."""


def _safe_parse_date(value: Any) -> date | None:
    """Parse a loose API date value into a date."""
    if not value:
        return None
    try:
        return parse_date(str(value)).date()
    except (TypeError, ValueError, OverflowError):
        return None


def _safe_float(value: Any) -> float:
    """Convert loose OCDS monetary values to float."""
    if value in (None, "", "Sin información"):
        return 0.0
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _request_json(
    url: str,
    params: dict[str, Any],
    timeout: int = 25,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Fetch JSON from the SERCOP API with friendly error handling and 429 backoff."""
    last_error: requests.RequestException | None = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            if response.status_code == 429 and attempt < max_retries:
                retry_after = response.headers.get("Retry-After")
                wait_seconds = float(retry_after) if retry_after and retry_after.isdigit() else 2.0 * (attempt + 1)
                LOGGER.warning("SERCOP rate limit reached; waiting %.1f seconds before retry", wait_seconds)
                time.sleep(wait_seconds)
                continue
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            LOGGER.exception("SERCOP API request failed: %s", exc)
            raise SercopAPIError("No se pudo consultar la API del SERCOP. Intenta actualizar nuevamente.") from exc
        except ValueError as exc:
            LOGGER.exception("SERCOP API returned invalid JSON")
            raise SercopAPIError("La API del SERCOP respondió con un formato inesperado.") from exc

    raise SercopAPIError("No se pudo consultar la API del SERCOP.") from last_error


def _extract_value(*containers: dict[str, Any] | None) -> float:
    """Return the first monetary amount found in common OCDS containers."""
    for container in containers:
        if not isinstance(container, dict):
            continue
        value = container.get("value")
        if isinstance(value, dict):
            amount = _safe_float(value.get("amount"))
            if amount:
                return amount
        amount_obj = container.get("amount")
        if isinstance(amount_obj, dict):
            amount = _safe_float(amount_obj.get("amount"))
            if amount:
                return amount
        amount = _safe_float(container.get("amount"))
        if amount:
            return amount
    return 0.0


def _latest_release(record: dict[str, Any]) -> dict[str, Any]:
    """Select the latest release in a SERCOP OCDS record."""
    releases = record.get("releases") or []
    if not releases:
        return {}
    return max(releases, key=lambda item: item.get("date") or "")


def _all_releases(record_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every release from either OCDS record packages or release packages."""
    releases = record_payload.get("releases") or []
    records = record_payload.get("records") or []
    for record in records:
        releases.extend(record.get("releases") or [])
    return sorted(releases, key=lambda item: item.get("date") or "")


def _nested_value(container: dict[str, Any], path: tuple[str, ...]) -> Any:
    """Read a nested value from a dictionary path."""
    value: Any = container
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _process_code_from_ocid(ocid: str) -> str:
    """Extract the SOCE process code embedded in SERCOP OCDS identifiers."""
    prefix = "ocds-5wno2w-"
    if not ocid:
        return ""
    code = ocid.removeprefix(prefix)
    match = re.match(r"^(?P<process_code>.+-\d{4}-\d+)-\d+$", code)
    if match:
        return match.group("process_code")
    return code


def _first_date_from_releases(releases: list[dict[str, Any]], paths: list[tuple[str, ...]]) -> date | None:
    """Find the latest available date matching any path across releases."""
    for release in reversed(releases):
        for path in paths:
            parsed = _safe_parse_date(_nested_value(release, path))
            if parsed:
                return parsed
    return None


def _budget_from_releases(releases: list[dict[str, Any]]) -> float:
    """Extract SERCOP's presupuesto referencial from planning/tender releases."""
    for release in releases:
        planning = release.get("planning") or {}
        tender = release.get("tender") or {}
        awards = release.get("awards") or []
        contracts = release.get("contracts") or []
        amount = _extract_value(
            planning.get("budget"),
            tender.get("value"),
            tender,
            *(award.get("value") or award for award in awards if isinstance(award, dict)),
            *(contract.get("value") or contract for contract in contracts if isinstance(contract, dict)),
        )
        if amount:
            return amount
    return 0.0


def _first_dict_from_releases(releases: list[dict[str, Any]], key: str) -> dict[str, Any]:
    """Return the latest non-empty dictionary stored under a release key."""
    for release in reversed(releases):
        value = release.get(key)
        if isinstance(value, dict) and value:
            return value
    return {}


def _process_phase(releases: list[dict[str, Any]], tender: dict[str, Any]) -> str:
    """Classify the actionable phase of a process from OCDS release tags."""
    tags = {
        str(tag).lower()
        for release in releases
        for tag in (release.get("tag") or [])
    }
    terminal_statuses = {"complete", "cancelled", "unsuccessful", "terminated"}
    tender_status = str(tender.get("status") or "").lower()

    if tags.intersection({"award", "contract", "implementation"}) or tender_status in terminal_statuses:
        return "post_adjudicacion"
    if "tender" in tags or tender:
        return "licitacion"
    if "planning" in tags:
        return "planeacion"
    return "desconocida"


def normalize_search_item(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a search result from `search_ocds` into the app schema."""
    ocid = item.get("ocid", "")
    process_code = _process_code_from_ocid(ocid)
    return {
        "ocid": ocid,
        "codigo_proceso": process_code,
        "fecha_publicacion": _safe_parse_date(item.get("date")),
        "entidad": item.get("buyerName") or item.get("buyer") or "",
        "buyer_id": item.get("buyerId") or "",
        "titulo": item.get("title") or ocid,
        "objeto": item.get("description") or "",
        "descripcion": item.get("description") or "",
        "tipo_proceso": item.get("internal_type") or item.get("method") or "",
        "estado": "",
        "fase": "desconocida",
        "fuente_estado": "Datos abiertos SERCOP/OCDS",
        "monto": _safe_float(item.get("budget") or item.get("amount")),
        "fecha_cierre": None,
        "url": f"{PROCESS_URL}/{ocid}" if ocid else "",
        "url_soce": SOCE_SEARCH_URL,
        "proveedor": item.get("single_provider") or "",
    }


def normalize_record(record_payload: dict[str, Any], fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    """Normalize a detailed OCDS record into the app schema."""
    fallback = fallback or {}
    records = record_payload.get("records") or []
    record = records[0] if records else record_payload
    releases = _all_releases(record_payload) or [record]
    release = releases[-1] if releases else _latest_release(record)
    tender = _first_dict_from_releases(releases, "tender")
    planning = _first_dict_from_releases(releases, "planning")
    buyer = _first_dict_from_releases(releases, "buyer")

    ocid = release.get("ocid") or record.get("ocid") or fallback.get("ocid", "")
    process_code = _process_code_from_ocid(ocid)
    amount = _budget_from_releases(releases)
    close_date = (
        _first_date_from_releases(
            releases,
            [
                ("tender", "tenderPeriod", "endDate"),
                ("tender", "enquiryPeriod", "endDate"),
                ("tender", "awardPeriod", "endDate"),
                ("tender", "contractPeriod", "endDate"),
            ],
        )
        or _safe_parse_date(fallback.get("fecha_cierre"))
    )
    publication_date = _safe_parse_date(
        record_payload.get("publishedDate")
        or release.get("date")
        or fallback.get("fecha_publicacion")
    )
    title = tender.get("title") or planning.get("rationale") or fallback.get("titulo") or ocid
    description = tender.get("description") or planning.get("rationale") or fallback.get("descripcion", "")
    phase = _process_phase(releases, tender)

    return {
        **fallback,
        "ocid": ocid,
        "codigo_proceso": process_code or fallback.get("codigo_proceso", ""),
        "fecha_publicacion": publication_date,
        "entidad": buyer.get("name") or fallback.get("entidad", ""),
        "buyer_id": buyer.get("id") or fallback.get("buyer_id", ""),
        "titulo": title,
        "objeto": title or fallback.get("objeto", ""),
        "descripcion": description,
        "tipo_proceso": tender.get("procurementMethodDetails") or fallback.get("tipo_proceso", ""),
        "estado": tender.get("status") or fallback.get("estado", ""),
        "fase": phase,
        "fuente_estado": "Datos abiertos SERCOP/OCDS",
        "monto": amount or fallback.get("monto", 0.0),
        "fecha_cierre": close_date,
        "url": f"{PROCESS_URL}/{ocid}" if ocid else fallback.get("url", ""),
        "url_soce": SOCE_SEARCH_URL,
        "proveedor": fallback.get("proveedor", ""),
    }


@st.cache_data(ttl=30 * 60, show_spinner=False)
def fetch_record_payload(ocid: str) -> dict[str, Any]:
    """Fetch one raw SERCOP OCDS record payload by OCID."""
    return _request_json(RECORD_ENDPOINT, {"ocid": ocid})


def fetch_release_detail(ocid: str) -> dict[str, Any]:
    """Fetch and normalize one SERCOP OCDS record by OCID."""
    return normalize_record(fetch_record_payload(ocid))


@st.cache_data(ttl=30 * 60, show_spinner=False)
def search_releases(
    years: tuple[int, ...],
    search_terms: tuple[str, ...],
    max_pages: int = 2,
    buyer: str | None = None,
    supplier: str | None = None,
    enrich_details: bool = False,
    max_detail_records: int = 20,
    detail_delay_seconds: float = 0.6,
) -> list[dict[str, Any]]:
    """Search SERCOP OCDS releases with automatic pagination.

    The current official API documents `search_ocds` and `record`, not `/releases`.
    This function keeps the app-level "releases" vocabulary while using the active
    API contract underneath.
    """
    results: dict[str, dict[str, Any]] = {}
    for year in years:
        for term in search_terms:
            page = 1
            while page <= max_pages:
                params: dict[str, Any] = {"year": year, "search": term, "page": page}
                if buyer:
                    params["buyer"] = buyer
                if supplier:
                    params["supplier"] = supplier
                LOGGER.info("Searching SERCOP year=%s term=%s page=%s", year, term, page)
                payload = _request_json(SEARCH_ENDPOINT, params)
                for item in payload.get("data", []):
                    normalized = normalize_search_item(item)
                    if normalized["ocid"]:
                        results.setdefault(normalized["ocid"], normalized)

                total_pages = int(payload.get("pages") or 1)
                if page >= total_pages:
                    break
                page += 1

    if enrich_details:
        enriched = []
        for index, item in enumerate(results.values()):
            if index >= max_detail_records:
                enriched.append(item)
                continue
            try:
                if index:
                    time.sleep(detail_delay_seconds)
                detail = normalize_record(fetch_record_payload(item["ocid"]), fallback=item)
                enriched.append(detail)
            except SercopAPIError:
                LOGGER.warning("Skipping detail enrichment for OCID %s", item["ocid"])
                enriched.append(item)
        return enriched

    return list(results.values())


def releases_to_dataframe(releases: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert normalized releases to a pandas DataFrame with stable columns."""
    columns = [
        "ocid",
        "codigo_proceso",
        "entidad",
        "objeto",
        "descripcion",
        "monto",
        "fecha_publicacion",
        "fecha_cierre",
        "tipo_proceso",
        "estado",
        "fase",
        "fuente_estado",
        "url",
        "url_soce",
    ]
    if not releases:
        return pd.DataFrame(columns=columns)
    frame = pd.DataFrame(releases)
    for column in columns:
        if column not in frame:
            frame[column] = None
    return frame[columns]
