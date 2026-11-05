import json
import random

from database import (
    get_user, get_daily_challenge, insert_daily_challenge,
    get_recent_challenge_topics,
)
from .groq import GroqService


class ChallengeService:
    """Génération du défi d'apprentissage quotidien."""

    CHALLENGE_CATEGORIES = {
        "science": [
            "Recherche comment fonctionne la physique quantique",
            "Découvre les dernières avancées en biologie cellulaire",
            "Explore le concept de l'espace-temps",
            "Apprends comment fonctionne l'ADN",
            "Étudie le principe de la relativité",
        ],
        "technologie": [
            "Découvre ce qu'est le machine learning",
            "Explore les bases de la blockchain",
            "Apprends un nouveau langage de programmation",
            "Comprends comment fonctionne l'Internet",
            "Étudie les algorithmes de tri",
        ],
        "histoire": [
            "Découvre un événement historique majeur du 20e siècle",
            "Explore l'histoire d'une civilisation ancienne",
            "Apprends sur la révolution industrielle",
            "Étudie les causes d'une guerre mondiale",
            "Recherche l'histoire de ton pays",
        ],
        "art": [
            "Découvre un mouvement artistique",
            "Explore l'œuvre d'un artiste célèbre",
            "Apprends sur l'histoire de la musique classique",
            "Étudie les techniques de peinture",
            "Découvre l'architecture gothique",
        ],
        "philosophie": [
            "Explore un courant philosophique",
            "Lis sur Socrate et ses idées",
            "Découvre l'existentialisme",
            "Apprends sur l'éthique et la morale",
            "Étudie le stoïcisme",
        ],
        "langues": [
            "Apprends 10 nouveaux mots dans une langue étrangère",
            "Découvre l'origine d'expressions courantes",
            "Explore la linguistique",
            "Pratique la prononciation d'une nouvelle langue",
            "Étudie la grammaire d'une langue",
        ],
    }

    def __init__(self, groq_service: GroqService, profile_service=None):
        self.groq     = groq_service
        self.profiles = profile_service

    def get_or_generate(self, user_id, today: str) -> dict:
        existing = get_daily_challenge(today, user_id) if user_id else None
        if existing:
            full_text, category = existing[0], existing[1]
        else:
            full_text, category = self._generate(user_id)
            if user_id:
                insert_daily_challenge(full_text, category, today, user_id)

        if "\n\n" in full_text:
            title, explanation = full_text.split("\n\n", 1)
        elif "\n" in full_text:
            title, explanation = full_text.split("\n", 1)
        else:
            title, explanation = full_text, ""

        return {"title": title, "explanation": explanation, "category": category}

    def _generate(self, user_id) -> tuple:
        user = get_user(user_id) if user_id else None
        interests = []
        if user and user[8]:
            try:
                interests = json.loads(user[8])
            except Exception:
                pass

        if interests:
            category = random.choice(interests)
            interest_context = f"Centres d'intérêt : {', '.join(interests)}\nThème du jour : {category}"
        else:
            category = random.choice(list(self.CHALLENGE_CATEGORIES.keys()))
            interest_context = f"Catégorie : {category}"

        avoid_block = ""
        if user_id:
            recent = get_recent_challenge_topics(user_id, limit=7)
            if recent:
                avoid_block = "\nSujets récents à NE PAS répéter :\n" + "\n".join(f"- {t}" for t in recent)

        level  = user[5] if user else 1
        streak = user[2] if user else 0

        profile_block = ""
        if user_id and self.profiles:
            pb = self.profiles.prompt_block(user_id, topic=category)
            if pb:
                profile_block = f"\nProfil de l'apprenant (le défi doit lui être faisable et pertinent) :\n{pb}\n"

        try:
            prompt = f"""Crée un défi d'apprentissage unique et motivant.

{interest_context}
Niveau : {level}, Streak : {streak} jours
{profile_block}{avoid_block}

Le défi doit :
- Être précis, concret, réalisable en 15-30 minutes
- Être directement lié aux centres d'intérêt
- Être FAISABLE dans le contexte réel de l'apprenant : respecte ses contraintes, son âge, son statut et son niveau auto-évalué dans le thème (ni trop facile, ni hors de portée)
- Servir son objectif d'apprentissage s'il en a un, et privilégier ses formats préférés (pratique, lecture, vidéo...)
- Être original (pas générique)
- Susciter la curiosité

Réponds UNIQUEMENT avec :
Ligne 1 : Le défi (une phrase claire et engageante)
Ligne 2 : (vide)
Lignes suivantes : Explication (2-3 phrases) sur pourquoi c'est fascinant et comment commencer"""

            response = self.groq.chat(
                messages=[
                    {"role": "system", "content": "Tu es un expert en pédagogie créative. Tu crées des défis d'apprentissage personnalisés, originaux et jamais répétitifs."},
                    {"role": "user", "content": prompt},
                ],
                temperature=1.0,
                max_tokens=400,
            )
            return response.choices[0].message.content.strip(), category
        except Exception:
            fallback = (
                f"Explore un aspect avancé de {random.choice(interests)} pendant 20 minutes."
                if interests else random.choice(self.CHALLENGE_CATEGORIES[category])
            )
            return fallback, category
