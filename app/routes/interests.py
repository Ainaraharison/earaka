from flask import Blueprint, request, jsonify, session
from app.services import user_service
from app.utils import login_required

bp = Blueprint("interests", __name__)


@bp.route("/api/interests", methods=["POST"])
@login_required
def set_interests():
    data = request.get_json() or {}
    interests = data.get("interests", [])
    if isinstance(interests, str):
        interests = [i.strip() for i in interests.split(",") if i.strip()]
    if not interests:
        return jsonify({"error": "Au moins un centre d'intérêt requis"}), 400
    return jsonify(user_service.update_interests(session["user_id"], interests))


@bp.route("/api/interests/<path:topic>", methods=["DELETE"])
@login_required
def delete_interest(topic):
    return jsonify(user_service.delete_interest(session["user_id"], topic))
