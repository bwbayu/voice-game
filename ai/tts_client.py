"""
TTS abstraction layer.

Hierarchy:
    TTSClient          – abstract base class
    ├── TTSElevenLabsClient  – ElevenLabs TTS (default)

Calling TTSClient() returns a TTSElevenLabsClient by default.
"""
from __future__ import annotations

import os
import tempfile
import logging
from abc import ABC, abstractmethod

from dotenv import load_dotenv

load_dotenv()


# ── Base class ────────────────────────────────────────────────────────────────

class TTSClient(ABC):
    """
    Abstract base class for TTS backends.

    Calling ``TTSClient()`` returns a :class:`TTSElevenLabsClient` instance
    (factory behaviour via ``__new__``).
    To use a specific backend, instantiate it directly.
    """

    def __new__(cls, *args, **kwargs):
        # Factory: bare TTSClient() → ElevenLabs
        if cls is TTSClient:
            return super().__new__(TTSElevenLabsClient)
        return super().__new__(cls)

    @abstractmethod
    def speak(self, text: str, voice: str | None = None) -> str:
        """
        Generate speech for *text*.
        Returns the path to a named temporary audio file.

        The file is created with delete=False so it persists after close().
        The caller must delete it when audio playback is complete.

        voice: optional per-call override for the configured voice.
        """


# ── ElevenLabs backend (default) ──────────────────────────────────────────────

_EL_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
_EL_VOICE = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")  # "George"


class TTSElevenLabsClient(TTSClient):
    """
    Wraps ElevenLabs TTS.
    Returns the path to a temporary MP3 file containing the generated speech.
    """

    def __init__(
        self,
        voice_id: str | None = None,
        model: str | None = None,
    ):
        from elevenlabs.client import ElevenLabs  # lazy import

        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ELEVENLABS_API_KEY is not set. Add it to your .env file."
            )
        self._client = ElevenLabs(api_key=api_key)
        self._voice  = voice_id or _EL_VOICE
        self._model  = model    or _EL_MODEL
        logging.info(
            "TTSElevenLabsClient: initialised (voice=%s, model=%s).",
            self._voice, self._model,
        )

    def speak(self, text: str, voice: str | None = None) -> str:
        from elevenlabs import save  # lazy import

        if not text.strip():
            raise ValueError("TTSElevenLabsClient.speak: received empty text.")

        audio = self._client.text_to_speech.convert(
            voice_id=voice or self._voice,
            model_id=self._model,
            text=text,
            output_format="mp3_44100_128",
            voice_settings={
                "speed": 1.2,  # 0.7 - 1.2
            }
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        save(audio, tmp.name)
        logging.debug("TTSElevenLabsClient: wrote speech to %s", tmp.name)
        return tmp.name