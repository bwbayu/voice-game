from PyQt6.QtCore import QObject, pyqtSignal


class AppSignals(QObject):
    """
    Central signal bus for the entire application.

    Must be instantiated on the main thread before any worker threads start.
    All cross-thread communication goes through this object.

    Signals emitted FROM worker threads (auto-queued to main thread by Qt):
        narration_started       NarrationWorker has begun
        narration_finished      NarrationWorker done; audio is playing
        narration_text(str)     Full narration text — displayed persistently in centre pane
        state_updated(dict)     Room/player state changed — UI should refresh
                                payload: {"room": {...}, "exits": {...}, "player": {...}}
        listening_started       Mic is open and streaming
        transcript_delta(str)   Partial transcription text (live display)
        processing_started      STT finished; intent parsing has begun
        processing_finished     Intent resolved; action dispatched
        error_occurred(str)     Non-fatal error message for status bar
        game_won(str, str)      Player reached exit: (room_name, wav_path)
    """

    narration_started   = pyqtSignal()
    narration_finished  = pyqtSignal()
    narration_text      = pyqtSignal(str)
    state_updated       = pyqtSignal(dict)
    listening_started   = pyqtSignal()
    transcript_delta    = pyqtSignal(str)
    processing_started  = pyqtSignal()
    processing_finished = pyqtSignal()
    error_occurred      = pyqtSignal(str)
    game_won            = pyqtSignal(str, str)   # (room_name, wav_path)

    # Phase 2 — combat + items
    combat_started     = pyqtSignal(dict)   # {name, hp, max_hp}
    combat_updated     = pyqtSignal(dict)   # {player_hp, player_max_hp, boss_hp, boss_max_hp}
    combat_ended       = pyqtSignal()       # boss defeated, back to exploration
    inventory_updated  = pyqtSignal(list)   # list of item dicts
    room_items_changed = pyqtSignal(list)   # list of item dicts in current room
