import json
from datetime import datetime

from database import get_user, insert_suggestion, get_recent_suggestions
from .groq import GroqService

_REQUIRED_FIELDS = {
    "skills_resources": "compétences & ressources",
    "time_available":   "temps disponible",
    "personality":      "personnalité & style de travail",
    "constraints":      "contraintes",
}

_IDEA_TYPES = {
    "entrepreneuriale": "entrepreneuriale",
    "educative":        "éducative",
    "les_deux":         "entrepreneuriale et/ou éducative",
}


class IdeaService:
    """Génération d'idées entrepreneuriales/éducatives personnalisées par profil.

    Flux : profil d'idéation → clarification (questions LLM) → synthèse d'un
    profil clarifié validé par l'utilisateur → génération d'idée → évaluation
    (pertinence, faisabilité, originalité) → régénération sans répétition.
    """

    def __init__(self, groq_service: GroqService, profile_service):
        self.groq     = groq_service
        self.profiles = profile_service

    # ── Étape 1 : clarification ──────────────────────────────────────────────

    def clarify(self, user_id: int, answers: list = None) -> dict:
        profile = self.profiles.load(user_id)
        missing = [label for f, label in _REQUIRED_FIELDS.items() if not profile.get(f)]
        if missing:
            return {"error": "Complète d'abord ton profil d'idéation : " + ", ".join(missing), "status": 400}

        general = self._general_block(user_id)
        if answers:
            clarified = self._synthesize(profile, answers, corrections=None, general=general)
            return {"clarified": clarified, "status": 200}

        response = self.groq.chat(
            messages=[{"role": "user", "content": self._questions_prompt(profile, general)}],
            temperature=0.3,
            max_tokens=300,
        )
        raw = response.choices[0].message.content.strip()
        questions = [l[2:].strip() for l in raw.splitlines() if l.strip().startswith("Q:")]
        if not questions or "COMPLET" in raw.upper():
            clarified = self._synthesize(profile, [], corrections=None, general=general)
            return {"clarified": clarified, "status": 200}
        return {"questions": questions[:3], "status": 200}

    def refine(self, user_id: int, clarified: str, correction: str) -> dict:
        """Re-synthétise le profil clarifié en tenant compte d'une correction utilisateur."""
        profile = self.profiles.load(user_id)
        new_clarified = self._synthesize(profile, [], corrections=[correction], previous=clarified,
                                         general=self._general_block(user_id))
        return {"clarified": new_clarified, "status": 200}

    def validate(self, user_id: int, clarified: str) -> dict:
        if not clarified or not clarified.strip():
            return {"error": "Profil clarifié vide", "status": 400}
        self.profiles.save(user_id, {"clarified_profile": clarified.strip()})
        return {"message": "Profil clarifié enregistré", "status": 200}

    # ── Étape 2 : génération + évaluation ────────────────────────────────────

    def generate(self, user_id: int, idea_type: str = "les_deux") -> dict:
        profile = self.profiles.load(user_id)
        clarified = profile.get("clarified_profile")
        if not clarified:
            missing = [label for f, label in _REQUIRED_FIELDS.items() if not profile.get(f)]
            if missing:
                return {"error": "Complète d'abord ton profil d'idéation : " + ", ".join(missing), "status": 400}
            clarified = self._profile_text(profile)

        # Le profil général est ajouté au moment de la génération (et non figé dans
        # le profil clarifié) pour toujours refléter l'onglet Profil à jour.
        general = self._general_block(user_id)
        if general:
            clarified = f"{clarified}\n\nProfil général (onglet Profil) :\n{general}"

        type_label     = _IDEA_TYPES.get(idea_type, _IDEA_TYPES["les_deux"])
        previous_ideas = get_recent_suggestions(user_id, limit=10, kind="idea")

        response = self.groq.chat(
            messages=[
                {"role": "system", "content": "Tu es un conseiller expert en entrepreneuriat et en apprentissage. Tes idées sont précises, personnalisées, réalistes et jamais génériques."},
                {"role": "user", "content": self._generation_prompt(clarified, type_label, previous_ideas)},
            ],
            temperature=0.9,
            max_tokens=700,
        )
        idea = response.choices[0].message.content.strip()

        idea_line = next((l for l in idea.splitlines() if l.startswith("Idée :")), None)
        title = (idea_line.replace("Idée :", "").strip().strip("*") if idea_line else idea[:80])
        insert_suggestion(user_id, title, datetime.now().isoformat(), kind="idea")

        evaluation = ""
        try:
            eval_response = self.groq.chat(
                messages=[{"role": "user", "content": self._evaluation_prompt(clarified, idea, previous_ideas)}],
                temperature=0.2,
                max_tokens=600,
            )
            evaluation = eval_response.choices[0].message.content.strip()
        except Exception:
            pass  # l'évaluation est un bonus : l'idée reste utilisable sans elle

        return {"idea": idea, "evaluation": evaluation, "status": 200}

    # ── Prompts ──────────────────────────────────────────────────────────────

    def _general_block(self, user_id: int) -> str:
        """Profil général (âge, statut, objectif, langues, niveaux, bio) + centres d'intérêt."""
        lines = self.profiles.prompt_block(user_id)
        user = get_user(user_id)
        try:
            interests = json.loads(user[8]) if user and user[8] else []
        except (ValueError, TypeError):
            interests = []
        if interests:
            interests_line = "- Centres d'intérêt : " + ", ".join(str(i) for i in interests)
            lines = f"{lines}\n{interests_line}" if lines else interests_line
        return lines

    @staticmethod
    def _profile_text(profile: dict) -> str:
        return f"""- Compétences et ressources : {profile.get('skills_resources', 'non précisé')}
- Temps disponible : {profile.get('time_available', 'non précisé')}
- Personnalité et style de travail : {profile.get('personality', 'non précisé')}
- Contraintes : {profile.get('constraints', 'non précisé')}
- Zone géographique : {profile.get('location', 'non précisée')}"""

    def _questions_prompt(self, profile: dict, general: str = "") -> str:
        general_block = f"\nProfil général déjà connu (ne repose AUCUNE question dont la réponse y figure) :\n{general}\n" if general else ""
        return f"""Tu prépares un profil utilisateur pour un générateur d'idées entrepreneuriales et éducatives.

Profil brut saisi par l'utilisateur :
{self._profile_text(profile)}
{general_block}
Identifie ce qui est vague, ambigu ou manquant et qui empêcherait de proposer une idée pertinente, faisable et originale (exemples : niveau réel des compétences, budget chiffré, objectif visé — revenu ou apprentissage, préférences de format, zone géographique trop vague ou marché cible non précisé...).

Si le profil est déjà assez précis, réponds exactement : COMPLET
Sinon, pose AU MAXIMUM 3 questions courtes et ciblées, une par ligne, au format strict :
Q: [question]
Ne pose jamais une question dont la réponse figure déjà dans le profil brut ou le profil général."""

    def _synthesize(self, profile: dict, answers: list, corrections: list = None, previous: str = None, general: str = "") -> str:
        qa_block = ""
        if answers:
            qa_block = "\nRéponses de clarification :\n" + "\n".join(
                f"- Q : {a.get('q', '')}\n  R : {a.get('a') or '(pas de réponse)'}" for a in answers
            )
        general_block = f"\nProfil général de l'utilisateur (contexte fiable, à intégrer là où c'est pertinent) :\n{general}\n" if general else ""
        previous_block = f"\nVersion précédente du profil clarifié :\n{previous}\n" if previous else ""
        corrections_block = ""
        if corrections:
            corrections_block = "\nCorrections demandées par l'utilisateur (prioritaires) :\n" + "\n".join(
                f"- {c}" for c in corrections
            )
        prompt = f"""Réécris le profil utilisateur ci-dessous en le clarifiant et en le complétant à partir des réponses de clarification.

Profil brut :
{self._profile_text(profile)}
{general_block}{qa_block}{previous_block}{corrections_block}

Règles :
1. Reste STRICTEMENT fidèle aux informations fournies — tu peux structurer, expliciter et déduire ce qui découle logiquement des réponses et du profil général, mais JAMAIS inventer des faits (pas de compétence, budget ou contrainte non mentionnés)
2. Si une réponse de clarification est vide, n'invente rien pour combler
3. Chaque champ doit être une description dense et précise en 1-2 phrases, directement exploitable par un générateur d'idées
4. Enrichis les champs avec le profil général quand c'est pertinent (ex : objectif et échéance dans les contraintes ou le temps, niveaux auto-évalués dans les compétences)

Réponds UNIQUEMENT dans ce format exact, sans rien avant ni après :
Compétences et ressources : [...]
Temps disponible : [...]
Personnalité et style de travail : [...]
Contraintes : [...]
Zone géographique : [...]"""
        response = self.groq.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()

    @staticmethod
    def _generation_prompt(clarified: str, type_label: str, previous_ideas: list) -> str:
        avoid_block = (
            "\nIdées déjà proposées à NE PAS répéter (ni sous une forme proche) :\n"
            + "\n".join(f"- {idea}" for idea in previous_ideas)
            if previous_ideas else ""
        )
        return f"""À partir du profil ci-dessous, propose UNE idée {type_label} précise, originale et réaliste.

Profil de l'utilisateur :
{clarified}
{avoid_block}
Exigences :
1. L'idée doit exploiter directement ses compétences et ressources actuelles
2. Elle doit être faisable dans le temps disponible indiqué
3. Elle doit correspondre à sa personnalité et son style de travail
4. Elle doit respecter TOUTES ses contraintes
5. Elle doit être ancrée dans sa zone géographique : réaliste pour le marché, l'infrastructure, le pouvoir d'achat et la réglementation de l'endroit (ou explicitement en ligne si c'est plus pertinent)
6. Pas d'idée générique (« lance un blog », « fais du dropshipping ») — sois spécifique
7. Elle doit servir son objectif principal et son échéance (si indiqués dans le profil général), et s'appuyer sur ses centres d'intérêt, ses niveaux auto-évalués, son âge et son statut

Format de réponse :
Idée : [titre précis en une ligne]

**Pourquoi c'est adapté à toi** : [2-3 phrases reliant l'idée au profil]

**Premier pas concret cette semaine** : [action réalisable en moins de 2 heures]

**Étapes sur 1 mois** : [3 étapes courtes et datées]

**Risque principal et parade** : [1 phrase]"""

    @staticmethod
    def _evaluation_prompt(clarified: str, idea: str, previous_ideas: list) -> str:
        already_seen = (
            "\nIdées déjà proposées lors des essais précédents (une idée trop proche de l'une d'elles doit perdre des points en originalité) :\n"
            + "\n".join(f"- {i}" for i in previous_ideas)
            if previous_ideas else ""
        )
        return f"""Tu es un évaluateur exigeant. Note la suggestion ci-dessous par rapport au profil fourni.

Profil :
{clarified}

Suggestion à évaluer :
---
{idea}
---
{already_seen}
Commence par 2-3 phrases d'analyse critique (points faibles d'abord), PUIS note chaque critère de 0 à 10 :
1. Pertinence (correspond vraiment au profil : compétences, personnalité, contraintes, objectif principal, centres d'intérêt et niveaux)
2. Faisabilité (réalisable avec le temps et les ressources disponibles, ET dans sa zone géographique : marché réel, infrastructure, pouvoir d'achat, réglementation locale)
3. Originalité (pas générique, apporte un angle nouveau DANS sa zone géographique)

Barème strict — utilise TOUTE l'échelle, ne te réfugie pas dans le 7/10 :
- 0-3 : faible (générique, hors profil ou irréaliste)
- 4-5 : moyen (correct mais sans relief, défauts notables)
- 6-7 : bon (solide, quelques faiblesses précises)
- 8-10 : excellent (rare — réserve ces notes aux idées remarquablement adaptées)

Format (respecte-le exactement) :
Analyse : [2-3 phrases critiques]
Pertinence : X/10 — [justification]
Faisabilité : X/10 — [justification]
Originalité : X/10 — [justification]
TOTAL : X/30
Verdict : [1 phrase — point fort principal et faiblesse principale]"""
