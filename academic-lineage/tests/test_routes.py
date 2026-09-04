from app import create_app


def test_health_endpoint_returns_ok(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite")})
    response = app.test_client().get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_index_page_serves_management_page(app):
    response = app.test_client().get("/")
    assert response.status_code == 200
    assert "学术谱系" in response.get_data(as_text=True)


def test_create_person_deduplicates_by_homepage(app):
    client = app.test_client()
    first = client.post("/api/persons", json={
        "name": "Jane Doe", "homepage_url": "https://example.edu/jane",
        "institution": "Example University",
    })
    assert first.status_code == 201
    assert first.get_json()["created"] is True

    second = client.post("/api/persons", json={
        "name": "Jane Again", "homepage_url": "https://example.edu/jane/#bio",
    })
    assert second.status_code == 201
    body = second.get_json()
    assert body["created"] is False
    assert body["person"]["id"] == first.get_json()["person"]["id"]


def test_search_persons_matches_institution(app):
    client = app.test_client()
    client.post("/api/persons", json={
        "name": "Jane Doe", "homepage_url": "https://example.edu/jane",
        "institution": "Example University",
    })
    response = client.get("/api/persons?q=Example")
    assert response.status_code == 200
    assert any(p["name"] == "Jane Doe" for p in response.get_json()["persons"])


def test_create_person_requires_name(app):
    response = app.test_client().post("/api/persons", json={"homepage_url": "https://example.edu/x"})
    assert response.status_code == 400


def test_create_mentorship_preserves_mentor_student_direction(app):
    client = app.test_client()
    mentor = client.post("/api/persons", json={
        "name": "Mentor", "homepage_url": "https://example.edu/mentor"
    }).get_json()
    student = client.post("/api/persons", json={
        "name": "Student", "homepage_url": "https://example.edu/student"
    }).get_json()
    response = client.post("/api/mentorships", json={
        "mentor_id": mentor["person"]["id"],
        "student_id": student["person"]["id"],
        "relationship_type": "phd",
        "evidence_url": "https://example.edu/student",
        "status": "verified",
        "public": True,
    })
    assert response.status_code == 201
    body = response.get_json()
    assert body["mentorship"]["mentor_id"] == mentor["person"]["id"]
    assert body["mentorship"]["student_id"] == student["person"]["id"]


def test_duplicate_mentorship_returns_409(app):
    client = app.test_client()
    mentor = client.post("/api/persons", json={"name": "M", "homepage_url": "https://example.edu/m"}).get_json()
    student = client.post("/api/persons", json={"name": "S", "homepage_url": "https://example.edu/s"}).get_json()
    payload = {
        "mentor_id": mentor["person"]["id"],
        "student_id": student["person"]["id"],
        "relationship_type": "phd",
        "evidence_url": "https://example.edu/s",
    }
    created = client.post("/api/mentorships", json=payload)
    assert created.status_code == 201
    response = client.post("/api/mentorships", json=payload)
    assert response.status_code == 409
    body = response.get_json()
    assert body["existing"]["id"] == created.get_json()["mentorship"]["id"]
    assert body["existing"]["mentor_id"] == mentor["person"]["id"]
    assert body["existing"]["student_name"] == "S"


def test_lineage_endpoint_serves_upstream_chain(app):
    client = app.test_client()
    grand = client.post("/api/persons", json={"name": "Grand", "homepage_url": "https://example.edu/g"}).get_json()
    mentor = client.post("/api/persons", json={"name": "Mentor", "homepage_url": "https://example.edu/m"}).get_json()
    student = client.post("/api/persons", json={"name": "Student", "homepage_url": "https://example.edu/s"}).get_json()
    client.post("/api/mentorships", json={
        "mentor_id": grand["person"]["id"], "student_id": mentor["person"]["id"],
        "relationship_type": "phd", "evidence_url": "https://example.edu/m",
    })
    client.post("/api/mentorships", json={
        "mentor_id": mentor["person"]["id"], "student_id": student["person"]["id"],
        "relationship_type": "phd", "evidence_url": "https://example.edu/s",
    })
    response = client.get(f"/api/persons/{student['person']['id']}/lineage?up=3&down=1")
    assert response.status_code == 200
    body = response.get_json()
    assert body["center_id"] == student["person"]["id"]
    assert {n["id"] for n in body["nodes"]} == {grand["person"]["id"], mentor["person"]["id"], student["person"]["id"]}
    assert len(body["edges"]) == 2


def test_lineage_depth_over_10_returns_400(app):
    client = app.test_client()
    person = client.post("/api/persons", json={"name": "X", "homepage_url": "https://example.edu/x"}).get_json()
    response = client.get(f"/api/persons/{person['person']['id']}/lineage?up=11&down=2")
    assert response.status_code == 400


def test_patch_mentorship_updates_status_and_public(app):
    client = app.test_client()
    mentor = client.post("/api/persons", json={"name": "M", "homepage_url": "https://example.edu/m"}).get_json()
    student = client.post("/api/persons", json={"name": "S", "homepage_url": "https://example.edu/s"}).get_json()
    created = client.post("/api/mentorships", json={
        "mentor_id": mentor["person"]["id"], "student_id": student["person"]["id"],
        "relationship_type": "phd", "evidence_url": "https://example.edu/s",
    }).get_json()["mentorship"]

    response = client.patch(f"/api/mentorships/{created['id']}", json={
        "status": "verified", "public": True, "notes_private": "仅本地可见",
    })
    assert response.status_code == 200
    updated = response.get_json()["mentorship"]
    assert updated["status"] == "verified"
    assert updated["public"] is True
    assert updated["notes_private"] == "仅本地可见"


def test_patch_cannot_swap_direction(app):
    client = app.test_client()
    mentor = client.post("/api/persons", json={"name": "M", "homepage_url": "https://example.edu/m"}).get_json()
    student = client.post("/api/persons", json={"name": "S", "homepage_url": "https://example.edu/s"}).get_json()
    created = client.post("/api/mentorships", json={
        "mentor_id": mentor["person"]["id"], "student_id": student["person"]["id"],
        "relationship_type": "phd", "evidence_url": "https://example.edu/s",
    }).get_json()["mentorship"]

    response = client.patch(f"/api/mentorships/{created['id']}", json={"mentor_id": student["person"]["id"]})
    assert response.status_code == 400


def test_preview_person_rejects_missing_url(app):
    response = app.test_client().post("/api/preview-person", json={})
    assert response.status_code == 400


def test_preview_person_rejects_unsafe_url(app):
    response = app.test_client().post("/api/preview-person", json={"url": "file:///secret.txt"})
    assert response.status_code == 400


def test_unknown_person_lineage_returns_404(app):
    response = app.test_client().get("/api/persons/does-not-exist/lineage")
    assert response.status_code == 404


def test_list_persons_without_query_returns_all(app):
    client = app.test_client()
    client.post("/api/persons", json={"name": "A", "homepage_url": "https://example.edu/a"})
    client.post("/api/persons", json={"name": "B", "homepage_url": "https://example.edu/b"})
    response = client.get("/api/persons")
    assert response.status_code == 200
    assert len(response.get_json()["persons"]) == 2


def test_stats_endpoint_returns_counts(app):
    client = app.test_client()
    client.post("/api/persons", json={"name": "M", "homepage_url": "https://example.edu/m"})
    client.post("/api/persons", json={"name": "S", "homepage_url": "https://example.edu/s"})
    mentor = client.get("/api/persons?q=M").get_json()["persons"][0]
    student = client.get("/api/persons?q=S").get_json()["persons"][0]
    client.post("/api/mentorships", json={
        "mentor_id": mentor["id"], "student_id": student["id"],
        "relationship_type": "phd", "evidence_url": "https://example.edu/s",
    })
    response = client.get("/api/stats")
    assert response.status_code == 200
    assert response.get_json() == {"persons": 2, "mentorships": 1}


def test_list_persons_supports_institution_filter(app):
    client = app.test_client()
    client.post("/api/persons", json={"name": "A", "homepage_url": "https://example.edu/a", "institution": "NUS"})
    client.post("/api/persons", json={"name": "B", "homepage_url": "https://example.edu/b", "institution": "SMU"})
    response = client.get("/api/persons?institution=NUS")
    assert response.status_code == 200
    assert [p["name"] for p in response.get_json()["persons"]] == ["A"]


def test_list_persons_supports_year_filter(app):
    client = app.test_client()
    mentor = client.post("/api/persons", json={"name": "M", "homepage_url": "https://example.edu/m"}).get_json()
    s1 = client.post("/api/persons", json={"name": "S1", "homepage_url": "https://example.edu/s1"}).get_json()
    client.post("/api/persons", json={"name": "S2", "homepage_url": "https://example.edu/s2"})
    client.post("/api/mentorships", json={
        "mentor_id": mentor["person"]["id"], "student_id": s1["person"]["id"],
        "relationship_type": "phd", "evidence_url": "https://example.edu/s1",
        "start_year": 2018, "end_year": 2023,
    })
    response = client.get("/api/persons?start_year=2018")
    assert response.status_code == 200
    assert [p["name"] for p in response.get_json()["persons"]] == ["S1"]


def test_filters_endpoint_lists_options(app):
    client = app.test_client()
    client.post("/api/persons", json={
        "name": "A", "homepage_url": "https://example.edu/a",
        "institution": "NUS", "title": "Professor",
    })
    response = client.get("/api/filters")
    assert response.status_code == 200
    body = response.get_json()
    assert body["institutions"] == ["NUS"]
    assert body["titles"] == ["Professor"]
    assert body["start_years"] == []
    assert body["end_years"] == []


def test_network_endpoint_returns_nodes_and_edges(app):
    client = app.test_client()
    mentor = client.post("/api/persons", json={
        "name": "M", "homepage_url": "https://example.edu/m", "institution": "NUS",
    }).get_json()
    student = client.post("/api/persons", json={
        "name": "S", "homepage_url": "https://example.edu/s", "institution": "NUS",
    }).get_json()
    client.post("/api/mentorships", json={
        "mentor_id": mentor["person"]["id"], "student_id": student["person"]["id"],
        "relationship_type": "phd", "evidence_url": "https://example.edu/s",
    })
    response = client.get("/api/network?institution=NUS")
    assert response.status_code == 200
    body = response.get_json()
    assert {n["name"] for n in body["nodes"]} == {"M", "S"}
    assert len(body["edges"]) == 1

    response = client.get("/api/network?relationship_type=master")
    assert response.get_json()["edges"] == []


def test_mentorships_list_endpoint_supports_filters(app):
    client = app.test_client()
    mentor = client.post("/api/persons", json={"name": "M", "homepage_url": "https://example.edu/m"}).get_json()
    student = client.post("/api/persons", json={"name": "S", "homepage_url": "https://example.edu/s"}).get_json()
    client.post("/api/mentorships", json={
        "mentor_id": mentor["person"]["id"], "student_id": student["person"]["id"],
        "relationship_type": "phd", "evidence_url": "https://example.edu/s", "status": "verified",
    })
    response = client.get("/api/mentorships?status=verified")
    assert response.status_code == 200
    body = response.get_json()
    assert len(body["mentorships"]) == 1
    assert body["mentorships"][0]["student_name"] == "S"


def test_delete_person_endpoint_cascades(app):
    client = app.test_client()
    mentor = client.post("/api/persons", json={"name": "M", "homepage_url": "https://example.edu/m"}).get_json()
    student = client.post("/api/persons", json={"name": "S", "homepage_url": "https://example.edu/s"}).get_json()
    client.post("/api/mentorships", json={
        "mentor_id": mentor["person"]["id"], "student_id": student["person"]["id"],
        "relationship_type": "phd", "evidence_url": "https://example.edu/s",
    })
    response = client.delete(f"/api/persons/{mentor['person']['id']}")
    assert response.status_code == 200
    assert response.get_json()["relationships_removed"] == 1
    assert client.get(f"/api/persons/{mentor['person']['id']}").status_code == 404
    assert client.get("/api/mentorships").get_json()["mentorships"] == []
    assert client.delete(f"/api/persons/{mentor['person']['id']}").status_code == 404


def test_delete_mentorship_endpoint(app):
    client = app.test_client()
    mentor = client.post("/api/persons", json={"name": "M", "homepage_url": "https://example.edu/m"}).get_json()
    student = client.post("/api/persons", json={"name": "S", "homepage_url": "https://example.edu/s"}).get_json()
    created = client.post("/api/mentorships", json={
        "mentor_id": mentor["person"]["id"], "student_id": student["person"]["id"],
        "relationship_type": "phd", "evidence_url": "https://example.edu/s",
    }).get_json()["mentorship"]
    response = client.delete(f"/api/mentorships/{created['id']}")
    assert response.status_code == 200
    assert response.get_json() == {"deleted": True}
    assert client.get("/api/mentorships").get_json()["mentorships"] == []
    assert client.delete(f"/api/mentorships/{created['id']}").status_code == 404


SUBMISSION_PAYLOAD = {
    "mentor": {"name": "投稿导师", "homepage_url": "https://example.edu/sub-mentor", "title": "Professor"},
    "student": {"name": "投稿学生", "homepage_url": "https://example.edu/sub-student", "title": "PhD Student"},
    "relationship": {
        "relationship_type": "phd",
        "start_year": 2020,
        "end_year": 2024,
        "institution": "NUS",
        "evidence_url": "https://example.edu/sub-student",
        "evidence_text": "主页列出导师",
    },
}


def test_submission_approve_imports_relationship(app):
    client = app.test_client()
    created = client.post("/api/submissions", json={"payload": SUBMISSION_PAYLOAD, "submitter_note": "请审核"})
    assert created.status_code == 201
    submission_id = created.get_json()["submission"]["id"]
    assert created.get_json()["submission"]["status"] == "pending"

    pending = client.get("/api/submissions?status=pending").get_json()["submissions"]
    assert len(pending) == 1

    approved = client.post(f"/api/submissions/{submission_id}/approve")
    assert approved.status_code == 200
    body = approved.get_json()
    assert body["submission"]["status"] == "approved"
    assert body["imported"]["duplicate"] is False

    persons = client.get("/api/persons").get_json()["persons"]
    assert {p["name"] for p in persons} == {"投稿导师", "投稿学生"}
    rels = client.get("/api/mentorships").get_json()["mentorships"]
    assert len(rels) == 1
    assert rels[0]["status"] == "verified"
    assert rels[0]["public"] is False

    assert client.post(f"/api/submissions/{submission_id}/approve").status_code == 400


def test_submission_reject_and_delete(app):
    client = app.test_client()
    submission_id = client.post("/api/submissions", json={"payload": SUBMISSION_PAYLOAD}).get_json()["submission"]["id"]
    rejected = client.post(f"/api/submissions/{submission_id}/reject", json={"review_note": "证据不足"})
    assert rejected.status_code == 200
    assert rejected.get_json()["submission"]["status"] == "rejected"
    assert rejected.get_json()["submission"]["review_note"] == "证据不足"
    assert client.delete(f"/api/submissions/{submission_id}").status_code == 200
    assert client.get("/api/submissions").get_json()["submissions"] == []


def test_submission_rejects_identical_homepages(app):
    payload = {
        "mentor": {"name": "A", "homepage_url": "https://example.edu/a"},
        "student": {"name": "B", "homepage_url": "https://example.edu/a"},
        "relationship": {"relationship_type": "phd"},
    }
    response = app.test_client().post("/api/submissions", json={"payload": payload})
    assert response.status_code == 400


def test_submission_duplicate_relationship_marks_approved(app):
    client = app.test_client()
    mentor = client.post("/api/persons", json={"name": "投稿导师", "homepage_url": "https://example.edu/sub-mentor"}).get_json()
    student = client.post("/api/persons", json={"name": "投稿学生", "homepage_url": "https://example.edu/sub-student"}).get_json()
    client.post("/api/mentorships", json={
        "mentor_id": mentor["person"]["id"], "student_id": student["person"]["id"],
        "relationship_type": "phd", "evidence_url": "https://example.edu/sub-student",
    })
    submission_id = client.post("/api/submissions", json={"payload": SUBMISSION_PAYLOAD}).get_json()["submission"]["id"]
    approved = client.post(f"/api/submissions/{submission_id}/approve")
    assert approved.status_code == 200
    body = approved.get_json()
    assert body["imported"]["duplicate"] is True
    assert body["submission"]["status"] == "approved"


def test_create_person_stores_title_editorial_and_honors(app):
    client = app.test_client()
    response = client.post("/api/persons", json={
        "name": "张三",
        "homepage_url": "https://example.edu/zhang",
        "title": "教授",
        "editorial_roles": ["Journal of Finance, 编委", "Management Science, 副主编"],
        "honors": ["国家杰出青年科学基金（杰青）"],
    })
    assert response.status_code == 201
    person = response.get_json()["person"]
    assert person["title"] == "教授"
    assert person["editorial_roles"] == ["Journal of Finance, 编委", "Management Science, 副主编"]
    assert person["honors"] == ["国家杰出青年科学基金（杰青）"]


def test_patch_person_updates_identity_fields(app):
    client = app.test_client()
    created = client.post("/api/persons", json={
        "name": "Old Name", "homepage_url": "https://example.edu/x",
    }).get_json()["person"]
    response = client.patch(f"/api/persons/{created['id']}", json={
        "name": "New Name",
        "title": "Associate Professor",
        "editorial_roles": ["Review of Finance, Editorial Board"],
        "honors": ["长江学者"],
        "public": True,
    })
    assert response.status_code == 200
    person = response.get_json()["person"]
    assert person["name"] == "New Name"
    assert person["title"] == "Associate Professor"
    assert person["editorial_roles"] == ["Review of Finance, Editorial Board"]
    assert person["honors"] == ["长江学者"]
    assert person["public"] is True


def test_patch_person_rejects_homepage_change(app):
    client = app.test_client()
    created = client.post("/api/persons", json={
        "name": "X", "homepage_url": "https://example.edu/x",
    }).get_json()["person"]
    response = client.patch(f"/api/persons/{created['id']}", json={"homepage_url": "https://example.edu/y"})
    assert response.status_code == 400


def test_mentorship_stores_student_placement(app):
    client = app.test_client()
    mentor = client.post("/api/persons", json={"name": "M", "homepage_url": "https://example.edu/m"}).get_json()
    student = client.post("/api/persons", json={"name": "S", "homepage_url": "https://example.edu/s"}).get_json()
    response = client.post("/api/mentorships", json={
        "mentor_id": mentor["person"]["id"], "student_id": student["person"]["id"],
        "relationship_type": "phd", "evidence_url": "https://example.edu/s",
        "student_placement": "Assistant Professor, NUS",
    })
    assert response.status_code == 201
    assert response.get_json()["mentorship"]["student_placement"] == "Assistant Professor, NUS"
