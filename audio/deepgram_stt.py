"""
DeepgramSTTWorker — live speech-to-text via Deepgram SDK v6.

Replaces RealtimeSTTWorker (Mistral-based) for hold-to-talk input.
Requires DEEPGRAM_API_KEY in .env (or environment).

Usage:
    stop_event = threading.Event()
    worker = DeepgramSTTWorker(stop_event)
    worker.transcript_delta.connect(...)   # live partial transcript (set semantics)
    worker.transcript_ready.connect(...)   # final transcript
    worker.error.connect(...)
    worker.start()
    # ... when Space released:
    stop_event.set()
"""

import threading

from PyQt6.QtCore import QThread, pyqtSignal

from config import CHUNK_DURATION_MS, SAMPLE_RATE


class DeepgramSTTWorker(QThread):
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
