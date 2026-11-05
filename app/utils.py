from functools import wraps
from flask import session, jsonify


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Non authentifié"}), 401
        return f(*args, **kwargs)
    return wrapper
