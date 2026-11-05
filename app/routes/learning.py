from flask import Blueprint, request, jsonify, session
from database import get_user, execute_query
from app.services import user_service, badge_service
from app.utils import login_required

bp = Blueprint("learning", __name__)


@bp.route("/api/log", methods=["POST"])
@login_required
def log_session():
    data = request.get_json() or {}
    result = user_service.log_session(
        session["user_id"],
        data.get("subject", "").strip(),
        data.get("duration"),
        data.get("description", "").strip(),
    )
    if "error" in result:
        return jsonify({"error": result["error"]}), result["status"]
    result["new_badges"] = badge_service.badges_info(badge_service.check_and_award(session["user_id"]))
    result.pop("status")
    return jsonify(result)


@bp.route("/api/stats")
@login_required
def stats():
    user_id = session["user_id"]
    user = get_user(user_id)
    log_stats = execute_query(
        "SELECT COUNT(*), SUM(duration), COUNT(DISTINCT subject) FROM learning_logs WHERE user_id = {ph}",
        (user_id,), fetch_one=True
    )
    top_subjects = execute_query(
        "SELECT subject, COUNT(*) as count FROM learning_logs WHERE user_id = {ph} GROUP BY subject ORDER BY count DESC LIMIT 5",
        (user_id,), fetch_all=True
    ) or []
    badge_count_row = execute_query(
        "SELECT COUNT(*) FROM badges WHERE user_id = {ph}", (user_id,), fetch_one=True
    )
    return jsonify({
        "username":       session["username"],
        "current_streak": user[2],
        "longest_streak": user[3],
        "total_points":   user[4],
        "level":          user[5],
        "total_sessions": log_stats[0] if log_stats else 0,
        "total_minutes":  log_stats[1] if log_stats and log_stats[1] else 0,
        "unique_subjects": log_stats[2] if log_stats else 0,
        "badge_count":    badge_count_row[0] if badge_count_row else 0,
        "total_badges":   len(badge_service.BADGES),
        "top_subjects":   [{"subject": s[0], "count": s[1]} for s in top_subjects],
        "created_at":     user[7] if user[7] else None,
    })


@bp.route("/api/history")
@login_required
def history():
    user_id = session["user_id"]
    limit = min(int(request.args.get("limit", 10)), 50)
    logs = execute_query(
        "SELECT subject, description, duration, log_date, points_earned FROM learning_logs WHERE user_id = {ph} ORDER BY log_date DESC LIMIT {ph}",
        (user_id, limit), fetch_all=True
    ) or []
    return jsonify([
        {"subject": l[0], "description": l[1], "duration": l[2], "date": l[3], "points": l[4]}
        for l in logs
    ])


@bp.route("/api/leaderboard")
def leaderboard():
    rows = execute_query(
        "SELECT username, current_streak, longest_streak, total_points, level FROM users ORDER BY total_points DESC LIMIT 10",
        fetch_all=True
    ) or []
    return jsonify([
        {"username": r[0], "streak": r[1], "longest_streak": r[2], "points": r[3], "level": r[4]}
        for r in rows
    ])
