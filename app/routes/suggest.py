from flask import Blueprint, jsonify, request, session
from database import get_user
from app.services import suggestion_service, idea_service
from app.utils import login_required

bp = Blueprint("suggest", __name__)


@bp.route("/api/suggest")
@login_required
def suggest():
    user_id = session["user_id"]
    result = suggestion_service.suggest(user_id, get_user(user_id))
    if "error" in result:
        return jsonify({"error": result["error"]}), result["status"]
    result.pop("status")
    return jsonify(result)


# ── Générateur d'idées personnalisées (onglet Suggestions) ───────────────────

def _respond(result):
    if "error" in result:
        return jsonify({"error": result["error"]}), result["status"]
    result.pop("status")
    return jsonify(result)


@bp.route("/api/idea/clarify", methods=["POST"])
@login_required
def idea_clarify():
    data = request.get_json() or {}
    answers = data.get("answers")
    if not isinstance(answers, list):
        answers = None
    else:
        answers = [a for a in answers if isinstance(a, dict)][:3]
    return _respond(idea_service.clarify(session["user_id"], answers))


@bp.route("/api/idea/refine", methods=["POST"])
@login_required
def idea_refine():
    data = request.get_json() or {}
    clarified = str(data.get("clarified", ""))[:2500]
    correction = str(data.get("correction", "")).strip()[:400]
    if not correction:
        return jsonify({"error": "Correction vide"}), 400
    return _respond(idea_service.refine(session["user_id"], clarified, correction))


@bp.route("/api/idea/validate", methods=["POST"])
@login_required
def idea_validate():
    data = request.get_json() or {}
    return _respond(idea_service.validate(session["user_id"], str(data.get("clarified", ""))))


@bp.route("/api/idea/generate", methods=["POST"])
@login_required
def idea_generate():
    data = request.get_json() or {}
    idea_type = data.get("idea_type", "les_deux")
    return _respond(idea_service.generate(session["user_id"], idea_type))
