from flask import Blueprint, request, jsonify, session
from database import get_user
from app.services import chat_service
from app.utils import login_required

bp = Blueprint("chat", __name__)


@bp.route("/api/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    if not message or len(message) > 1000:
        return jsonify({"error": "Message invalide"}), 400
    user_id = session["user_id"]
    return jsonify({"reply": chat_service.reply(user_id, message, get_user(user_id))})
