import json
import hashlib
from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash

from database import (
    get_user, create_user as db_create_user,
    update_user_streak, update_user_points,
    insert_learning_log,
    get_user_by_email, get_user_by_google_id, set_user_google_id,
    update_user_interests,
)


class UserService:
    """Inscription, connexion, streak, points et intérêts utilisateur."""

    @staticmethod
    def _user_id_from_username(username: str) -> int:
        return int(hashlib.sha256(username.encode()).hexdigest()[:15], 16)

    @staticmethod
    def calculate_points(duration: int, streak: int) -> int:
        return duration * 10 + streak * 5

    @staticmethod
    def calculate_level(total_points: int) -> int:
        return max(1, int((total_points / 100) ** 0.5))

    def register(self, username: str, email: str, password: str) -> dict:
        if not username or len(username) < 2 or len(username) > 30:
            return {"error": "Nom d'utilisateur invalide (2-30 caractères)", "status": 400}
        if not email or "@" not in email:
            return {"error": "Email invalide", "status": 400}
        if not password or len(password) < 6:
            return {"error": "Mot de passe trop court (6 caractères minimum)", "status": 400}
        if get_user_by_email(email):
            return {"error": "Cet email est déjà utilisé", "status": 409}
        user_id = self._user_id_from_username(email)
        db_create_user(user_id, username, datetime.now().isoformat(),
                       email=email, password_hash=generate_password_hash(password))
        return {"user_id": user_id, "username": username, "status": 200}

    def login(self, email: str, password: str) -> dict:
        if not email or not password:
            return {"error": "Email et mot de passe requis", "status": 400}
        user = get_user_by_email(email)
        if not user:
            return {"error": "Email ou mot de passe incorrect", "status": 401}
        pwd_hash = user[10] if len(user) > 10 else None
        if not pwd_hash or not check_password_hash(pwd_hash, password):
            return {"error": "Email ou mot de passe incorrect", "status": 401}
        return {"user_id": user[0], "username": user[1], "status": 200}

    def login_or_create_google(self, google_id: str, email: str, name: str) -> dict:
        user = get_user_by_google_id(google_id)
        if not user:
            user = get_user_by_email(email)
            if user:
                set_user_google_id(user[0], google_id)
            else:
                user_id = self._user_id_from_username(f"google_{google_id}")
                db_create_user(user_id, name, datetime.now().isoformat(),
                               email=email, google_id=google_id)
                user = get_user(user_id)
        return {"user_id": user[0], "username": user[1]}

    def get_profile(self, user_id: int) -> dict:
        user = get_user(user_id)
        if not user:
            return None
        return {
            "username": user[1],
            "current_streak": user[2],
            "longest_streak": user[3],
            "total_points": user[4],
            "level": user[5],
            "interests": json.loads(user[8]) if user[8] else [],
        }

    def update_streak(self, user_id: int) -> int:
        user = get_user(user_id)
        if not user:
            return 0
        today = datetime.now().date()
        last_log_date = user[6]
        if last_log_date:
            last_date = datetime.fromisoformat(last_log_date).date()
            days_diff = (today - last_date).days
            new_streak = user[2] if days_diff == 0 else (user[2] + 1 if days_diff == 1 else 1)
        else:
            new_streak = 1
        new_longest = max(user[3], new_streak)
        update_user_streak(user_id, new_streak, new_longest, today.isoformat())
        return new_streak

    def log_session(self, user_id: int, subject: str, duration, description: str) -> dict:
        if not subject:
            return {"error": "Sujet requis", "status": 400}
        try:
            duration = int(duration)
        except (TypeError, ValueError):
            return {"error": "Durée invalide", "status": 400}
        if duration <= 0 or duration > 1440:
            return {"error": "Durée entre 1 et 1440 minutes", "status": 400}
        user = get_user(user_id)
        new_streak  = self.update_streak(user_id)
        points      = self.calculate_points(duration, new_streak)
        new_total   = user[4] + points
        new_level   = self.calculate_level(new_total)
        update_user_points(user_id, new_total, new_level)
        insert_learning_log(user_id, subject, description, duration, datetime.now().isoformat(), points)
        return {
            "subject": subject, "duration": duration, "points_earned": points,
            "streak": new_streak, "level": new_level, "total_points": new_total,
            "status": 200,
        }

    def update_interests(self, user_id: int, interests: list) -> dict:
        user = get_user(user_id)
        existing = json.loads(user[8]) if user and user[8] else []
        merged = list(dict.fromkeys(existing + interests))
        update_user_interests(user_id, json.dumps(merged))
        return {"interests": merged}

    def delete_interest(self, user_id: int, topic: str) -> dict:
        user = get_user(user_id)
        existing = json.loads(user[8]) if user and user[8] else []
        updated = [i for i in existing if i != topic]
        update_user_interests(user_id, json.dumps(updated))
        return {"interests": updated}
