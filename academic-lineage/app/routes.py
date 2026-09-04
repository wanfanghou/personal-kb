"""HTTP API routes for the local lineage management app."""
from flask import Blueprint, jsonify, request

from . import repositories, services
from .db import get_db

bp = Blueprint("api", __name__, url_prefix="/api")


def _json_payload():
    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise services.ValidationError("request body must be a JSON object")
    return payload


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/stats")
def stats():
    db = get_db()
    return jsonify({
        "persons": db.execute("SELECT COUNT(*) AS c FROM persons").fetchone()["c"],
        "mentorships": db.execute("SELECT COUNT(*) AS c FROM mentorships").fetchone()["c"],
    })


@bp.post("/preview-person")
def preview_person():
    try:
        result = services.preview_person_service(_json_payload())
    except services.ValidationError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(result)


@bp.post("/persons")
def create_person():
    try:
        person, created = services.create_person_service(_json_payload())
    except services.ValidationError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({"person": person, "created": created}), 201


@bp.get("/persons")
def list_persons():
    query = (request.args.get("q") or "").strip()
    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        limit = 100
    filters = {
        "institution": request.args.get("institution"),
        "title": request.args.get("title"),
        "start_year": request.args.get("start_year"),
        "end_year": request.args.get("end_year"),
    }
    return jsonify({"persons": repositories.find_persons(query, limit, filters)})


@bp.get("/filters")
def filter_options():
    return jsonify(repositories.get_filter_options())


@bp.get("/network")
def network():
    filters = {
        key: request.args.get(key)
        for key in ("q", "institution", "title", "honor", "public",
                    "relationship_type", "start_year", "end_year")
    }
    return jsonify(repositories.get_network(filters))


@bp.get("/persons/<person_id>")
def get_person(person_id):
    person = repositories.get_person(person_id)
    if person is None:
        return jsonify({"error": "person not found"}), 404
    return jsonify({"person": person})


@bp.patch("/persons/<person_id>")
def update_person(person_id):
    try:
        person = services.update_person_service(person_id, _json_payload())
    except services.NotFoundError as error:
        return jsonify({"error": str(error)}), 404
    except services.ValidationError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({"person": person})


@bp.delete("/persons/<person_id>")
def delete_person(person_id):
    result = repositories.delete_person(person_id)
    if not result["deleted"]:
        return jsonify({"error": "person not found"}), 404
    return jsonify(result)


@bp.get("/persons/<person_id>/lineage")
def get_lineage(person_id):
    try:
        result = services.lineage_service(
            person_id,
            request.args.get("up", "3"),
            request.args.get("down", "2"),
        )
    except services.NotFoundError as error:
        return jsonify({"error": str(error)}), 404
    except services.ValidationError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(result)


@bp.get("/mentorships")
def list_mentorships():
    filters = {
        "q": request.args.get("q"),
        "status": request.args.get("status"),
        "relationship_type": request.args.get("relationship_type"),
    }
    return jsonify({"mentorships": repositories.list_mentorships(filters)})


@bp.post("/mentorships")
def create_mentorship():
    try:
        mentorship = services.create_mentorship_service(_json_payload())
    except services.DuplicateError as error:
        return jsonify({"error": str(error), "existing": error.existing}), 409
    except services.NotFoundError as error:
        return jsonify({"error": str(error)}), 404
    except services.ValidationError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({"mentorship": mentorship}), 201


@bp.get("/mentorships/<mentorship_id>")
def get_mentorship(mentorship_id):
    mentorship = repositories.get_mentorship(mentorship_id)
    if mentorship is None:
        return jsonify({"error": "mentorship not found"}), 404
    return jsonify({"mentorship": mentorship})


@bp.patch("/mentorships/<mentorship_id>")
def update_mentorship(mentorship_id):
    try:
        mentorship = services.update_mentorship_service(mentorship_id, _json_payload())
    except services.NotFoundError as error:
        return jsonify({"error": str(error)}), 404
    except services.ValidationError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({"mentorship": mentorship})


@bp.delete("/mentorships/<mentorship_id>")
def delete_mentorship(mentorship_id):
    deleted = repositories.delete_mentorship(mentorship_id)
    if not deleted:
        return jsonify({"error": "mentorship not found"}), 404
    return jsonify({"deleted": True})


@bp.post("/export/public")
def export_public():
    result = services.export_public_service()
    return jsonify(result)


@bp.post("/submissions")
def create_submission():
    try:
        payload = _json_payload()
        submission = services.create_submission_service(
            payload.get("payload"), payload.get("submitter_note")
        )
    except services.ValidationError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({"submission": submission}), 201


@bp.get("/submissions")
def list_submissions():
    status = (request.args.get("status") or "").strip() or None
    return jsonify({"submissions": repositories.list_submissions(status)})


@bp.get("/submissions/<submission_id>")
def get_submission(submission_id):
    submission = repositories.get_submission(submission_id)
    if submission is None:
        return jsonify({"error": "submission not found"}), 404
    return jsonify({"submission": submission})


@bp.post("/submissions/<submission_id>/approve")
def approve_submission(submission_id):
    try:
        result = services.approve_submission_service(submission_id)
    except services.NotFoundError as error:
        return jsonify({"error": str(error)}), 404
    except services.ValidationError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(result)


@bp.post("/submissions/<submission_id>/reject")
def reject_submission(submission_id):
    try:
        payload = _json_payload()
        submission = services.reject_submission_service(submission_id, payload.get("review_note"))
    except services.NotFoundError as error:
        return jsonify({"error": str(error)}), 404
    return jsonify({"submission": submission})


@bp.delete("/submissions/<submission_id>")
def delete_submission(submission_id):
    if not repositories.delete_submission(submission_id):
        return jsonify({"error": "submission not found"}), 404
    return jsonify({"deleted": True})
