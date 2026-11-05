import os

from .groq import GroqService
from .user import UserService
from .badge import BadgeService
from .challenge import ChallengeService
from .quiz import QuizService
from .chat import ChatService
from .suggestion import SuggestionService
from .profile import ProfileService
from .idea import IdeaService

groq_service       = GroqService(api_key=os.getenv("GROQ_API_KEY"))
user_service       = UserService()
badge_service      = BadgeService()
profile_service    = ProfileService()
challenge_service  = ChallengeService(groq_service, profile_service)
quiz_service       = QuizService(groq_service, badge_service, user_service, profile_service)
chat_service       = ChatService(groq_service, profile_service)
suggestion_service = SuggestionService(groq_service, profile_service)
idea_service       = IdeaService(groq_service, profile_service)
