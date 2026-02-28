import logging
from pathlib import Path

import pygame

from config import AUDIO_DIR, BG_VOLUME

# pygame mixer channel assignments
_CH_TTS = 1   # one-shot TTS narration clips
_CH_SFX = 2   # short skill stingers (plays concurrently with TTS)


class AudioManager:
    """
    Manages two independent audio channels via pygame.mixer:
      - Background loop  : pygame.mixer.music (looping ambient track)
      - TTS clips        : pygame.mixer.Channel(_CH_TTS) (one-shot narration)

    All public methods are safe to call from the main Qt thread.
    pygame.mixer.init() is called once in __init__; never call it again.
    """

    def __init__(self):
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
        self._bg_track: str | None = None
        logging.info("AudioManager: pygame.mixer initialised.")

    # ── Background loop ───────────────────────────────────────────────────────

    def play_bg(self, track_name: str) -> None:
        """
        Load and loop audio/bg/{track_name}.mp3.
        Silently skips (with a warning) if the file does not exist.
        No-op if the same track is already playing.
        """
        path = AUDIO_DIR / f"{track_name}.mp3"
        if not path.exists():
            logging.warning(f"AudioManager: background track not found — {path}")
            return
        if self._bg_track == track_name and pygame.mixer.music.get_busy():
            return
        pygame.mixer.music.load(str(path))
        pygame.mixer.music.set_volume(BG_VOLUME)
        pygame.mixer.music.play(loops=-1)
        self._bg_track = track_name
        logging.debug(f"AudioManager: playing bg '{track_name}'")

    # ── TTS clip ──────────────────────────────────────────────────────────────

    def play_clip(self, file_path: str) -> None:
        """
        Load and play a one-shot WAV clip (TTS output) on the TTS channel.
        Stops any currently playing clip first.
        """
        ch = pygame.mixer.Channel(_CH_TTS)
        ch.stop()
        try:
            sound = pygame.mixer.Sound(file_path)
            ch.play(sound)
            logging.debug(f"AudioManager: playing clip '{file_path}'")
        except Exception as e:
            logging.error(f"AudioManager: failed to play clip '{file_path}': {e}")

    def play_sfx(self, file_path: str) -> None:
        """
        Play a short sound effect on the SFX channel without interrupting TTS.
        Used for boss skill stingers during combat.
        """
        ch = pygame.mixer.Channel(_CH_SFX)
        ch.stop()
        try:
            sound = pygame.mixer.Sound(file_path)
            ch.play(sound)
            logging.debug(f"AudioManager: playing sfx '{file_path}'")
        except Exception as e:
            logging.error(f"AudioManager: failed to play sfx '{file_path}': {e}")

    # ── Control ───────────────────────────────────────────────────────────────

    def stop_all(self) -> None:
        """Stop background music and any playing TTS clip."""
        pygame.mixer.music.stop()
        pygame.mixer.Channel(_CH_TTS).stop()
        self._bg_track = None

    def is_clip_playing(self) -> bool:
        return pygame.mixer.Channel(_CH_TTS).get_busy()
