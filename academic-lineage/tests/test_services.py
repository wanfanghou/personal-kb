import pytest

from app import services
from app.repositories import find_or_create_person


def test_lineage_service_rejects_depth_over_10(app):
    with app.app_context():
        person, _ = find_or_create_person({"name": "X", "homepage_url": "https://example.edu/x"})
        with pytest.raises(services.ValidationError):
            services.lineage_service(person["id"], up="11", down="2")
        with pytest.raises(services.ValidationError):
            services.lineage_service(person["id"], up="2", down="-1")


def test_create_mentorship_service_rejects_missing_ids(app):
    with pytest.raises(services.ValidationError, match="mentor_id"):
        with app.app_context():
            services.create_mentorship_service({"evidence_url": "https://example.edu/x"})


def test_create_mentorship_service_rejects_invalid_relationship_type(app):
    with app.app_context():
        mentor, _ = find_or_create_person({"name": "M", "homepage_url": "https://example.edu/m"})
        student, _ = find_or_create_person({"name": "S", "homepage_url": "https://example.edu/s"})
        with pytest.raises(services.ValidationError, match="relationship_type"):
            services.create_mentorship_service({
                "mentor_id": mentor["id"],
                "student_id": student["id"],
                "relationship_type": "boss",
                "evidence_url": "https://example.edu/s",
            })


def test_update_service_rejects_direction_swap(app):
    with app.app_context():
        mentor, _ = find_or_create_person({"name": "M", "homepage_url": "https://example.edu/m"})
        student, _ = find_or_create_person({"name": "S", "homepage_url": "https://example.edu/s"})
        created = services.create_mentorship_service({
            "mentor_id": mentor["id"],
            "student_id": student["id"],
            "relationship_type": "phd",
            "evidence_url": "https://example.edu/s",
        })
        with pytest.raises(services.ValidationError, match="not allowed"):
            services.update_mentorship_service(created["id"], {"mentor_id": student["id"]})
        unchanged = services.update_mentorship_service(created["id"], {})
        assert unchanged["mentor_id"] == mentor["id"]
        assert unchanged["student_id"] == student["id"]


def test_create_person_service_rejects_missing_name(app):
    with pytest.raises(services.ValidationError, match="name"):
        with app.app_context():
            services.create_person_service({"homepage_url": "https://example.edu/x"})


def test_mentorship_url_resolution_after_preview(app):
    """Mentorship can be created from homepage URLs of already saved persons."""
    with app.app_context():
        mentor, _ = find_or_create_person({"name": "M", "homepage_url": "https://example.edu/m"})
        student, _ = find_or_create_person({"name": "S", "homepage_url": "https://example.edu/s"})
        created = services.create_mentorship_service({
            "mentor_url": "https://example.edu/m",
            "student_url": "https://example.edu/s/#bio",
            "relationship_type": "master",
            "evidence_url": "https://example.edu/s",
        })
    assert created["mentor_id"] == mentor["id"]
    assert created["student_id"] == student["id"]
    assert created["relationship_type"] == "master"
