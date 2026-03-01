"""
STT abstraction layer.

Hierarchy:
    STTWorker          – abstract base class
    ├── ElevenLabsSTTWorker   – ElevenLabs Scribe v2 Realtime (default)
    ├── DeepgramSTTWorker     – Deepgram live transcription
    └── MistralSTTWorker      – Mistral realtime transcription (kept for reference)

Calling STTWorker() returns an ElevenLabsSTTWorker by default.
To use other backends, instantiate them directly:
    - DeepgramSTTWorker(stop_event)
    - MistralSTTWorker(api_key, stop_event)

Usage (default — ElevenLabs):
    stop_event = threading.Event()
    worker = STTWorker(stop_event)
    worker.transcript_delta.connect(...)   # live partial transcript (set semantics)
    worker.transcript_ready.connect(...)   # final transcript
    worker.error.connect(...)
    worker.start()
    # ... when Space released:
    stop_event.set()
"""

from __future__ import annotations

import asyncio
import threading
from abc import ABC, ABCMeta, abstractmethod

from PyQt6.QtCore import QThread, pyqtSignal

from config import CHUNK_DURATION_MS, SAMPLE_RATE, STT_MODEL


# ── Metaclass resolver ─────────────────────────────────────────────────────────

class ABCQThreadMeta(ABCMeta, type(QThread)):
    """Resolves metaclass conflict between ABCMeta and Qt's metaclass."""
    pass


# ── Base class ────────────────────────────────────────────────────────────────

class STTWorker(QThread, ABC, metaclass=ABCQThreadMeta):
    """
    Abstract base class for STT backends.

    Calling ``STTWorker(stop_event)`` returns an :class:`ElevenLabsSTTWorker` instance
    (factory behaviour via ``__new__``).
    To use a specific backend, instantiate it directly.
    """

    transcript_delta = pyqtSignal(str)   # live partial text for UI display
    transcript_ready = pyqtSignal(str)   # final complete transcript
    error            = pyqtSignal(str)

    def __new__(cls, stop_event: threading.Event, *args, **kwargs):
        # Factory: bare STTWorker(stop_event) → ElevenLabs (default)
        if cls is STTWorker:
            return super().__new__(ElevenLabsSTTWorker)
        return super().__new__(cls)

    @abstractmethod
    def run(self) -> None:
        """
        Main thread entry point. Must emit transcript_delta, transcript_ready, or error.
        """


# ── Deepgram backend (default) ────────────────────────────────────────────────

class DeepgramSTTWorker(STTWorker):
    """
    Streams microphone audio to Deepgram live transcription (SDK v6).

    Lifecycle:
      1. Instantiated and started when the player presses Space.
      2. Opens `dg.listen.v1.connect(...)` as a context manager.
      3. A daemon sub-thread runs `connection.start_listening()` (blocking receive loop).
      4. run() main loop reads mic chunks and sends via `connection.send_media()`.
      5. When stop_event is set (Space released), stops sending, calls
         `send_finalize()` so Deepgram can emit final transcripts, then
         `send_close_stream()` to close the WebSocket.
      6. Accumulated is_final=True transcripts are emitted via transcript_ready.

    transcript_delta carries the latest non-final partial (set semantics, not append).
    """

    transcript_delta = pyqtSignal(str)   # latest partial text for live display
    transcript_ready = pyqtSignal(str)   # final complete transcript on done
    error            = pyqtSignal(str)

    def __init__(self, stop_event: threading.Event):
        super().__init__()
        self._stop_event = stop_event
        self._final_text = ""

    def run(self) -> None:
        import pyaudio
        from deepgram import DeepgramClient
        from deepgram.core.events import EventType

        dg = DeepgramClient()   # reads DEEPGRAM_API_KEY from env
        p  = None

        try:
            with dg.listen.v1.connect(
                model="nova-3",
                language="en-US",
                encoding="linear16",   # PCM 16-bit little-endian — matches paInt16
                sample_rate=SAMPLE_RATE,
                channels=1,
                interim_results="true",   # must be lowercase string — Deepgram rejects Python True
                endpointing=300,
            ) as conn:

                def on_message(message) -> None:
                    if getattr(message, "type", "") != "Results":
                        return
                    channel = getattr(message, "channel", None)
                    alts    = getattr(channel, "alternatives", []) if channel else []
                    text    = (alts[0].transcript if alts else "") or ""
                    if not text:
                        return
                    if getattr(message, "is_final", False):
                        self._final_text += text + " "
                    else:
                        self.transcript_delta.emit(text)

                conn.on(EventType.MESSAGE, on_message)
                conn.on(EventType.ERROR,   lambda error: self.error.emit(str(error)))

                # Blocking receive loop runs in a daemon thread.
                listen_thread = threading.Thread(
                    target=conn.start_listening, daemon=True
                )
                listen_thread.start()

                # Stream mic audio until the stop event is set.
                chunk = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)
                p = pyaudio.PyAudio()
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=chunk,
                )
                while not self._stop_event.is_set():
                    data = stream.read(chunk, exception_on_overflow=False)
                    conn.send_media(data)

                stream.stop_stream()
                stream.close()

                # Signal end-of-audio so Deepgram emits final transcripts,
                # then close the WebSocket.
                conn.send_finalize()
                listen_thread.join(timeout=3.0)   # wait for last final transcript
                conn.send_close_stream()

        except Exception as e:
            self.error.emit(str(e))
            return
        finally:
            if p:
                p.terminate()

        self.transcript_ready.emit(self._final_text.strip())


