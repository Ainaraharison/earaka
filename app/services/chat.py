import json

from .groq import GroqService


class ChatService:
    """Chat IA avec historique de conversation par utilisateur."""

    MAX_HISTORY = 20

    def __init__(self, groq_service: GroqService, profile_service=None):
        self.groq     = groq_service
        self.profiles = profile_service
        self._histories: dict = {}

    def reply(self, user_id: int, message: str, user) -> str:
        interests = []
        if user and user[8]:
            try:
                interests = json.loads(user[8])
            except Exception:
                pass

        if user:
            profile_block = ""
            if self.profiles:
                pb = self.profiles.prompt_block(user_id)
                if pb:
                    profile_block = f"\nProfil de l'utilisateur (adapte tes réponses à ce profil : niveau de détail, exemples, ton objectif et ses contraintes) :\n{pb}\n"
            user_context = f"""
L'utilisateur est connecté :
- Streak actuel : {user[2]} jours (meilleur : {user[3]} jours)
- Niveau {user[5]} avec {user[4]} points
- Centres d'intérêt : {', '.join(interests) if interests else 'pas encore définis'}
{profile_block}"""
            feature_guidance = """Section à suggérer selon le contexte (UNE seule, intégrée naturellement dans la phrase) :
- Dashboard → si l'utilisateur parle de sa progression ou ses résultats
- onglet Défi → si l'utilisateur cherche quoi apprendre aujourd'hui
- bouton Suggestion → si l'utilisateur veut une idée de sujet
- onglet Quiz → si l'utilisateur veut se tester
- Dashboard (badges) → si l'utilisateur parle de récompenses ou motivation
- onglet Logger → si l'utilisateur vient de finir une session
- onglet Profil (clic sur son nom en bas de la barre latérale) → si ses centres d'intérêt ne sont pas définis, si son profil est incomplet ou s'il veut modifier ses informations
- onglet Suggestions → si l'utilisateur cherche une idée entrepreneuriale ou éducative personnalisée
- onglet Classement → si l'utilisateur parle de classement ou compétition"""
        else:
            user_context = "\nL'utilisateur n'est pas encore connecté.\n"
            feature_guidance = "Invite-le à se connecter pour accéder à toutes les fonctionnalités."

        system_prompt = f"""Tu es un ami passionné d'apprentissage qui guide naturellement l'utilisateur.
{user_context}
{feature_guidance}

Comment répondre :
- Parle comme un ami : naturel, chaleureux, direct
- Utilise le profil pour personnaliser ta réponse sans le réciter mécaniquement
- Termine toujours par la section la plus pertinente, avec ce format exact :
  ╰ **[Nom de la section]** — courte description de ce qu'elle fait
- Utilise des emojis dans chaque réponse pour rendre la conversation agréable, mais de façon naturelle (pas à chaque mot)
- Sois concis par défaut (2-3 phrases), mais développe librement si l'utilisateur demande une explication, un conseil détaillé ou un sujet complexe"""

        history = self._histories.get(user_id, [])
        try:
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": message})
            response = self.groq.chat(messages=messages, temperature=0.7, max_tokens=400)
            reply = response.choices[0].message.content
        except Exception:
            reply = "😊 Je suis là pour t'aider ! Explore les différentes sections de l'app pour suivre ton apprentissage ! 📚"

        history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply},
        ]
        self._histories[user_id] = history[-self.MAX_HISTORY:]
        return reply
