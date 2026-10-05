from flask import Blueprint, current_app, jsonify, request

from models import Lead, db

api_bp = Blueprint("api", __name__)


def _cors_origin() -> str | None:
    origin = request.headers.get("Origin")
    allowed = current_app.config.get("ALLOWED_LEAD_ORIGINS", [])
    if origin and (origin in allowed or "*" in allowed):
        return origin
    return None


@api_bp.after_request
def add_cors_headers(response):
    origin = _cors_origin()
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Api-Key"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return response


@api_bp.route("/api/leads", methods=["OPTIONS"])
def create_lead_preflight():
    return "", 204


@api_bp.route("/api/leads", methods=["POST"])
def create_lead():
    """Public endpoint the Fine Learning landing page form submits to.

    Protected by a shared key (sent as header X-Api-Key) rather than full
    auth, since the caller is an anonymous parent's browser. The key just
    has to match what's baked into the landing page; it keeps randos who
    find the URL from writing junk rows, it's not meant to be a strong
    secret.
    """
    expected_key = current_app.config.get("LEAD_API_KEY")
    if expected_key:
        provided_key = request.headers.get("X-Api-Key", "")
        if provided_key != expected_key:
            return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True) or request.form

    parent_name = (data.get("parent_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    email = (data.get("email") or "").strip()

    if not parent_name or not (phone or email):
        return jsonify({"error": "parent_name and at least one of phone/email are required"}), 400

    lead = Lead(
        parent_name=parent_name,
        phone=phone or None,
        email=email or None,
        child_name=(data.get("child_name") or "").strip() or None,
        year_group=(data.get("year_group") or "").strip() or None,
        subject_needed=(data.get("subject_needed") or "").strip() or None,
        source="landing_page",
        stage="new",
    )
    db.session.add(lead)
    db.session.commit()

    return jsonify({"status": "ok", "lead_id": lead.id}), 201
