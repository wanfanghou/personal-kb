"""Persistence operations for persons, mentorships and source snapshots."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from .config import MAX_LINEAGE_DEPTH, MAX_URL_LENGTH, MIN_YEAR
from .db import get_db

RELATIONSHIP_TYPES = {"phd", "master", "postdoc", "informal", "other"}
CONFIDENCE_LEVELS = {"confirmed", "probable", "uncertain"}
MENTORSHIP_STATUSES = {"draft", "verified", "rejected"}

RELATIONSHIP_LABELS_ZH = {
    "phd": "博士导师",
    "master": "硕士导师",
    "postdoc": "博士后合作导师",
    "informal": "非正式指导",
    "other": "其他",
}


class DuplicateMentorshipError(ValueError):
    """Raised when the same (mentor, student, type) relationship already exists."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return str(uuid.uuid4())


def max_year() -> int:
    return datetime.now().year + 1


def normalize_homepage_url(url: str) -> str:
    """Normalize a homepage URL: lower scheme/host, drop fragment and trailing slash."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("homepage URL is required")
    url = url.strip()
    if len(url) > MAX_URL_LENGTH:
        raise ValueError(f"URL is too long (max {MAX_URL_LENGTH} characters)")
    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https"):
        raise ValueError("URL must use http or https")
    if not parts.netloc:
        raise ValueError("URL must include a hostname")
    if "@" in parts.netloc:
        raise ValueError("URL must not contain credentials")
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def validate_years(data: dict) -> None:
    top = max_year()
    for key in ("start_year", "end_year"):
        value = data.get(key)
        if value in (None, ""):
            continue
        try:
            year = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{key} must be an integer year")
        if not (MIN_YEAR <= year <= top):
            raise ValueError(f"{key} must be between {MIN_YEAR} and {top}")
    start, end = data.get("start_year"), data.get("end_year")
    if start not in (None, "") and end not in (None, "") and int(end) < int(start):
        raise ValueError("end_year must not be earlier than start_year")


def _person_to_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["public"] = bool(data["public"])
    data["aliases"] = json.loads(data.pop("aliases_json") or "[]")
    return data


def _mentorship_to_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["public"] = bool(data["public"])
    return data


def get_person(person_id: str) -> dict | None:
    row = get_db().execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
    return _person_to_dict(row) if row is not None else None


def get_person_by_url(url: str) -> dict | None:
    row = get_db().execute("SELECT * FROM persons WHERE homepage_url = ?", (url,)).fetchone()
    return _person_to_dict(row) if row is not None else None


def find_or_create_person(data: dict) -> tuple[dict, bool]:
    """Find a person by normalized homepage URL or create one. Returns (person, created)."""
    homepage_url = normalize_homepage_url(data["homepage_url"])
    db = get_db()
    row = db.execute("SELECT * FROM persons WHERE homepage_url = ?", (homepage_url,)).fetchone()
    if row is not None:
        return _person_to_dict(row), False

    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    person_id = new_id()
    timestamp = now_iso()
    db.execute(
        """
        INSERT INTO persons
            (id, name, name_en, aliases_json, institution, field,
             homepage_url, homepage_title, public, notes_private, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            person_id,
            name,
            data.get("name_en") or None,
            json.dumps(data.get("aliases") or [], ensure_ascii=False),
            data.get("institution") or None,
            data.get("field") or None,
            homepage_url,
            data.get("homepage_title") or None,
            1 if data.get("public") else 0,
            data.get("notes_private") or None,
            timestamp,
            timestamp,
        ),
    )
    db.commit()
    return get_person(person_id), True


