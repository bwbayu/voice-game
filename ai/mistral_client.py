import os
import logging

from dotenv import load_dotenv
from mistralai import Mistral

from config import LLM_MODEL

load_dotenv()


class MistralClient:
    """
    Thin wrapper around the Mistral SDK for chat completion only.
    Realtime STT is handled separately inside RealtimeSTTWorker using
    its own Mistral client instance and the async audio API.
    """

    def __init__(self):
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "MISTRAL_API_KEY is not set. Add it to your .env file."
            )
        self._client = Mistral(api_key=api_key)
        self._api_key = api_key   # exposed so GameController can pass it to STT workers
        logging.info("MistralClient: initialised.")

    @property
    def api_key(self) -> str:
        return self._api_key

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """
        Call mistral-large-latest chat completion.
        Returns the assistant's text content.
        Raises on API error — callers should wrap in try/except.
        """
        response = self._client.chat.complete(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )
        return response.choices[0].message.content

    def parse(self, system_prompt: str, user_prompt: str,
              response_format, model: str | None = None,
              max_tokens: int = 128, temperature: float = 0) -> object:
        """
        Call client.chat.parse() with a Pydantic response_format.
        Returns the parsed Pydantic model instance.
        """
        _model = model or LLM_MODEL
        response = self._client.chat.parse(
            model=_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            response_format=response_format,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.parsed
