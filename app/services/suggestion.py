import json
import random
from datetime import datetime

from database import execute_query, insert_suggestion, get_recent_suggestions
from .groq import GroqService


class SuggestionService:
    """Suggestions de sujets d'apprentissage personnalisées par IA."""

    def __init__(self, groq_service: GroqService, profile_service=None):
        self.groq     = groq_service
        self.profiles = profile_service

    def suggest(self, user_id: int, user) -> dict:
        interests = json.loads(user[8]) if user[8] else []
        if not interests:
            return {"error": "Définis d'abord tes centres d'intérêt", "status": 400}

        recent = execute_query(
            "SELECT subject FROM learning_logs WHERE user_id = {ph} ORDER BY log_date DESC LIMIT 5",
            (user_id,), fetch_all=True
        )
        recent_subjects  = [r[0] for r in recent] if recent else []
        past_suggestions = get_recent_suggestions(user_id, limit=10)
        all_to_avoid     = list(dict.fromkeys(past_suggestions + recent_subjects))
        avoid_block = (
            "\nSujets déjà proposés ou étudiés à NE PAS répéter :\n"
            + "\n".join(f"- {s}" for s in all_to_avoid)
            if all_to_avoid else ""
        )

        profile_block = ""
        if self.profiles:
            pb = self.profiles.prompt_block(user_id)
            if pb:
                profile_block = f"\nProfil de l'apprenant (adapte la suggestion à ce profil) :\n{pb}\n"

        try:
            prompt = f"""Suggère un sujet d'apprentissage précis et innovant pour quelqu'un qui s'intéresse à : {', '.join(interests)}.

Contexte :
- Niveau : {user[5]}
- Streak : {user[2]} jours
{profile_block}{avoid_block}

Donne UNE suggestion ORIGINALE :
1. Un sujet précis et actionnable (pas générique)
2. Adapté à son niveau
3. Différent des sujets déjà proposés ou étudiés
4. Courte explication (1-2 phrases) de pourquoi c'est intéressant
5. Un conseil pratique pour commencer

Format :
Sujet : [titre précis]
**Pourquoi** : [explication courte]

**Comment commencer** : [conseil pratique]"""

            response = self.groq.chat(
                messages=[
                    {"role": "system", "content": "Tu es un conseiller d'apprentissage expert. Tu donnes des suggestions précises, personnalisées et jamais répétitives."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.9,
                max_tokens=400,
            )
            suggestion = response.choices[0].message.content.strip()
            subject_line = next((l for l in suggestion.splitlines() if l.startswith("Sujet :")), None)
            subject_saved = subject_line.replace("Sujet :", "").strip() if subject_line else suggestion[:80]
            insert_suggestion(user_id, subject_saved, datetime.now().isoformat())
        except Exception:
            suggestion = f"Explore un aspect avancé de **{random.choice(interests)}** que tu n'as pas encore étudié."

        return {"suggestion": suggestion, "interests": interests, "recent": recent_subjects, "status": 200}
