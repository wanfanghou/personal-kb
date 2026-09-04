"""Business validation and orchestration for lineage operations."""
from pathlib import Path

from flask import current_app

from . import exporter, fetcher, repositories
from .config import MAX_LINEAGE_DEPTH
from .db import get_db


class ValidationError(ValueError):
    """Maps to HTTP 400."""


class DuplicateError(ValueError):
    """Maps to HTTP 409; carries the existing record when available."""

    def __init__(self, message, existing=None):
        super().__init__(message)
        self.existing = existing


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


def _string_list(payload, key, max_items=50):
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        items = [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        items = [item.strip() for item in value if item.strip()]
    else:
        raise ValidationError(f"{key} must be a list of strings")
    return items[:max_items]


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
        "title": _optional_str(payload, "title"),
        "homepage_title": _optional_str(payload, "homepage_title"),
        "notes_private": payload.get("notes_private") or None,
        "public": _bool(payload, "public", False),
    }
    aliases = _string_list(payload, "aliases", max_items=20)
    if aliases is not None:
        data["aliases"] = aliases
    editorial_roles = _string_list(payload, "editorial_roles")
    if editorial_roles is not None:
        data["editorial_roles"] = editorial_roles
    honors = _string_list(payload, "honors")
    if honors is not None:
        data["honors"] = honors
    return repositories.find_or_create_person(data)


PERSON_UPDATE_ALLOWED = {
    "name", "name_en", "aliases", "institution", "field", "title",
    "editorial_roles", "honors", "public", "notes_private", "homepage_title",
}


def update_person_service(person_id: str, payload: dict) -> dict:
    unknown = set(payload) - PERSON_UPDATE_ALLOWED - {"id"}
    if unknown:
        raise ValidationError(f"fields not allowed: {', '.join(sorted(unknown))}")

    fields: dict = {}
    if "name" in payload:
        fields["name"] = _require_str(payload, "name")
    for key in ("name_en", "institution", "field", "title", "notes_private", "homepage_title"):
        if key in payload:
            fields[key] = payload.get(key)
    for key in ("aliases", "editorial_roles", "honors"):
        if key in payload:
            fields[key] = _string_list(payload, key, max_items=20 if key == "aliases" else 50) or []
    if "public" in payload:
        fields["public"] = _bool(payload, "public")

    try:
        result = repositories.update_person(person_id, fields)
    except ValueError as error:
        raise ValidationError(str(error)) from error
    if result is None:
        raise NotFoundError("person not found")
    return result


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
        "student_placement": _optional_str(payload, "student_placement"),
        "public": _bool(payload, "public", False),
        "notes_private": payload.get("notes_private") or None,
        "start_year": _year(payload, "start_year"),
        "end_year": _year(payload, "end_year"),
    }
    repositories.validate_years(data)
    try:
        return repositories.create_mentorship(data)
    except repositories.DuplicateMentorshipError as error:
        existing = repositories.find_mentorship(mentor_id, student_id, relationship_type)
        raise DuplicateError(str(error), existing=existing) from error
    except KeyError as error:
        raise NotFoundError(str(error)) from error


def lineage_service(person_id: str, up="3", down="2", relationship_type: str | None = None) -> dict:
    if not person_id:
        raise ValidationError("person id is required")
    try:
        up_i = int(up)
        down_i = int(down)
    except (TypeError, ValueError):
        raise ValidationError("up and down must be integers")
    if not (0 <= up_i <= MAX_LINEAGE_DEPTH and 0 <= down_i <= MAX_LINEAGE_DEPTH):
        raise ValidationError(f"lineage depth must be between 0 and {MAX_LINEAGE_DEPTH}")
    if relationship_type and relationship_type not in repositories.RELATIONSHIP_TYPES:
        raise ValidationError(f"invalid relationship_type: {relationship_type}")
    try:
        return repositories.get_lineage(person_id, up_i, down_i, relationship_type or None)
    except KeyError as error:
        raise NotFoundError(str(error)) from error