# ── ElevenLabs backend ────────────────────────────────────────────────────────

class ElevenLabsSTTWorker(STTWorker):
    """
    Streams microphone audio to ElevenLabs Scribe v2 Realtime transcription.
    Uses asyncio with websockets library for async handling.
    """

    def __init__(self, stop_event: threading.Event):
        super().__init__()
        self._stop_event = stop_event
        self._final_text = ""

    def run(self) -> None:
        import os
        import asyncio
        from dotenv import load_dotenv

        load_dotenv()
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            self.error.emit("ELEVENLABS_API_KEY is not set. Add it to your .env file.")
            return

        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self._stream_realtime(api_key))
        except Exception as e:
            self.error.emit(str(e))
        finally:
            loop.close()

    async def _stream_realtime(self, api_key: str):
        """
        Async method to handle ElevenLabs WebSocket realtime transcription.
        """
        import json
        import base64
        import pyaudio
        import logging
        
        try:
            import websockets
        except ImportError:
            self.error.emit("websockets library required. Install with: pip install websockets")
            return

        ws_url = f"wss://api.elevenlabs.io/v1/speech-to-text/realtime?model_id=scribe_v2_realtime"
        
        # 1. FIX HEADER: Gunakan Bearer Token untuk Scribe v2
        try:
            import websockets.version
            major_version = int(websockets.version.version.split('.')[0])
            header_param = "additional_headers" if major_version >= 14 else "extra_headers"
        except Exception:
            header_param = "extra_headers"

        connect_kwargs = {
            header_param: {"xi-api-key": f"{api_key}"}
        }

        p = None
        stream = None
        
        try:
            async with websockets.connect(ws_url, **connect_kwargs) as ws:
                logging.debug("ElevenLabsSTTWorker: Connected to WebSocket")

                loop = asyncio.get_running_loop()
                audio_queue = asyncio.Queue()

                # 2. FIX CRASH: Gunakan PyAudio Callback agar tidak butuh run_in_executor
                def audio_callback(in_data, frame_count, time_info, status):
                    if not self._stop_event.is_set():
                        # Kirim data secara thread-safe ke asyncio queue
                        loop.call_soon_threadsafe(audio_queue.put_nowait, in_data)
                    return (None, pyaudio.paContinue)

                chunk_size = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)
                p = pyaudio.PyAudio()
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=chunk_size,
                    stream_callback=audio_callback  # Alihkan pembacaan mic ke C-level thread PyAudio
                )
                stream.start_stream()

                async def send_audio():
                    try:
                        while not self._stop_event.is_set():
                            try:
                                audio_chunk = await asyncio.wait_for(audio_queue.get(), timeout=0.1)
                                audio_b64 = base64.b64encode(audio_chunk).decode('utf-8')
                                
                                message = {
                                    "message_type": "input_audio_chunk",
                                    "audio_base_64": audio_b64,
                                }
                                await ws.send(json.dumps(message))
                            except asyncio.TimeoutError:
                                continue
                            except websockets.exceptions.ConnectionClosed:
                                break
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logging.error(f"ElevenLabsSTTWorker: Send error - {e}")

                async def receive_transcripts():
                    try:
                        async for message in ws:
                            if self._stop_event.is_set():
                                break
                            try:
                                data = json.loads(message)
                                msg_type = data.get("message_type", "")
                                
                                if msg_type == "partial_transcript":
                                    text = data.get("text", "").strip()
                                    if text:
                                        self.transcript_delta.emit(text)
                                        self._final_text = text  # Reset _final_text dengan teks baru untuk menghindari duplikasi
                                        
                                elif msg_type == "committed_transcript":
                                    text = data.get("text", "").strip()
                                    logging.debug(f"ElevenLabsSTTWorker: Committed transcript - '{text}'")
                                    if text:
                                        self._final_text += text + " "
                                        self.transcript_delta.emit(text) # Beri tahu UI bahwa ini sudah final
                                        
                                elif msg_type in ["scribe_error", "error"] or "error" in data:
                                    error_msg = data.get("message", data.get("error", "Unknown error"))
                                    self.error.emit(f"ElevenLabs API error: {error_msg}")
                                    break
                            except json.JSONDecodeError:
                                pass
                    except websockets.exceptions.ConnectionClosed:
                        pass
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logging.error(f"ElevenLabsSTTWorker: Receive error - {e}")

                send_task = asyncio.create_task(send_audio())
                receive_task = asyncio.create_task(receive_transcripts())

                # Loop utama menunggu sampai tombol spasi dilepas
                while not self._stop_event.is_set():
                    await asyncio.sleep(0.1)

                # Batalkan task pengiriman dan penerimaan
                send_task.cancel()
                receive_task.cancel()

        except Exception as e:
            logging.error(f"ElevenLabsSTTWorker: Connection error - {e}")
            self.error.emit(f"Connection error: {e}")
        finally:
            # Karena pembacaan audio ada di callback, kita bisa menutupnya dengan sangat aman
            # tanpa memicu Segfault
            if stream:
                stream.stop_stream()
                stream.close()
            if p:
                p.terminate()

        # Emit final result saat Spasi dilepas
        logging.debug(f"ElevenLabsSTTWorker: Final transcript - '{self._final_text.strip()}'")
        final_result = self._final_text.strip()
        if final_result:
            self.transcript_ready.emit(final_result)

