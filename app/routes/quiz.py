from flask import Blueprint, request, jsonify, session
from app.services import quiz_service
from app.utils import login_required

bp = Blueprint("quiz", __name__)


_ALLOWED = {
    "size":        {"flash", "standard", "examen"},
    "difficulty":  {"enfant", "standard", "expert"},
    "qcm_type":    {"classique", "vrai_faux"},
    "num_options": {4, 5, 7},
}


def _quiz_config(data):
    try:
        num_options = int(data.get("num_options", 5))
    except (TypeError, ValueError):
        num_options = 5
    return {
        "size":        data.get("size") if data.get("size") in _ALLOWED["size"] else "flash",
        "difficulty":  data.get("difficulty") if data.get("difficulty") in _ALLOWED["difficulty"] else "standard",
        "qcm_type":    data.get("qcm_type") if data.get("qcm_type") in _ALLOWED["qcm_type"] else "classique",
        "num_options": num_options if num_options in _ALLOWED["num_options"] else 5,
        "multi":       bool(data.get("multi", False)),
    }


@bp.route("/api/quiz/generate", methods=["POST"])
@login_required
def quiz_generate():
    data = request.get_json() or {}
    result = quiz_service.generate(session["user_id"], data.get("topic", "").strip(), _quiz_config(data))
    if "error" in result:
        return jsonify({"error": result["error"]}), result["status"]
    result.pop("status")
    return jsonify(result)


@bp.route("/api/quiz/topics", methods=["GET"])
@login_required
def quiz_topics():
    result = quiz_service.suggest_topics(session["user_id"])
    if "error" in result:
        return jsonify({"error": result["error"]}), result["status"]
    result.pop("status")
    return jsonify(result)


@bp.route("/api/quiz/submit", methods=["POST"])
@login_required
def quiz_submit():
    data = request.get_json() or {}
    try:
        score = int(data.get("score", 0))
        total = int(data.get("total", 1))
    except (TypeError, ValueError):
        return jsonify({"error": "score et total doivent être des entiers"}), 400
    correct_questions = data.get("correct_questions") or []
    if not isinstance(correct_questions, list):
        correct_questions = []
    result = quiz_service.submit(
        session["user_id"],
        data.get("topic", "quiz"),
        score,
        total,
        correct_questions,
    )
    if "error" in result:
        return jsonify({"error": result["error"]}), result["status"]
    result.pop("status")
    return jsonify(result)
