import os
import tempfile
import logging

from dotenv import load_dotenv
from openai import OpenAI

from config import TTS_MODEL, TTS_VOICE, TTS_FORMAT

load_dotenv()


class TTSClient:
    """
    Wraps OpenAI TTS (tts-1).
    Returns the path to a temporary WAV file containing the generated speech.
    The caller is responsible for deleting the file when done with it.
    """

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set. Add it to your .env file."
            )
        self._client = OpenAI(api_key=api_key)
        logging.info("TTSClient: initialised.")

    def speak(self, text: str, voice: str | None = None) -> str:
        """
        Generate speech for text using OpenAI TTS.
        Returns the path to a named temporary WAV file.

        The file is created with delete=False so it persists after close().
        The caller must delete it when audio playback is complete.

        voice: optional override for the default TTS_VOICE (e.g. boss voices).
        """
        if not text.strip():
            raise ValueError("TTSClient.speak: received empty text.")

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()

        response = self._client.audio.speech.create(
            model=TTS_MODEL,
            voice=voice or TTS_VOICE,
            input=text,
            response_format=TTS_FORMAT,
        )
        response.stream_to_file(tmp.name)
        logging.debug(f"TTSClient: wrote speech to {tmp.name}")
        return tmp.name