# ── Mistral backend (reference) ───────────────────────────────────────────────

class MistralSTTWorker(STTWorker):
    """
    Streams microphone audio to Mistral's realtime transcription API.

    Lifecycle:
      1. Instantiated and started when the player presses Space.
      2. Opens a PyAudio input stream and yields chunks to Mistral.
      3. When stop_event is set (Space released), the async generator exits.
      4. Mistral finalises the transcription and emits TranscriptionStreamDone.
      5. transcript_ready is emitted with the full text.

    Uses threading.Event (not asyncio.Event) because it is set from the
    main Qt thread — threading.Event.is_set() is safe under Python's GIL.
    """

    def __init__(self, stop_event: threading.Event):
        super().__init__()

        import dotenv
        api_key = dotenv.get_key(dotenv.find_dotenv(), "MISTRAL_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "MISTRAL_API_KEY is not set. Add it to your .env file."
            )
        self._api_key    = api_key
        self._stop_event = stop_event

    def run(self) -> None:
        asyncio.run(self._stream())

    async def _stream(self) -> None:
        from mistralai import Mistral
        from mistralai.models import (
            AudioFormat,
            TranscriptionStreamTextDelta,
            TranscriptionStreamDone,
            RealtimeTranscriptionError,
        )
        try:
            from mistralai.extra.realtime import UnknownRealtimeEvent
            _has_unknown = True
        except ImportError:
            _has_unknown = False

        client       = Mistral(api_key=self._api_key)
        audio_format = AudioFormat(encoding="pcm_s16le", sample_rate=SAMPLE_RATE)
        full_text    = ""

        try:
            async for event in client.audio.realtime.transcribe_stream(
                audio_stream=self._iter_microphone(),
                model=STT_MODEL,
                audio_format=audio_format,
            ):
                if isinstance(event, TranscriptionStreamTextDelta):
                    full_text += event.text
                    self.transcript_delta.emit(event.text)
                elif isinstance(event, TranscriptionStreamDone):
                    break
                elif isinstance(event, RealtimeTranscriptionError):
                    self.error.emit(f"Realtime STT error: {event}")
                    return
        except Exception as e:
            self.error.emit(str(e))
            return

        self.transcript_ready.emit(full_text)

    async def _iter_microphone(self):
        import pyaudio
        p             = pyaudio.PyAudio()
        chunk_samples = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)
        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=chunk_samples,
            )
        except Exception as e:
            self.error.emit(f"PyAudio open failed: {e}")
            p.terminate()
            return

        loop = asyncio.get_running_loop()
        try:
            while not self._stop_event.is_set():
                data = await loop.run_in_executor(
                    None, stream.read, chunk_samples, False
                )
                yield data
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
