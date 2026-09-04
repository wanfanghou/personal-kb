"""Whitelist-based public export of lineage data."""
import json
from datetime import datetime, timezone
from pathlib import Path


def export_public_data(connection, output_dir) -> dict:
    """Write public people/relationships/manifest JSON. Returns counts.

    Only persons with public=1 are exported. Only relationships with
    public=1, status='verified' and both endpoints public are exported.
    Private fields are never included (whitelist strategy).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    people = []
    for row in connection.execute(
        "SELECT * FROM persons WHERE public = 1 ORDER BY name"
    ):
        people.append({
            "id": row["id"],
            "name": row["name"],
            "name_en": row["name_en"],
            "aliases": json.loads(row["aliases_json"] or "[]"),
            "institution": row["institution"],
            "field": row["field"],
            "title": row["title"],
            "editorial_roles": json.loads(row["editorial_roles_json"] or "[]"),
            "honors": json.loads(row["honors_json"] or "[]"),
            "homepage_url": row["homepage_url"],
        })
    public_ids = {person["id"] for person in people}

    relationships = []
    for row in connection.execute(
        "SELECT * FROM mentorships WHERE public = 1 AND status = 'verified' "
        "ORDER BY mentor_id, student_id"
    ):
        if row["mentor_id"] not in public_ids or row["student_id"] not in public_ids:
            continue
        relationships.append({
            "id": row["id"],
            "mentor_id": row["mentor_id"],
            "student_id": row["student_id"],
            "relationship_type": row["relationship_type"],
            "start_year": row["start_year"],
            "end_year": row["end_year"],
            "institution": row["institution"],
            "student_placement": row["student_placement"],
            "evidence_url": row["evidence_url"],
            "evidence_text": row["evidence_text"],
            "confidence": row["confidence"],
            "status": row["status"],
        })

    payload = {"people": people, "relationships": relationships}
    for name, records in payload.items():
        (output_dir / f"{name}.json").write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "people_count": len(people),
        "relationship_count": len(relationships),
        "schema_version": 2,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"people": len(people), "relationships": len(relationships)}
