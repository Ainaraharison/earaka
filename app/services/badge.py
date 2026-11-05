from datetime import datetime

from database import (
    get_user, insert_badge, get_user_badges,
    count_user_logs, count_unique_subjects, execute_query,
)


class BadgeService:
    """Attribution et lecture des badges utilisateur."""

    BADGES = {
        "first_step":    {"name": "🌱 Premier Pas",           "description": "Première session loguée"},
        "week_warrior":  {"name": "🔥 Guerrier Hebdomadaire", "description": "7 jours consécutifs"},
        "month_master":  {"name": "🏆 Maître du Mois",        "description": "30 jours consécutifs"},
        "century":       {"name": "💯 Centurion",              "description": "100 sessions au total"},
        "explorer":      {"name": "🗺️ Explorateur",           "description": "Explorer 10 sujets différents"},
        "dedicated":     {"name": "⚡ Dédié",                  "description": "Atteindre le niveau 5"},
        "marathon":      {"name": "🎯 Marathon",               "description": "50 jours consécutifs"},
        "polymath":      {"name": "🧠 Polymathe",              "description": "Explorer 25 sujets différents"},
        "quiz_novice":   {"name": "🎓 Apprenti Quiz",          "description": "Réussir 5 quiz"},
        "quiz_expert":   {"name": "🏅 Expert Quiz",            "description": "Réussir 20 quiz"},
        "perfect_score": {"name": "💎 Score Parfait",          "description": "Obtenir 100% à un quiz"},
    }

    def check_and_award(self, user_id: int) -> list:
        user = get_user(user_id)
        if not user:
            return []
        earned_names = get_user_badges(user_id)
        checks = [
            (count_user_logs(user_id) == 1,           "first_step"),
            (int(user[2]) >= 7,                       "week_warrior"),
            (int(user[2]) >= 30,                      "month_master"),
            (int(user[2]) >= 50,                      "marathon"),
            (count_user_logs(user_id) >= 100,         "century"),
            (count_unique_subjects(user_id) >= 10,    "explorer"),
            (count_unique_subjects(user_id) >= 25,    "polymath"),
            (int(user[5]) >= 5,                       "dedicated"),
        ]
        now = datetime.now().isoformat()
        new_badges = []
        for condition, key in checks:
            if condition and self.BADGES[key]["name"] not in earned_names:
                new_badges.append(key)
                insert_badge(user_id, self.BADGES[key]["name"], self.BADGES[key]["description"], now)
        return new_badges

    def check_and_award_quiz(self, user_id: int, total_quizzes: int, perfect_scores: int) -> list:
        earned_names = get_user_badges(user_id)
        new_badges = []
        if total_quizzes >= 5  and self.BADGES["quiz_novice"]["name"]   not in earned_names:
            new_badges.append("quiz_novice")
        if total_quizzes >= 20 and self.BADGES["quiz_expert"]["name"]   not in earned_names:
            new_badges.append("quiz_expert")
        if perfect_scores >= 1 and self.BADGES["perfect_score"]["name"] not in earned_names:
            new_badges.append("perfect_score")
        now = datetime.now().isoformat()
        for key in new_badges:
            b = self.BADGES[key]
            insert_badge(user_id, b["name"], b["description"], now)
        return new_badges

    def get_badges(self, user_id: int) -> dict:
        earned = execute_query(
            "SELECT badge_name, badge_description, earned_date FROM badges WHERE user_id = {ph}",
            (user_id,), fetch_all=True
        ) or []
        earned_names = [b[0] for b in earned]
        return {
            "earned": [{"name": b[0], "description": b[1], "earned_date": b[2]} for b in earned],
            "locked": [{"name": v["name"], "description": v["description"]}
                       for v in self.BADGES.values() if v["name"] not in earned_names],
            "total": len(self.BADGES),
        }

    def badges_info(self, keys: list) -> list:
        return [{"name": self.BADGES[k]["name"], "description": self.BADGES[k]["description"]}
                for k in keys]
