import pytest

from app.repositories import (
    create_mentorship,
    delete_mentorship,
    delete_person,
    find_or_create_person,
    find_persons,
    get_filter_options,
    get_lineage,
    get_network,
    get_person,
    list_mentorships,
    normalize_homepage_url,
    update_mentorship,
    update_person,
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


def test_get_lineage_filters_by_relationship_type(app):
    with app.app_context():
        mentor, _ = find_or_create_person({"name": "M", "homepage_url": "https://example.edu/m"})
        student, _ = find_or_create_person({"name": "S", "homepage_url": "https://example.edu/s"})
        create_mentorship({"mentor_id": mentor["id"], "student_id": student["id"], "relationship_type": "master",
                           "evidence_url": "https://example.edu/s"})
        phd_only = get_lineage(student["id"], 3, 2, relationship_type="phd")
        all_types = get_lineage(student["id"], 3, 2)
    assert phd_only["edges"] == []
    assert {n["id"] for n in phd_only["nodes"]} == {student["id"]}
    assert len(all_types["edges"]) == 1


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


def test_update_person_round_trip(app):
    with app.app_context():
        person, _ = find_or_create_person({"name": "张三", "homepage_url": "https://example.edu/zhang"})
        updated = update_person(person["id"], {
            "name": "张三丰",
            "title": "教授",
            "editorial_roles": ["管理世界, 编委"],
            "honors": ["国家杰青"],
            "public": True,
        })
    assert updated["name"] == "张三丰"
    assert updated["title"] == "教授"
    assert updated["editorial_roles"] == ["管理世界, 编委"]
    assert updated["honors"] == ["国家杰青"]
    assert updated["public"] is True


def test_update_person_requires_name_if_provided(app):
    with app.app_context():
        person, _ = find_or_create_person({"name": "X", "homepage_url": "https://example.edu/x"})
        with pytest.raises(ValueError, match="name is required"):
            update_person(person["id"], {"name": "   "})


def test_filter_persons_by_institution_and_title(app):
    with app.app_context():
        find_or_create_person({"name": "A", "homepage_url": "https://example.edu/a",
                               "institution": "NUS", "title": "Professor"})
        find_or_create_person({"name": "B", "homepage_url": "https://example.edu/b",
                               "institution": "SMU", "title": "Assistant Professor"})
        find_or_create_person({"name": "C", "homepage_url": "https://example.edu/c",
                               "institution": "NUS", "title": "Assistant Professor"})
        by_institution = {p["name"] for p in find_persons("", filters={"institution": "NUS"})}
        by_title = {p["name"] for p in find_persons("", filters={"title": "Assistant Professor"})}
    assert by_institution == {"A", "C"}
    assert by_title == {"B", "C"}


def test_filter_persons_by_enrollment_and_graduation_year(app):
    with app.app_context():
        mentor, _ = find_or_create_person({"name": "M", "homepage_url": "https://example.edu/m"})
        s2015, _ = find_or_create_person({"name": "S2015", "homepage_url": "https://example.edu/s1"})
        s2018, _ = find_or_create_person({"name": "S2018", "homepage_url": "https://example.edu/s2"})
        create_mentorship({"mentor_id": mentor["id"], "student_id": s2015["id"], "relationship_type": "phd",
                           "evidence_url": "https://example.edu/s1", "start_year": 2015, "end_year": 2020})
        create_mentorship({"mentor_id": mentor["id"], "student_id": s2018["id"], "relationship_type": "phd",
                           "evidence_url": "https://example.edu/s2", "start_year": 2018, "end_year": 2023})
        by_start = {p["name"] for p in find_persons("", filters={"start_year": 2018})}
        by_end = {p["name"] for p in find_persons("", filters={"end_year": 2020})}
    assert by_start == {"S2018"}
    assert by_end == {"S2015"}


def test_get_filter_options_lists_distinct_values(app):
    with app.app_context():
        mentor, _ = find_or_create_person({"name": "M", "homepage_url": "https://example.edu/m",
                                           "institution": "NUS", "title": "Professor",
                                           "honors": ["国家杰青"]})
        student, _ = find_or_create_person({"name": "S", "homepage_url": "https://example.edu/s",
                                            "institution": "NUS"})
        create_mentorship({"mentor_id": mentor["id"], "student_id": student["id"], "relationship_type": "phd",
                           "evidence_url": "https://example.edu/s", "start_year": 2020, "end_year": 2025})
        options = get_filter_options()
    assert options["institutions"] == ["NUS"]
    assert options["titles"] == ["Professor"]
    assert options["honors"] == ["国家杰青"]
    assert options["start_years"] == [2020]
    assert options["end_years"] == [2025]
    assert "phd" in options["relationship_types"]


def test_get_network_filters_nodes_and_edges(app):
    with app.app_context():
        mentor, _ = find_or_create_person({"name": "M", "homepage_url": "https://example.edu/m",
                                           "institution": "NUS", "title": "Professor"})
        student, _ = find_or_create_person({"name": "S", "homepage_url": "https://example.edu/s",
                                            "institution": "NUS", "title": "PhD Student"})
        outsider, _ = find_or_create_person({"name": "O", "homepage_url": "https://example.edu/o",
                                             "institution": "SMU"})
        create_mentorship({"mentor_id": mentor["id"], "student_id": student["id"], "relationship_type": "phd",
                           "evidence_url": "https://example.edu/s", "start_year": 2020, "end_year": 2024})
        create_mentorship({"mentor_id": mentor["id"], "student_id": outsider["id"], "relationship_type": "master",
                           "evidence_url": "https://example.edu/o", "start_year": 2021})

        network = get_network({"institution": "NUS", "relationship_type": "phd"})
    names = {n["name"] for n in network["nodes"]}
    assert names == {"M", "S"}
    assert len(network["edges"]) == 1
    assert network["edges"][0]["relationship_type"] == "phd"


def test_list_mentorships_supports_status_filter(app):
    with app.app_context():
        mentor, _ = find_or_create_person({"name": "M", "homepage_url": "https://example.edu/m"})
        student, _ = find_or_create_person({"name": "S", "homepage_url": "https://example.edu/s"})
        create_mentorship({"mentor_id": mentor["id"], "student_id": student["id"], "relationship_type": "phd",
                           "evidence_url": "https://example.edu/s", "status": "verified"})
        create_mentorship({"mentor_id": mentor["id"], "student_id": student["id"], "relationship_type": "master",
                           "evidence_url": "https://example.edu/s", "status": "draft"})
        verified = list_mentorships({"status": "verified"})
        drafts = list_mentorships({"status": "draft"})
        by_name = list_mentorships({"q": "S"})
    assert len(verified) == 1
    assert verified[0]["student_name"] == "S"
    assert len(drafts) == 1
    assert len(by_name) == 2


def test_delete_person_cascades_relationships(app):
    with app.app_context():
        mentor, _ = find_or_create_person({"name": "M", "homepage_url": "https://example.edu/m"})
        student, _ = find_or_create_person({"name": "S", "homepage_url": "https://example.edu/s"})
        other, _ = find_or_create_person({"name": "O", "homepage_url": "https://example.edu/o"})
        create_mentorship({"mentor_id": mentor["id"], "student_id": student["id"], "relationship_type": "phd",
                           "evidence_url": "https://example.edu/s"})
        create_mentorship({"mentor_id": mentor["id"], "student_id": other["id"], "relationship_type": "master",
                           "evidence_url": "https://example.edu/o"})
        result = delete_person(mentor["id"])
        assert result["deleted"] is True
        assert result["relationships_removed"] == 2
        assert get_person(mentor["id"]) is None
        assert list_mentorships() == []
        assert delete_person(mentor["id"])["deleted"] is False


def test_delete_mentorship(app):
    with app.app_context():
        mentor, _ = find_or_create_person({"name": "M", "homepage_url": "https://example.edu/m"})
        student, _ = find_or_create_person({"name": "S", "homepage_url": "https://example.edu/s"})
        created = create_mentorship({"mentor_id": mentor["id"], "student_id": student["id"], "relationship_type": "phd",
                                     "evidence_url": "https://example.edu/s"})
        assert delete_mentorship(created["id"]) is True
        assert list_mentorships() == []
        assert delete_mentorship(created["id"]) is False
