from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from config import BG_COLOR, TEXT_COLOR, ACCENT_COLOR, STATUS_COLOR, DIM_COLOR


class GameView(QWidget):
    """
    The main game display. Entirely read-only — no user interaction here.
    Updated exclusively via its public slot methods.
    Key events are handled by MainWindow, not this widget.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._apply_styles()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(0)

        # ── Title ──────────────────────────────────────────
        self.lbl_title = QLabel("BLIND DUNGEON")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ── Spacer ──────────────────────────────────────────
        layout.addWidget(self.lbl_title)
        layout.addSpacing(40)

        # ── Room name ───────────────────────────────────────
        self.lbl_room = QLabel("—")
        self.lbl_room.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_room.setWordWrap(True)
        layout.addWidget(self.lbl_room)

        layout.addSpacing(16)

        # ── Exits ───────────────────────────────────────────
        self.lbl_exits = QLabel("Exits: —")
        self.lbl_exits.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_exits.setWordWrap(True)
        layout.addWidget(self.lbl_exits)

        layout.addSpacing(24)

        # ── Narration text (persistent overlay) ─────────────
        self.lbl_narration = QLabel("")
        self.lbl_narration.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_narration.setWordWrap(True)
        layout.addWidget(self.lbl_narration)

        layout.addStretch()

        # ── Live transcript (shown while listening) ──────────
        self.lbl_transcript = QLabel("")
        self.lbl_transcript.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_transcript.setWordWrap(True)
        self.lbl_transcript.setVisible(False)
        layout.addWidget(self.lbl_transcript)

        layout.addSpacing(12)

        # ── Status ──────────────────────────────────────────
        self.lbl_status = QLabel("Initializing...")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)

        layout.addSpacing(8)

        # ── Hotkey hint ─────────────────────────────────────
        self.lbl_hint = QLabel("Hold  [SPACE]  to speak")
        self.lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_hint)

    def _apply_styles(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR}; color: {TEXT_COLOR};")

        self.lbl_title.setStyleSheet(
            f"font-size: 28px; font-weight: bold; "
            f"color: {ACCENT_COLOR}; letter-spacing: 6px;"
        )
        self.lbl_room.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {ACCENT_COLOR};"
        )
        self.lbl_exits.setStyleSheet(
            "font-size: 13px; color: #8888aa; letter-spacing: 1px;"
        )
        self.lbl_narration.setStyleSheet(
            "font-size: 13px; font-style: italic; color: #a0a0b8; line-height: 1.6;"
        )
        self.lbl_transcript.setStyleSheet(
            "font-size: 13px; font-style: italic; color: #70c090;"
        )
        self.lbl_status.setStyleSheet(
            f"font-size: 14px; font-style: italic; color: {STATUS_COLOR};"
        )
        self.lbl_hint.setStyleSheet(
            f"font-size: 11px; color: {DIM_COLOR}; letter-spacing: 2px;"
        )

    # ── Slots ─────────────────────────────────────────────────────────────────

    def update_state(self, payload: dict) -> None:
        """
        Connected to AppSignals.state_updated.
        payload = {"room": {...}, "exits": {direction: room_id}, "player": {...}}
        """
        room  = payload["room"]
        exits = payload["exits"]

        self.lbl_room.setText(room["name"])

        if exits:
            exits_text = "   |   ".join(
                f"[{d.upper()}]" for d in exits.keys()
            )
        else:
            exits_text = "(no exits)"
        self.lbl_exits.setText(f"Exits:  {exits_text}")

    def set_status(self, text: str) -> None:
        """Connected to status change signals."""
        self.lbl_status.setText(text)
        # Hide transcript when not actively listening
        if text not in ("Listening...",):
            self._hide_transcript()

    def show_listening(self) -> None:
        """Called when mic recording begins."""
        self.lbl_transcript.setText("")
        self.lbl_transcript.setVisible(True)
        self.lbl_status.setText("Listening...")

    def append_transcript_delta(self, text: str) -> None:
        """Appends live partial transcription text."""
        current = self.lbl_transcript.text()
        self.lbl_transcript.setText(current + text)

    def update_narration(self, text: str) -> None:
        """Displays the full narration text. Persists until the next narration replaces it."""
        self.lbl_narration.setText(text)

    def _hide_transcript(self) -> None:
        self.lbl_transcript.setVisible(False)
        self.lbl_transcript.setText("")
