from groq import Groq


class GroqService:
    """Client Groq avec basculement automatique sur le modèle de secours."""

    PRIMARY_MODEL  = "openai/gpt-oss-120b"
    FALLBACK_MODEL = "openai/gpt-oss-20b"

    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)

    def chat(self, messages, temperature=0.7, max_tokens=500):
        last_error = None
        for model in (self.PRIMARY_MODEL, self.FALLBACK_MODEL):
            try:
                return self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                last_error = e
        raise last_error
