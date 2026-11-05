import json
from datetime import date

from database import get_user_profile, update_user_profile

_TEXT_FIELDS = [
    "birth_date", "location", "bio", "goal", "goal_deadline", "status", "languages",
    # Profil d'idéation (générateur d'idées de l'onglet Suggestions)
    "skills_resources", "time_available", "personality", "constraints",
    "clarified_profile",
]
_MAX_LEN = {"bio": 600, "skills_resources": 400, "time_available": 400,
            "personality": 400, "constraints": 400, "clarified_profile": 2500}
_DEFAULT_MAX_LEN = 120
_DOMAIN_LEVELS = ("débutant", "intermédiaire", "avancé")
_COMPLETION_FIELDS = [
    "birth_date", "location", "bio", "goal", "goal_deadline", "status", "languages",
    "skills_resources", "time_available", "personality", "constraints",
    "learning_formats", "domain_levels",
]


class ProfileService:
    """Profil utilisateur persistant, réutilisé par les quiz et les suggestions."""

    def get(self, user_id: int) -> dict:
        profile = self._load(user_id)
        return {"profile": profile, "completion": self._completion(profile), "status": 200}

    def save(self, user_id: int, data: dict) -> dict:
        """Fusionne les champs fournis dans le profil existant.

        Seuls les champs présents dans `data` sont modifiés ; une valeur
        vide supprime le champ. Les champs absents sont préservés.
        """
        profile = self._load(user_id)
        for field in _TEXT_FIELDS:
            if field not in data:
                continue
            value = data.get(field)
            value = value.strip()[: _MAX_LEN.get(field, _DEFAULT_MAX_LEN)] if isinstance(value, str) else ""
            if value:
                profile[field] = value
            else:
                profile.pop(field, None)

        if "learning_formats" in data:
            formats = data.get("learning_formats")
            clean = [str(f).strip()[:40] for f in formats if str(f).strip()][:6] if isinstance(formats, list) else []
            if clean:
                profile["learning_formats"] = clean
            else:
                profile.pop("learning_formats", None)

        if "domain_levels" in data:
            levels = data.get("domain_levels")
            clean = {
                str(domain).strip()[:60]: str(level)
                for domain, level in list(levels.items())[:20]
                if str(level) in _DOMAIN_LEVELS and str(domain).strip()
            } if isinstance(levels, dict) else {}
            if clean:
                profile["domain_levels"] = clean
            else:
                profile.pop("domain_levels", None)

        update_user_profile(user_id, json.dumps(profile, ensure_ascii=False))
        return {"profile": profile, "completion": self._completion(profile), "status": 200}

    def load(self, user_id: int) -> dict:
        """Profil brut (dict) — pour les autres services."""
        return self._load(user_id)

    def prompt_block(self, user_id: int, topic: str = None) -> str:
        """Résumé du profil en lignes '- ...' pour enrichir un prompt LLM.

        Chaîne vide si le profil n'est pas rempli. Si un topic est fourni,
        seul le niveau auto-évalué du domaine correspondant est inclus.
        """
        p = self._load(user_id)
        if not p:
            return ""
        lines = []
        age = self._age(p.get("birth_date", ""))
        if age is not None:
            lines.append(f"Âge : {age} ans")
        if p.get("status"):
            lines.append(f"Statut : {p['status']}")
        if p.get("location"):
            lines.append(f"Lieu de résidence : {p['location']}")
        if p.get("goal"):
            goal = p["goal"]
            if p.get("goal_deadline"):
                goal += f" (horizon : {p['goal_deadline']})"
            lines.append(f"Objectif d'apprentissage : {goal}")
        if p.get("languages"):
            lines.append(f"Langues : {p['languages']}")
        if p.get("learning_formats"):
            lines.append("Formats d'apprentissage préférés : " + ", ".join(p["learning_formats"]))
        levels = p.get("domain_levels") or {}
        if topic and levels:
            topic_lower = topic.lower()
            for domain, level in levels.items():
                if domain.lower() in topic_lower or topic_lower in domain.lower():
                    lines.append(f"Niveau auto-évalué en {domain} : {level}")
                    break
        elif levels:
            lines.append("Niveaux auto-évalués : " + ", ".join(f"{d} ({l})" for d, l in levels.items()))
        if p.get("bio"):
            lines.append(f"À propos : {p['bio']}")
        return "\n".join(f"- {l}" for l in lines)

    # ── Interne ───────────────────────────────────────────────────────────────

    def _load(self, user_id: int) -> dict:
        raw = get_user_profile(user_id)
        try:
            profile = json.loads(raw) if raw else {}
            return profile if isinstance(profile, dict) else {}
        except (ValueError, TypeError):
            return {}

    @staticmethod
    def _completion(profile: dict) -> int:
        filled = sum(1 for f in _COMPLETION_FIELDS if profile.get(f))
        return round(100 * filled / len(_COMPLETION_FIELDS))

    @staticmethod
    def _age(birth_date: str):
        try:
            born = date.fromisoformat(birth_date)
        except (ValueError, TypeError):
            return None
        today = date.today()
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        return age if 0 < age < 120 else None
