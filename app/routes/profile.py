from flask import Blueprint, request, jsonify, session
from app.services import profile_service
from app.utils import login_required

bp = Blueprint("profile", __name__)


@bp.route("/api/profile")
@login_required
def get_profile():
    result = profile_service.get(session["user_id"])
    result.pop("status")
    return jsonify(result)


@bp.route("/api/profile", methods=["PUT"])
@login_required
def save_profile():
    data = request.get_json() or {}
    result = profile_service.save(session["user_id"], data)
    result.pop("status")
    return jsonify(result)
