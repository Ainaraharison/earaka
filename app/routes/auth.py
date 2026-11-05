from flask import Blueprint, request, jsonify, session, redirect, url_for
from app.services import user_service
from app.extensions import google_oauth

bp = Blueprint("auth", __name__)


@bp.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    result = user_service.register(
        data.get("username", "").strip(),
        data.get("email", "").strip().lower(),
        data.get("password", ""),
    )
    if "error" in result:
        return jsonify({"error": result["error"]}), result["status"]
    session["user_id"] = result["user_id"]
    session["username"] = result["username"]
    return jsonify({"message": "Inscription réussie!", "username": result["username"]})


@bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    result = user_service.login(
        data.get("email", "").strip().lower(),
        data.get("password", ""),
    )
    if "error" in result:
        return jsonify({"error": result["error"]}), result["status"]
    session["user_id"] = result["user_id"]
    session["username"] = result["username"]
    return jsonify({"message": "Connexion réussie!", "username": result["username"]})


@bp.route("/auth/google")
def google_login():
    if not google_oauth:
        return jsonify({"error": "Google OAuth non configuré"}), 501
    return google_oauth.authorize_redirect(url_for("auth.google_callback", _external=True))


@bp.route("/auth/google/callback")
def google_callback():
    if not google_oauth:
        return redirect("/?error=oauth_unavailable")
    try:
        token = google_oauth.authorize_access_token()
        userinfo = token.get("userinfo") or google_oauth.userinfo()
        result = user_service.login_or_create_google(
            userinfo["sub"],
            userinfo["email"].lower(),
            userinfo.get("name", userinfo["email"].split("@")[0]),
        )
        session["user_id"] = result["user_id"]
        session["username"] = result["username"]
    except Exception as e:
        print(f"Erreur Google OAuth: {e}")
        return redirect("/?error=oauth_failed")
    return redirect("/")


@bp.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Déconnexion réussie"})


@bp.route("/api/me")
def me():
    if "user_id" not in session:
        return jsonify({"logged_in": False})
    profile = user_service.get_profile(session["user_id"])
    if not profile:
        session.clear()
        return jsonify({"logged_in": False})
    return jsonify({"logged_in": True, **profile})
