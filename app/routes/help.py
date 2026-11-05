from flask import Blueprint, request, jsonify, session
from database import get_user, insert_help_question
from app.utils import login_required

bp = Blueprint("help", __name__)


@bp.route("/api/help-question", methods=["POST"])
@login_required
def submit_help_question():
    data = request.json or {}
    question = data.get("question", "").strip()[:500]
    if not question:
        return jsonify({"error": "La question ne peut pas être vide"}), 400
    user = get_user(session["user_id"])
    insert_help_question(user[1] if user else "anonyme", question)
    return jsonify({"ok": True})
