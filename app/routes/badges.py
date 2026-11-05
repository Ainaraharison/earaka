from flask import Blueprint, jsonify, session
from app.services import badge_service
from app.utils import login_required

bp = Blueprint("badges", __name__)


@bp.route("/api/badges")
@login_required
def badges():
    return jsonify(badge_service.get_badges(session["user_id"]))
