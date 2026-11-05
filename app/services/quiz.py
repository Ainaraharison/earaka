import json
import random
from datetime import datetime

from database import get_user, update_user_points, execute_query, get_mastered_questions, insert_mastered_questions
from .groq import GroqService
from .badge import BadgeService
from .user import UserService

# Bloom distribution par niveau d'apprenant (repli si pas de difficulté choisie)
_BLOOM_BY_LEVEL = {
    "débutant":      ["mémorisation",  "mémorisation",  "compréhension"],
    "intermédiaire": ["compréhension", "application",   "analyse"],
    "avancé":        ["application",   "analyse",       "évaluation"],
}

# ── Options de configuration du QCM ──────────────────────────────────────────

_SIZES = {"flash": 6, "standard": 12, "examen": 20}

_DIFFICULTY_BLOOM = {
    "enfant":   ["mémorisation",  "mémorisation", "compréhension"],
    "standard": ["compréhension", "application",  "analyse"],
    "expert":   ["application",   "analyse",      "évaluation"],
}

_DIFFICULTY_AUDIENCE = {
    "enfant":   "des enfants de 8 à 12 ans — vocabulaire simple, phrases courtes, exemples concrets du quotidien",
    "standard": "le grand public — vocabulaire courant, niveau culture générale",
    "expert":   "des spécialistes du domaine — questions pointues, subtilités, cas limites et exceptions",
}

DEFAULT_CONFIG = {
    "size":        "flash",
    "difficulty":  "standard",
    "qcm_type":    "classique",
    "num_options": 5,
    "multi":       False,
}


def _level_label(level: int) -> str:
    if level <= 2:
        return "débutant"
    elif level <= 5:
        return "intermédiaire"
    return "avancé"


