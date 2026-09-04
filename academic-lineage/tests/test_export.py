import json

from app.db import get_db
from app.exporter import export_public_data
from app.repositories import create_mentorship, find_or_create_person


def test_public_export_filters_private_and_unverified_records(app, tmp_path):
    output = tmp_path / "data"
    with app.app_context():
        mentor, _ = find_or_create_person({
            "name": "Public Mentor",
            "homepage_url": "https://example.edu/mentor",
            "public": True,
        })
        student, _ = find_or_create_person({
            "name": "Public Student",
            "homepage_url": "https://example.edu/student",
            "public": True,
        })
        private_student, _ = find_or_create_person({
            "name": "Private Student",
            "homepage_url": "https://example.edu/private-student",
            "public": False,
        })
        create_mentorship({
            "mentor_id": mentor["id"], "student_id": student["id"],
            "relationship_type": "phd", "evidence_url": mentor["homepage_url"],
            "status": "verified", "public": True, "notes_private": "secret note",
        })
        create_mentorship({
            "mentor_id": mentor["id"], "student_id": private_student["id"],
            "relationship_type": "phd", "evidence_url": mentor["homepage_url"],
            "status": "draft", "public": True,
        })
        create_mentorship({
            "mentor_id": mentor["id"], "student_id": student["id"],
            "relationship_type": "master", "evidence_url": mentor["homepage_url"],
            "status": "verified", "public": False,
        })
        result = export_public_data(get_db(), output)

    people = json.loads((output / "people.json").read_text(encoding="utf-8"))
    relationships = json.loads((output / "relationships.json").read_text(encoding="utf-8"))
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))

    assert result["people"] == 2
    assert result["relationships"] == 1
    assert len(people) == 2
    assert all("notes_private" not in person for person in people)
    assert all(edge["status"] == "verified" for edge in relationships)
    assert "notes_private" not in relationships[0]
    assert manifest["people_count"] == 2
    assert manifest["relationship_count"] == 1
    assert manifest["schema_version"] == 1
    assert "generated_at" in manifest


def test_public_export_excludes_private_endpoint_edges(app, tmp_path):
    """An edge whose mentor is private is excluded even if the edge is public."""
    output = tmp_path / "data"
    with app.app_context():
        private_mentor, _ = find_or_create_person({
            "name": "Private Mentor",
            "homepage_url": "https://example.edu/pm",
            "public": False,
        })
        student, _ = find_or_create_person({
            "name": "Public Student",
            "homepage_url": "https://example.edu/ps",
            "public": True,
        })
        create_mentorship({
            "mentor_id": private_mentor["id"], "student_id": student["id"],
            "relationship_type": "phd", "evidence_url": private_mentor["homepage_url"],
            "status": "verified", "public": True,
        })
        result = export_public_data(get_db(), output)

    relationships = json.loads((output / "relationships.json").read_text(encoding="utf-8"))
    assert result["people"] == 1
    assert result["relationships"] == 0
    assert relationships == []