def find_persons(query: str, limit: int = 50) -> list[dict]:
    query = (query or "").strip()
    if not query:
        return []
    db = get_db()
    pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    rows = db.execute(
        """
        SELECT * FROM persons
        WHERE name LIKE ? ESCAPE '\\'
           OR name_en LIKE ? ESCAPE '\\'
           OR institution LIKE ? ESCAPE '\\'
           OR aliases_json LIKE ? ESCAPE '\\'
        ORDER BY name
        LIMIT ?
        """,
        (pattern, pattern, pattern, pattern, max(1, min(int(limit), 100))),
    ).fetchall()
    return [_person_to_dict(row) for row in rows]


def get_mentorship(mentorship_id: str) -> dict | None:
    db = get_db()
    row = db.execute(
        """
        SELECT m.*, mentor.name AS mentor_name, mentor.homepage_url AS mentor_homepage_url,
               student.name AS student_name, student.homepage_url AS student_homepage_url
        FROM mentorships m
        JOIN persons mentor ON mentor.id = m.mentor_id
        JOIN persons student ON student.id = m.student_id
        WHERE m.id = ?
        """,
        (mentorship_id,),
    ).fetchone()
    return _mentorship_to_dict(row) if row is not None else None


def create_mentorship(data: dict) -> dict:
    db = get_db()
    mentor_id, student_id = data["mentor_id"], data["student_id"]
    if mentor_id == student_id:
        raise ValueError("mentor and student must differ")

    relationship_type = data.get("relationship_type") or "phd"
    if relationship_type not in RELATIONSHIP_TYPES:
        raise ValueError(f"invalid relationship_type: {relationship_type}")
    confidence = data.get("confidence") or "confirmed"
    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError(f"invalid confidence: {confidence}")
    status = data.get("status") or "draft"
    if status not in MENTORSHIP_STATUSES:
        raise ValueError(f"invalid status: {status}")

    evidence_url = (data.get("evidence_url") or "").strip()
    if not evidence_url:
        raise ValueError("evidence_url is required")
    validate_years(data)

    for pid in (mentor_id, student_id):
        if db.execute("SELECT 1 FROM persons WHERE id = ?", (pid,)).fetchone() is None:
            raise KeyError(f"person not found: {pid}")

    duplicate = db.execute(
        "SELECT id FROM mentorships WHERE mentor_id = ? AND student_id = ? AND relationship_type = ?",
        (mentor_id, student_id, relationship_type),
    ).fetchone()
    if duplicate is not None:
        raise DuplicateMentorshipError("identical mentorship already exists")

    mentorship_id = new_id()
    timestamp = now_iso()
    db.execute(
        """
        INSERT INTO mentorships
            (id, mentor_id, student_id, relationship_type, start_year, end_year,
             institution, evidence_url, evidence_text, confidence, status, public,
             notes_private, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            mentorship_id,
            mentor_id,
            student_id,
            relationship_type,
            data.get("start_year") or None,
            data.get("end_year") or None,
            data.get("institution") or None,
            evidence_url,
            data.get("evidence_text") or None,
            confidence,
            status,
            1 if data.get("public") else 0,
            data.get("notes_private") or None,
            timestamp,
            timestamp,
        ),
    )
    db.commit()
    return get_mentorship(mentorship_id)


UPDATABLE_FIELDS = {
    "status", "confidence", "start_year", "end_year", "institution",
    "evidence_url", "evidence_text", "public", "notes_private",
}


def update_mentorship(mentorship_id: str, fields: dict) -> dict | None:
    db = get_db()
    current = db.execute("SELECT * FROM mentorships WHERE id = ?", (mentorship_id,)).fetchone()
    if current is None:
        return None

    updates: dict = {}
    if "status" in fields:
        if fields["status"] not in MENTORSHIP_STATUSES:
            raise ValueError(f"invalid status: {fields['status']}")
        updates["status"] = fields["status"]
    if "confidence" in fields:
        if fields["confidence"] not in CONFIDENCE_LEVELS:
            raise ValueError(f"invalid confidence: {fields['confidence']}")
        updates["confidence"] = fields["confidence"]
    if "evidence_url" in fields:
        evidence_url = (fields["evidence_url"] or "").strip()
        if not evidence_url:
            raise ValueError("evidence_url is required")
        updates["evidence_url"] = evidence_url
    for key in ("evidence_text", "institution", "notes_private"):
        if key in fields:
            updates[key] = fields[key] or None
    if "public" in fields:
        updates["public"] = 1 if fields["public"] else 0
    if "start_year" in fields or "end_year" in fields:
        combined = {
            "start_year": current["start_year"],
            "end_year": current["end_year"],
        }
        if "start_year" in fields:
            combined["start_year"] = fields["start_year"]
        if "end_year" in fields:
            combined["end_year"] = fields["end_year"]
        validate_years(combined)
        if "start_year" in fields:
            updates["start_year"] = fields["start_year"] or None
        if "end_year" in fields:
            updates["end_year"] = fields["end_year"] or None

    if not updates:
        return get_mentorship(mentorship_id)

    updates["updated_at"] = now_iso()
    set_clause = ", ".join(f"{key} = ?" for key in updates)
    params = list(updates.values()) + [mentorship_id]
    db.execute(f"UPDATE mentorships SET {set_clause} WHERE id = ?", params)
    db.commit()
    return get_mentorship(mentorship_id)


def get_lineage(person_id: str, up: int, down: int) -> dict:
    """BFS lineage: mentors of the person (up generations) and students (down generations)."""
    db = get_db()
    up = max(0, min(int(up), MAX_LINEAGE_DEPTH))
    down = max(0, min(int(down), MAX_LINEAGE_DEPTH))
    center = get_person(person_id)
    if center is None:
        raise KeyError(f"person not found: {person_id}")

    nodes: dict[str, dict] = {center["id"]: center}
    edges: dict[str, dict] = {}

    def fetch_persons(ids) -> None:
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        rows = db.execute(
            f"SELECT * FROM persons WHERE id IN ({placeholders})", tuple(ids)
        ).fetchall()
        for row in rows:
            person = _person_to_dict(row)
            nodes.setdefault(person["id"], person)

    # Upward: mentors of the current frontier
    frontier = {person_id}
    for _ in range(up):
        if not frontier:
            break
        placeholders = ",".join("?" * len(frontier))
        rows = db.execute(
            f"SELECT * FROM mentorships WHERE student_id IN ({placeholders})",
            tuple(frontier),
        ).fetchall()
        next_frontier = set()
        for row in rows:
            edges[row["id"]] = _mentorship_to_dict(row)
            if row["mentor_id"] not in nodes:
                next_frontier.add(row["mentor_id"])
        fetch_persons(next_frontier)
        frontier = next_frontier

    # Downward: students of the current frontier
    frontier = {person_id}
    for _ in range(down):
        if not frontier:
            break
        placeholders = ",".join("?" * len(frontier))
        rows = db.execute(
            f"SELECT * FROM mentorships WHERE mentor_id IN ({placeholders})",
            tuple(frontier),
        ).fetchall()
        next_frontier = set()
        for row in rows:
            edges[row["id"]] = _mentorship_to_dict(row)
            if row["student_id"] not in nodes:
                next_frontier.add(row["student_id"])
        fetch_persons(next_frontier)
        frontier = next_frontier

    return {
        "center_id": person_id,
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "up": up,
        "down": down,
    }


def record_snapshot(person_id: str, snapshot: dict) -> dict:
    """Record minimal identifying info from a user-submitted URL fetch."""
    db = get_db()
    snapshot_id = new_id()
    db.execute(
        """
        INSERT INTO source_snapshots (id, person_id, url, title, description, fetched_at, http_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            person_id,
            snapshot["url"],
            snapshot.get("title"),
            snapshot.get("description"),
            now_iso(),
            snapshot.get("http_status"),
        ),
    )
    db.commit()
    return {"id": snapshot_id, "person_id": person_id}
