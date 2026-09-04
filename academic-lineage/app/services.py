"""Business validation and orchestration for lineage operations."""
from pathlib import Path

from flask import current_app

from . import exporter, fetcher, repositories
from .config import MAX_LINEAGE_DEPTH
from .db import get_db


class ValidationError(ValueError):
    """Maps to HTTP 400."""


class DuplicateError(ValueError):
    """Maps to HTTP 409."""


class NotFoundError(ValueError):
    """Maps to HTTP 404."""


def _require_str(payload, key, *, required=True, max_len=500):
    value = payload.get(key)
    if value is None:
        if required:
            raise ValidationError(f"{key} is required")
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{key} must be a string")
    value = value.strip()
    if required and not value:
        raise ValidationError(f"{key} is required")
    if len(value) > max_len:
        raise ValidationError(f"{key} is too long (max {max_len})")
    return value or None


def _optional_str(payload, key, max_len=500):
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{key} must be a string")
    return value.strip()[:max_len] or None


def _bool(payload, key, default=False):
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in ("true", "1", "yes", "on"):
            return True
        if value.lower() in ("false", "0", "no", "off", ""):
            return False
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    raise ValidationError(f"{key} must be a boolean")


def _year(payload, key):
    value = payload.get(key)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{key} must be an integer year")


def preview_person_service(payload: dict) -> dict:
    url = (payload or {}).get("url")
    if not url or not isinstance(url, str) or not url.strip():
        raise ValidationError("url is required")
    try:
        return fetcher.preview_person_url(url.strip())
    except ValueError as error:
        raise ValidationError(str(error)) from error


def create_person_service(payload: dict) -> tuple[dict, bool]:
    name = _require_str(payload, "name")
    homepage_url = _require_str(payload, "homepage_url", max_len=2048)
    data = {
        "name": name,
        "homepage_url": homepage_url,
        "name_en": _optional_str(payload, "name_en"),
        "institution": _optional_str(payload, "institution"),
        "field": _optional_str(payload, "field"),
        "homepage_title": _optional_str(payload, "homepage_title"),
        "notes_private": payload.get("notes_private") or None,
        "public": _bool(payload, "public", False),
    }
    aliases = payload.get("aliases")
    if aliases is not None:
        if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
            raise ValidationError("aliases must be a list of strings")
        data["aliases"] = [a.strip() for a in aliases if a.strip()][:20]
    return repositories.find_or_create_person(data)


def _resolve_person_id(payload, id_key, url_key):
    person_id = _require_str(payload, id_key, required=False)
    if person_id:
        return person_id
    url = _require_str(payload, url_key, required=False)
    if url:
        person = repositories.get_person_by_url(repositories.normalize_homepage_url(url))
        if person is not None:
            return person["id"]
    return None


def create_mentorship_service(payload: dict) -> dict:
    mentor_id = _resolve_person_id(payload, "mentor_id", "mentor_url")
    student_id = _resolve_person_id(payload, "student_id", "student_url")
    if not mentor_id or not student_id:
        raise ValidationError("mentor_id and student_id are required")

    relationship_type = (payload.get("relationship_type") or "phd").strip()
    if relationship_type not in repositories.RELATIONSHIP_TYPES:
        raise ValidationError(f"invalid relationship_type: {relationship_type}")
    confidence = (payload.get("confidence") or "confirmed").strip()
    if confidence not in repositories.CONFIDENCE_LEVELS:
        raise ValidationError(f"invalid confidence: {confidence}")
    status = (payload.get("status") or "draft").strip()
    if status not in repositories.MENTORSHIP_STATUSES:
        raise ValidationError(f"invalid status: {status}")

    data = {
        "mentor_id": mentor_id,
        "student_id": student_id,
        "relationship_type": relationship_type,
        "confidence": confidence,
        "status": status,
        "evidence_url": _require_str(payload, "evidence_url"),
        "evidence_text": _optional_str(payload, "evidence_text"),
        "institution": _optional_str(payload, "institution"),
        "public": _bool(payload, "public", False),
        "notes_private": payload.get("notes_private") or None,
        "start_year": _year(payload, "start_year"),
        "end_year": _year(payload, "end_year"),
    }
    repositories.validate_years(data)
    try:
        return repositories.create_mentorship(data)
    except repositories.DuplicateMentorshipError as error:
        raise DuplicateError(str(error)) from error
    except KeyError as error:
        raise NotFoundError(str(error)) from error


def lineage_service(person_id: str, up="3", down="2") -> dict:
    if not person_id:
        raise ValidationError("person id is required")
    try:
        up_i = int(up)
        down_i = int(down)
    except (TypeError, ValueError):
        raise ValidationError("up and down must be integers")
    if not (0 <= up_i <= MAX_LINEAGE_DEPTH and 0 <= down_i <= MAX_LINEAGE_DEPTH):
        raise ValidationError(f"lineage depth must be between 0 and {MAX_LINEAGE_DEPTH}")
    try:
        return repositories.get_lineage(person_id, up_i, down_i)
    except KeyError as error:
        raise NotFoundError(str(error)) from error


_UPDATE_ALLOWED = {
    "status", "confidence", "start_year", "end_year", "institution",
    "evidence_url", "evidence_text", "public", "notes_private",
}


def update_mentorship_service(mentorship_id: str, payload: dict) -> dict:
    unknown = set(payload) - _UPDATE_ALLOWED - {"id"}
    if unknown:
        raise ValidationError(f"fields not allowed: {', '.join(sorted(unknown))}")

    fields: dict = {}
    if "status" in payload:
        status = (payload.get("status") or "").strip()
        if status not in repositories.MENTORSHIP_STATUSES:
            raise ValidationError(f"invalid status: {status}")
        fields["status"] = status
    if "confidence" in payload:
        confidence = (payload.get("confidence") or "").strip()
        if confidence not in repositories.CONFIDENCE_LEVELS:
            raise ValidationError(f"invalid confidence: {confidence}")
        fields["confidence"] = confidence
    if "evidence_url" in payload:
        evidence_url = (payload.get("evidence_url") or "").strip()
        if not evidence_url:
            raise ValidationError("evidence_url is required")
        fields["evidence_url"] = evidence_url
    if "public" in payload:
        fields["public"] = _bool(payload, "public")
    for key in ("evidence_text", "institution", "notes_private"):
        if key in payload:
            fields[key] = payload.get(key)
    if "start_year" in payload:
        fields["start_year"] = _year(payload, "start_year")
    if "end_year" in payload:
        fields["end_year"] = _year(payload, "end_year")

    try:
        result = repositories.update_mentorship(mentorship_id, fields)
    except ValueError as error:
        raise ValidationError(str(error)) from error
    if result is None:
        raise NotFoundError("mentorship not found")
    return result


def export_public_service() -> dict:
    output_dir = Path(current_app.config["PUBLIC_DATA_DIR"])
    return exporter.export_public_data(get_db(), output_dir)