_UPDATE_ALLOWED = {
    "status", "confidence", "start_year", "end_year", "institution",
    "student_placement", "evidence_url", "evidence_text", "public", "notes_private",
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
    for key in ("evidence_text", "institution", "student_placement", "notes_private"):
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


# ---------- 投稿审核 ----------

def _validate_submission_payload(payload) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError("payload must be a JSON object")
    mentor = payload.get("mentor")
    student = payload.get("student")
    relationship = payload.get("relationship")
    if not isinstance(mentor, dict) or not isinstance(student, dict) or not isinstance(relationship, dict):
        raise ValidationError("mentor / student / relationship fields are required")

    mentor_name = _require_str(mentor, "name")
    mentor_url = _require_str(mentor, "homepage_url", max_len=2048)
    student_name = _require_str(student, "name")
    student_url = _require_str(student, "homepage_url", max_len=2048)
    try:
        mentor_url = repositories.normalize_homepage_url(mentor_url)
        student_url = repositories.normalize_homepage_url(student_url)
    except ValueError as error:
        raise ValidationError(str(error)) from error
    if mentor_url == student_url:
        raise ValidationError("导师与学生的主页 URL 不能相同")

    relationship_type = (relationship.get("relationship_type") or "phd").strip()
    if relationship_type not in repositories.RELATIONSHIP_TYPES:
        raise ValidationError(f"invalid relationship_type: {relationship_type}")
    confidence = (relationship.get("confidence") or "confirmed").strip()
    if confidence not in repositories.CONFIDENCE_LEVELS:
        raise ValidationError(f"invalid confidence: {confidence}")

    rel_data = {
        "relationship_type": relationship_type,
        "confidence": confidence,
        "start_year": _year(relationship, "start_year"),
        "end_year": _year(relationship, "end_year"),
        "institution": _optional_str(relationship, "institution"),
        "student_placement": _optional_str(relationship, "student_placement"),
        "evidence_url": _require_str(relationship, "evidence_url", required=False) or student_url,
        "evidence_text": _optional_str(relationship, "evidence_text"),
    }
    repositories.validate_years(rel_data)

    return {
        "mentor": {
            "name": mentor_name,
            "homepage_url": mentor_url,
            "title": _optional_str(mentor, "title"),
        },
        "student": {
            "name": student_name,
            "homepage_url": student_url,
            "title": _optional_str(student, "title"),
        },
        "relationship": rel_data,
    }


def create_submission_service(payload: dict, submitter_note: str | None = None) -> dict:
    cleaned = _validate_submission_payload(payload)
    note = (submitter_note or "").strip()[:1000] or None
    return repositories.create_submission(cleaned, note)


def approve_submission_service(submission_id: str) -> dict:
    submission = repositories.get_submission(submission_id)
    if submission is None:
        raise NotFoundError("submission not found")
    if submission["status"] != "pending":
        raise ValidationError("只有待审核（pending）的投稿可以批准")

    payload = _validate_submission_payload(submission["payload"])
    try:
        mentor, _ = repositories.find_or_create_person({
            "name": payload["mentor"]["name"],
            "homepage_url": payload["mentor"]["homepage_url"],
            "title": payload["mentor"]["title"],
            "public": False,
        })
        student, _ = repositories.find_or_create_person({
            "name": payload["student"]["name"],
            "homepage_url": payload["student"]["homepage_url"],
            "title": payload["student"]["title"],
            "public": False,
        })
        rel = payload["relationship"]
        mentorship = repositories.create_mentorship({
            "mentor_id": mentor["id"],
            "student_id": student["id"],
            "relationship_type": rel["relationship_type"],
            "start_year": rel["start_year"],
            "end_year": rel["end_year"],
            "institution": rel["institution"],
            "student_placement": rel["student_placement"],
            "evidence_url": rel["evidence_url"],
            "evidence_text": rel["evidence_text"],
            "confidence": rel["confidence"],
            "status": "verified",
            "public": False,
        })
        imported = {"mentorship_id": mentorship["id"], "duplicate": False}
        repositories.set_submission_status(submission_id, "approved", review_note="已导入本地图谱")
    except repositories.DuplicateMentorshipError:
        imported = {"mentorship_id": None, "duplicate": True}
        repositories.set_submission_status(submission_id, "approved", review_note="关系已存在，未重复导入")
    return {"submission": repositories.get_submission(submission_id), "imported": imported}


def reject_submission_service(submission_id: str, review_note: str | None = None) -> dict:
    submission = repositories.set_submission_status(
        submission_id, "rejected", review_note=(review_note or "").strip()[:1000] or None
    )
    if submission is None:
        raise NotFoundError("submission not found")
    return submission
