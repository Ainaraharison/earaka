from datetime import datetime
from flask import Blueprint, jsonify, session
from app.services import challenge_service

bp = Blueprint("challenge", __name__)


@bp.route("/api/challenge")
def challenge():
    today = datetime.now().date().isoformat()
    return jsonify(challenge_service.get_or_generate(session.get("user_id"), today))
