import pytest

from app.repositories import (
    create_mentorship,
    find_or_create_person,
    find_persons,
    get_lineage,
    normalize_homepage_url,
    update_mentorship,
)


def test_person_is_deduplicated_by_normalized_homepage(app):
    with app.app_context():
        first, created_first = find_or_create_person({
            "name": "Jane Doe",
            "homepage_url": "HTTPS://example.edu/jane/#bio",
        })
        second, created_second = find_or_create_person({
            "name": "Different Label",
            "homepage_url": "https://example.edu/jane",
        })
    assert created_first is True
    assert created_second is False
    assert first["id"] == second["id"]


def test_self_mentorship_is_rejected(app):
    with app.app_context():
        person, _ = find_or_create_person({"name": "Jane Doe", "homepage_url": "https://example.edu/jane"})
        with pytest.raises(ValueError, match="mentor and student must differ"):
            create_mentorship({
                "mentor_id": person["id"],
                "student_id": person["id"],
                "relationship_type": "phd",
                "evidence_url": "https://example.edu/jane",
            })


def test_duplicate_mentorship_is_rejected(app):
    with app.app_context():
        mentor, _ = find_or_create_person({"name": "M", "homepage_url": "https://example.edu/m"})
        student, _ = find_or_create_person({"name": "S", "homepage_url": "https://example.edu/s"})
        payload = {
            "mentor_id": mentor["id"],
            "student_id": student["id"],
            "relationship_type": "phd",
            "evidence_url": "https://example.edu/s",
        }
        create_mentorship(payload)
        with pytest.raises(ValueError, match="already exists"):
            create_mentorship(payload)


def test_mentorship_requires_evidence_url(app):
    with app.app_context():
        mentor, _ = find_or_create_person({"name": "M", "homepage_url": "https://example.edu/m"})
        student, _ = find_or_create_person({"name": "S", "homepage_url": "https://example.edu/s"})
        with pytest.raises(ValueError, match="evidence_url"):
            create_mentorship({
                "mentor_id": mentor["id"],
                "student_id": student["id"],
                "relationship_type": "phd",
            })


def test_mentorship_rejects_unknown_person(app):
    with app.app_context():
        mentor, _ = find_or_create_person({"name": "M", "homepage_url": "https://example.edu/m"})
        with pytest.raises(KeyError):
            create_mentorship({
                "mentor_id": mentor["id"],
                "student_id": "missing-id",
                "relationship_type": "phd",
                "evidence_url": "https://example.edu/m",
            })


def test_mentorship_rejects_invalid_years(app):
    with app.app_context():
        mentor, _ = find_or_create_person({"name": "M", "homepage_url": "https://example.edu/m"})
        student, _ = find_or_create_person({"name": "S", "homepage_url": "https://example.edu/s"})
        with pytest.raises(ValueError, match="earlier"):
            create_mentorship({
                "mentor_id": mentor["id"],
                "student_id": student["id"],
                "relationship_type": "phd",
                "evidence_url": "https://example.edu/s",
                "start_year": 2024,
                "end_year": 2020,
            })


def test_get_lineage_walks_upstream_mentors(app):
    with app.app_context():
        grand, _ = find_or_create_person({"name": "Grand", "homepage_url": "https://example.edu/g"})
        mentor, _ = find_or_create_person({"name": "Mentor", "homepage_url": "https://example.edu/m"})
        student, _ = find_or_create_person({"name": "Student", "homepage_url": "https://example.edu/s"})
        create_mentorship({"mentor_id": grand["id"], "student_id": mentor["id"],
                           "relationship_type": "phd", "evidence_url": "https://example.edu/m"})
        create_mentorship({"mentor_id": mentor["id"], "student_id": student["id"],
                           "relationship_type": "phd", "evidence_url": "https://example.edu/s"})
        result = get_lineage(student["id"], 3, 1)
    assert result["center_id"] == student["id"]
    assert {n["id"] for n in result["nodes"]} == {grand["id"], mentor["id"], student["id"]}
    assert len(result["edges"]) == 2


def test_get_lineage_clamps_depth_to_10(app):
    with app.app_context():
        person, _ = find_or_create_person({"name": "X", "homepage_url": "https://example.edu/x"})
        result = get_lineage(person["id"], 99, -5)
    assert result["up"] == 10
    assert result["down"] == 0


def test_update_mentorship_changes_only_allowed_fields(app):
    with app.app_context():
        mentor, _ = find_or_create_person({"name": "M", "homepage_url": "https://example.edu/m"})
        student, _ = find_or_create_person({"name": "S", "homepage_url": "https://example.edu/s"})
        created = create_mentorship({"mentor_id": mentor["id"], "student_id": student["id"],
                                     "relationship_type": "phd", "evidence_url": "https://example.edu/s"})
        updated = update_mentorship(created["id"], {"status": "verified", "public": True, "confidence": "probable"})
    assert updated["status"] == "verified"
    assert updated["public"] is True
    assert updated["confidence"] == "probable"
    assert updated["mentor_id"] == mentor["id"]


def test_normalize_url_drops_fragment_and_trailing_slash():
    assert normalize_homepage_url("HTTPS://Example.EDU/jane/#bio/") == "https://example.edu/jane"
    assert normalize_homepage_url("https://example.edu") == "https://example.edu"


def test_normalize_url_rejects_unsafe_scheme():
    with pytest.raises(ValueError, match="http or https"):
        normalize_homepage_url("file:///etc/passwd")


def test_search_matches_institution_and_alias(app):
    with app.app_context():
        find_or_create_person({
            "name": "张三",
            "homepage_url": "https://example.edu/zhang",
            "institution": "Example University",
            "aliases": ["San Zhang"],
        })
        results = find_persons("Example")
        assert any(p["name"] == "张三" for p in results)
        assert any(p["name"] == "张三" for p in find_persons("San Zhang"))