class QuizService:
    """Génération et soumission des quiz."""

    def __init__(self, groq_service: GroqService, badge_service: BadgeService, user_service: UserService, profile_service=None):
        self.groq     = groq_service
        self.badges   = badge_service
        self.user     = user_service
        self.profiles = profile_service

    # ── API publique ─────────────────────────────────────────────────────────

    def generate(self, user_id: int, topic: str, config: dict = None) -> dict:
        cfg = dict(DEFAULT_CONFIG)
        if config:
            cfg.update({k: v for k, v in config.items() if k in DEFAULT_CONFIG})
        if cfg["qcm_type"] == "vrai_faux":
            cfg["num_options"] = 2
            cfg["multi"] = False

        user = get_user(user_id)
        if not topic:
            interests = json.loads(user[8]) if user and user[8] else []
            if not interests:
                return {"error": "Spécifie un sujet ou définis tes centres d'intérêt", "status": 400}
            topic = random.choice(interests)

        level      = int(user[5]) if user else 1
        streak     = int(user[2]) if user else 0
        n          = _SIZES.get(cfg["size"], _SIZES["flash"])
        bloom_base = _DIFFICULTY_BLOOM.get(cfg["difficulty"]) or _BLOOM_BY_LEVEL[_level_label(level)]
        bloom_dist = [bloom_base[i % len(bloom_base)] for i in range(n)]
        mastered   = get_mastered_questions(user_id, topic)
        profile_block = self.profiles.prompt_block(user_id, topic) if self.profiles else ""

        try:
            response = self.groq.chat(
                messages=[
                    {"role": "system", "content": self._system_prompt(topic, cfg)},
                    {"role": "user",   "content": self._user_prompt(topic, level, streak, bloom_dist, cfg, mastered, profile_block)},
                ],
                temperature=0.8,
                max_tokens=min(500 + 230 * n, 7500),
            )
            content = response.choices[0].message.content.strip()
            for prefix in ("```json", "```"):
                if content.startswith(prefix):
                    content = content[len(prefix):]
            if content.endswith("```"):
                content = content[:-3]
            questions = json.loads(content.strip())
            questions = self._apply_confidence_filter(questions, topic, cfg)
            questions = self._reconcile_correct(questions, cfg)
            questions = self._verify_questions(questions, topic, cfg)
        except Exception:
            questions = [self._fallback_question(topic, cfg)]

        return {"topic": topic, "questions": questions, "config": cfg, "status": 200}

    def suggest_topics(self, user_id: int) -> dict:
        """Propose des sujets d'exercices adaptés au profil de l'apprenant."""
        user      = get_user(user_id)
        interests = json.loads(user[8]) if user and user[8] else []
        level     = int(user[5]) if user else 1
        profile_block = self.profiles.prompt_block(user_id) if self.profiles else ""

        recent = execute_query(
            "SELECT category FROM quiz_results WHERE user_id = {ph} ORDER BY quiz_date DESC LIMIT 10",
            (user_id,), fetch_all=True,
        )
        recent_topics = list(dict.fromkeys(r[0] for r in recent)) if recent else []

        context_lines = []
        if interests:
            context_lines.append("Centres d'intérêt : " + ", ".join(interests))
        context_lines.append(f"Niveau global : {level} ({_level_label(level)})")
        if profile_block:
            context_lines.append("Profil détaillé :\n" + profile_block)
        if recent_topics:
            context_lines.append(
                "Sujets de quiz déjà faits récemment (propose autre chose ou un approfondissement) : "
                + ", ".join(recent_topics)
            )

        prompt = f"""Voici le profil d'un apprenant :
{chr(10).join(context_lines)}

Propose exactement 6 sujets d'exercices (quiz) personnalisés pour cet apprenant :
- des sujets PRÉCIS et actionnables (pas « Mathématiques » mais « Les fractions : addition et comparaison »)
- adaptés à son niveau, ses centres d'intérêt et son objectif d'apprentissage
- variés : mélange approfondissements de ce qu'il connaît et découvertes proches de ses intérêts
- différents des sujets déjà faits récemment
- chaque "topic" fait moins de 60 caractères, chaque "why" est une phrase courte

Retourne UNIQUEMENT un tableau JSON de 6 objets, sans texte autour :
[{{"topic": "Sujet précis", "why": "Pourquoi ce sujet lui correspond"}}]"""

        try:
            response = self.groq.chat(
                messages=[
                    {"role": "system", "content": "Tu es un conseiller pédagogique expert. Tu réponds uniquement en JSON valide."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.9,
                max_tokens=700,
            )
            content = response.choices[0].message.content.strip()
            for prefix in ("```json", "```"):
                if content.startswith(prefix):
                    content = content[len(prefix):]
            if content.endswith("```"):
                content = content[:-3]
            raw = json.loads(content.strip())
            suggestions = [
                {"topic": str(s.get("topic", "")).strip()[:80], "why": str(s.get("why", "")).strip()[:200]}
                for s in raw if isinstance(s, dict) and str(s.get("topic", "")).strip()
            ][:6]
        except Exception:
            suggestions = []

        if not suggestions:
            suggestions = self._fallback_topics(user_id, interests)
        if not suggestions:
            return {"error": "Définis tes centres d'intérêt ou complète ton profil pour recevoir des suggestions", "status": 400}
        return {"suggestions": suggestions, "status": 200}

    def _fallback_topics(self, user_id: int, interests: list) -> list:
        """Suggestions sans LLM : centres d'intérêt + domaines auto-évalués du profil."""
        profile = self.profiles.load(user_id) if self.profiles else {}
        levels  = profile.get("domain_levels") or {}
        angles_by_level = {
            "débutant":      "Les bases de {d}",
            "intermédiaire": "Approfondir {d} : cas pratiques",
            "avancé":        "{d} : subtilités et cas limites",
        }
        seen, out = set(), []
        for domain, lvl in levels.items():
            topic = angles_by_level.get(lvl, "Les bases de {d}").format(d=domain)
            if domain.lower() not in seen:
                seen.add(domain.lower())
                out.append({"topic": topic[:80], "why": f"Basé sur ton niveau {lvl} en {domain}."})
        for it in interests:
            if it.lower() not in seen:
                seen.add(it.lower())
                out.append({"topic": f"L'essentiel de {it}"[:80], "why": "Basé sur tes centres d'intérêt."})
        random.shuffle(out)
        return out[:6]

    def submit(self, user_id: int, topic: str, score: int, total: int, correct_questions: list = None) -> dict:
        if total <= 0:
            return {"error": "Données invalides", "status": 400}
        score = max(0, min(score, total))
        user = get_user(user_id)
        percentage   = (score / total) * 100
        bonus        = 100 if percentage == 100 else (50 if percentage >= 66 else 0)
        total_earned = score * 50 + bonus
        new_total    = user[4] + total_earned
        new_level    = self.user.calculate_level(new_total)
        update_user_points(user_id, new_total, new_level)
        execute_query(
            "INSERT INTO quiz_results (user_id, category, score, total_questions, points_earned, quiz_date) VALUES ({ph},{ph},{ph},{ph},{ph},{ph})",
            (user_id, topic, score, total, total_earned, datetime.now().isoformat()),
        )
        qr = execute_query("SELECT COUNT(*) FROM quiz_results WHERE user_id = {ph}", (user_id,), fetch_one=True)
        pr = execute_query(
            "SELECT COUNT(*) FROM quiz_results WHERE user_id = {ph} AND score = total_questions",
            (user_id,), fetch_one=True
        )
        if correct_questions:
            insert_mastered_questions(user_id, topic, correct_questions)

        new_badge_keys = self.badges.check_and_award_quiz(
            user_id, qr[0] if qr else 0, pr[0] if pr else 0
        )
        return {
            "score": score, "total": total, "percentage": percentage,
            "points_earned": total_earned, "total_points": new_total, "level": new_level,
            "new_badges": self.badges.badges_info(new_badge_keys),
            "status": 200,
        }

    # ── Composante 1 : Rôle expert + domaine ─────────────────────────────────

    def _system_prompt(self, topic: str, cfg: dict) -> str:
        audience = _DIFFICULTY_AUDIENCE.get(cfg["difficulty"], _DIFFICULTY_AUDIENCE["standard"])
        return (
            f"Tu es un professeur expert en {topic}, spécialisé dans la conception "
            f"de QCM pédagogiques pour {audience}. "
            "Tu génères uniquement du JSON valide, sans aucun texte autour."
        )

    # ── Composante 2 : Format explicite ──────────────────────────────────────
    # ── Composante 3 : Guidelines de génération ──────────────────────────────

    def _user_prompt(self, topic: str, level: int, streak: int, bloom_dist: list, cfg: dict, mastered: list = None, profile_block: str = "") -> str:
        n           = len(bloom_dist)
        num_options = cfg["num_options"]
        vrai_faux   = cfg["qcm_type"] == "vrai_faux"
        multi       = cfg["multi"]

        bloom_lines = "\n".join(
            f"  - Question {i + 1} : niveau Bloom « {b} »"
            for i, b in enumerate(bloom_dist)
        )
        mastered_block = ""
        if mastered:
            lines = "\n".join(f'  - "{q}"' for q in mastered)
            mastered_block = f"\n━━ QUESTIONS DÉJÀ MAÎTRISÉES (ne pas répéter) ━━\nL'apprenant a déjà répondu correctement à ces questions. Ne génère pas de question identique ni de question portant sur le même sous-thème :\n{lines}\n"

        if vrai_faux:
            options_example = '["Vrai", "Faux"]'
            correct_example = "0"
            correct_text_line = '"correct_text": "Vrai",'
            correct_rule = (
                '2. UNE SEULE BONNE RÉPONSE : "correct" vaut 0 (Vrai) ou 1 (Faux). '
                "Chaque question est une AFFIRMATION à juger, factuellement vraie ou fausse sans ambiguïté — "
                "alterne les affirmations vraies et fausses."
            )
            type_note = "Chaque \"question\" est une affirmation commençant par « Vrai ou faux : »."
        elif multi:
            letters = ["A", "B", "C", "D", "E", "F", "G"][:num_options]
            options_example = "[" + ", ".join(f'"Option {l}"' for l in letters) + "]"
            correct_example = "[0, 2]"
            correct_text_line = '"correct_texts": ["Copie exacte du texte de chaque option correcte"],'
            correct_rule = (
                f'2. ENSEMBLE EXACT DE BONNES RÉPONSES : "correct" est un tableau de 1 à 3 indices (entre 0 et {num_options - 1}). '
                "Chaque index pointé est incontestablement exact, TOUTES les autres options sont factuellement fausses. "
                "Varie le nombre de bonnes réponses d'une question à l'autre."
            )
            type_note = f"QCM à réponses multiples : exactement {num_options} options par question."
        else:
            letters = ["A", "B", "C", "D", "E", "F", "G"][:num_options]
            options_example = "[" + ", ".join(f'"Option {l}"' for l in letters) + "]"
            correct_example = "0"
            correct_text_line = '"correct_text": "Copie exacte du texte de l\'option correcte",'
            correct_rule = (
                f'2. UNE SEULE BONNE RÉPONSE : "correct" est un entier entre 0 et {num_options - 1}, '
                "et la réponse correcte doit être incontestablement unique et factuellement vérifiable."
            )
            type_note = f"QCM classique : exactement {num_options} options par question."

        distractor_rules = "" if vrai_faux else f"""
1. DISTRACTEURS PLAUSIBLES : chaque mauvaise réponse doit sembler crédible pour quelqu'un qui maîtrise mal le sujet — pas de fausses réponses évidentes.
3. LONGUEUR HOMOGÈNE : les {num_options} options doivent avoir une longueur similaire pour ne pas trahir visuellement la bonne réponse.
4. PAS DE "TOUT CI-DESSUS" : n'utilise jamais les formulations "Toutes les réponses", "Aucune de ces réponses" ou équivalents."""

        return f"""Génère exactement {n} questions QCM sur : **{topic}**
{type_note}

━━ PROFIL APPRENANT ━━
• Niveau : {level}  |  Streak : {streak} jours
• Public cible : {_DIFFICULTY_AUDIENCE.get(cfg["difficulty"], _DIFFICULTY_AUDIENCE["standard"])}
{profile_block}

━━ RÉPARTITION BLOOM OBLIGATOIRE ━━
{bloom_lines}
{mastered_block}
━━ FORMAT DE SORTIE (JSON strict) ━━
Retourne un tableau JSON de {n} objets, chacun avec exactement ces champs :
[
  {{
    "question":    "Énoncé complet et précis de la question ?",
    "options":     {options_example},
    "correct":     {correct_example},
    {correct_text_line}
    "explanation": "Explication concise justifiant précisément la ou les options désignées par correct",
    "difficulty":  "facile",
    "bloom_level": "mémorisation",
    "confidence":  0.95
  }}
]
Valeurs autorisées pour "difficulty"  : facile | moyen | difficile
Valeurs autorisées pour "bloom_level" : mémorisation | compréhension | application | analyse | évaluation
"confidence" : nombre décimal entre 0.0 et 1.0 — ta certitude que "correct" désigne la ou les seules réponses factuellement exactes. Sois honnête : si tu n'es pas sûr à 70 % ou plus, mets une valeur inférieure à 0.7.

━━ RÈGLES QUALITÉ (obligatoires) ━━{distractor_rules}
{correct_rule}
5. COUVERTURE DES SOUS-THÈMES : les {n} questions doivent couvrir {n} sous-thèmes différents de {topic} — aucune répétition de concept.
6. COHÉRENCE RÉPONSE/EXPLICATION : "explanation" justifie exclusivement la ou les options désignées par "correct" — relis chaque question avant de la finaliser : si l'explication décrit une autre option, corrige "correct" pour qu'ils coïncident.
7. RÉFÉRENCE TEXTE : "correct_text" (ou "correct_texts") est la copie mot pour mot de la ou des options correctes, telle qu'écrite dans "options". C'est la référence : décide d'abord de la bonne réponse en texte, puis déduis-en l'index "correct"."""

    # ── Réconciliation texte → index (déterministe, sans LLM) ────────────────
    # Les LLM se trompent bien plus souvent d'index que de texte : la réponse
    # désignée en toutes lettres fait foi, l'index en est déduit localement.

    @staticmethod
    def _match_option(options: list, text) -> int:
        if not isinstance(text, str) or not text.strip():
            return -1
        t = text.strip().lower()
        for i, opt in enumerate(options):
            if str(opt).strip().lower() == t:
                return i
        candidates = [
            i for i, opt in enumerate(options)
            if t in str(opt).strip().lower() or str(opt).strip().lower() in t
        ]
        return candidates[0] if len(candidates) == 1 else -1

    def _reconcile_correct(self, questions: list, cfg: dict) -> list:
        for q in questions:
            if not isinstance(q, dict):
                continue
            options = q.get("options") or []
            texts = q.pop("correct_texts", None)
            single_text = q.pop("correct_text", None)
            if texts is None and single_text is not None:
                texts = [single_text]
            if not isinstance(texts, list) or not options:
                continue
            matched = [self._match_option(options, t) for t in texts]
            if any(i < 0 for i in matched) or not matched:
                continue  # texte introuvable : on garde l'index d'origine
            matched = sorted(set(matched))
            q["correct"] = matched if cfg["multi"] else matched[0]
        return questions

    # ── Vérification factuelle (2e appel LLM) ────────────────────────────────

    def _verify_questions(self, questions: list, topic: str, cfg: dict) -> list:
        if not questions:
            return questions
        if cfg["multi"]:
            answer_desc = '"correct_texts" : liste des textes EXACTS (copiés depuis "options") des seules réponses factuellement exactes'
            example = '[{"correct_texts": ["Texte option A"], "explanation": null}, {"correct_texts": ["Texte option B", "Texte option D"], "explanation": "Nouvelle explication..."}]'
        else:
            answer_desc = '"correct_text" : texte EXACT (copié depuis "options") de la seule réponse factuellement exacte'
            example = '[{"correct_text": "Texte option A", "explanation": null}, {"correct_text": "Texte option C", "explanation": "Nouvelle explication..."}]'
        questions_json = json.dumps(questions, ensure_ascii=False)
        prompt = (
            f"Tu es un correcteur factuel spécialisé en {topic}.\n"
            "Pour chaque question ci-dessous, l'index de la réponse donnée est dans \"correct\" (0 = première option). Vérifie deux choses :\n"
            "1. que cette réponse est bien la ou les seules factuellement exactes parmi les options ;\n"
            "2. que le champ \"explanation\" justifie bien CETTE réponse et non une autre option.\n"
            "Retourne UNIQUEMENT un tableau JSON d'objets, un par question et dans le même ordre :\n"
            f"- {answer_desc}\n"
            "- \"explanation\" : null si la réponse d'origine ET son explication sont correctes et cohérentes ; "
            "sinon, une explication concise (1-2 phrases) justifiant la réponse que tu retiens\n"
            f"Exemple pour 2 questions : {example}\n\n"
            f"Questions :\n{questions_json}"
        )
        try:
            response = self.groq.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200 + 120 * len(questions),
            )
            raw = response.choices[0].message.content.strip()
            for prefix in ("```json", "```"):
                if raw.startswith(prefix):
                    raw = raw[len(prefix):]
            if raw.endswith("```"):
                raw = raw[:-3]
            corrected = json.loads(raw.strip())
            if isinstance(corrected, list) and len(corrected) == len(questions):
                for q, item in zip(questions, corrected):
                    if not isinstance(item, dict) or not isinstance(q, dict):
                        continue
                    options = q.get("options") or []
                    texts = item.get("correct_texts")
                    if texts is None and item.get("correct_text") is not None:
                        texts = [item.get("correct_text")]
                    changed = False
                    if isinstance(texts, list) and texts and options:
                        matched = [self._match_option(options, t) for t in texts]
                        if matched and all(i >= 0 for i in matched):
                            matched = sorted(set(matched))
                            new_correct = matched if cfg["multi"] else matched[0]
                            changed = new_correct != q.get("correct")
                            q["correct"] = new_correct
                    new_expl = item.get("explanation")
                    if isinstance(new_expl, str) and new_expl.strip():
                        q["explanation"] = new_expl.strip()
                    elif changed:
                        # filet de sécurité : jamais d'explication qui contredit la réponse affichée
                        q["explanation"] = self._safe_explanation(q, cfg)
        except Exception:
            pass  # en cas d'échec, on garde les questions telles quelles
        return questions

    @staticmethod
    def _safe_explanation(q: dict, cfg: dict) -> str:
        options = q.get("options") or []
        try:
            if cfg["multi"]:
                labels = " ; ".join(f"« {options[i]} »" for i in q["correct"])
                return f"Après vérification, les bonnes réponses sont : {labels}."
            return f"Après vérification, la bonne réponse est « {options[q['correct']]} »."
        except (IndexError, KeyError, TypeError):
            return "Réponse vérifiée par le correcteur factuel."

    # ── Filtre de confiance ───────────────────────────────────────────────────

    _CONFIDENCE_THRESHOLD = 0.7

    def _apply_confidence_filter(self, questions: list, topic: str, cfg: dict) -> list:
        result = []
        for q in questions:
            confidence = q.pop("confidence", 1.0)
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = 1.0
            if confidence < self._CONFIDENCE_THRESHOLD:
                result.append(self._fallback_question(topic, cfg))
            else:
                result.append(q)
        return result

    # ── Fallback ──────────────────────────────────────────────────────────────

    def _fallback_question(self, topic: str, cfg: dict = None) -> dict:
        cfg = cfg or DEFAULT_CONFIG
        if cfg["qcm_type"] == "vrai_faux":
            return {
                "question": f"Vrai ou faux : progresser en {topic} demande une pratique régulière.",
                "options": ["Vrai", "Faux"],
                "correct": 0,
                "explanation": "La régularité est un principe fondamental de tout apprentissage.",
                "difficulty": "facile",
                "bloom_level": "mémorisation",
            }
        distractors = [
            f"Une définition incorrecte de {topic}",
            f"Un concept sans lien avec {topic}",
            f"Une confusion courante sur {topic}",
            f"Une idée reçue erronée sur {topic}",
            f"Un contresens fréquent sur {topic}",
            f"Une notion étrangère à {topic}",
        ]
        options = [f"Un principe de base de {topic}"] + distractors[:cfg["num_options"] - 1]
        return {
            "question": f"Quelle est une caractéristique fondamentale de {topic} ?",
            "options": options,
            "correct": [0] if cfg["multi"] else 0,
            "explanation": f"La première option décrit correctement un principe de {topic}.",
            "difficulty": "facile",
            "bloom_level": "mémorisation",
        }
