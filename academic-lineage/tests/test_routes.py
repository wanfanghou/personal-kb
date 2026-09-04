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
    assert client.post("/api/mentorships", json=payload).status_code == 201
    response = client.post("/api/mentorships", json=payload)
    assert response.status_code == 409


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
