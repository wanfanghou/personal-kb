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
            "title": "Professor",
            "editorial_roles": ["Journal of Finance, Editorial Board"],
            "honors": ["国家杰青"],
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
            "student_placement": "Assistant Professor, Stanford University",
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
    assert set(people[0]) == {
        "id", "name", "name_en", "aliases", "institution", "field",
        "title", "editorial_roles", "honors", "homepage_url",
    }
    assert all("student_placement" in edge for edge in relationships)
    assert relationships[0]["student_placement"] == "Assistant Professor, Stanford University"
    mentor_exported = next(p for p in people if p["name"] == "Public Mentor")
    assert mentor_exported["title"] == "Professor"
    assert mentor_exported["editorial_roles"] == ["Journal of Finance, Editorial Board"]
    assert mentor_exported["honors"] == ["国家杰青"]
    assert manifest["people_count"] == 2
    assert manifest["relationship_count"] == 1
    assert manifest["schema_version"] == 2
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
