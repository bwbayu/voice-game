from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter

from config import BG_COLOR, TEXT_COLOR, ACCENT_COLOR, STATUS_COLOR, ASSETS_DIR

_ICONS_DIR = ASSETS_DIR / "icons"
_ICON_SIZE  = 36   # px — icon labels are fixed at this square size


def _load_icon(name: str) -> QPixmap | None:
    px = QPixmap(str(_ICONS_DIR / name))
    if px.isNull():
        return None
    return px.scaled(
        _ICON_SIZE, _ICON_SIZE,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


class GameView(QWidget):
    """
    The main game display. Entirely read-only — no user interaction here.
    Updated exclusively via its public slot methods.
    Key events are handled by MainWindow, not this widget.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bg_pixmap: QPixmap | None = None
        self._build_ui()
        self._apply_styles()

    # ── Background painting ────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        if self._bg_pixmap:
            painter = QPainter(self)
            painter.drawPixmap(self.rect(), self._bg_pixmap)
        super().paintEvent(event)

    def update_bg_image(self, path: str) -> None:
        """Load a room background image. Silently skips if the file is missing."""
        px = QPixmap(path)
        self._bg_pixmap = px if not px.isNull() else None
        self.update()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(0)

        # ── Title ──────────────────────────────────────────
        self.lbl_title = QLabel("BLIND DUNGEON")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_title)

        layout.addSpacing(8)

        # ── Room name ───────────────────────────────────────
        self.lbl_room = QLabel("—")
        self.lbl_room.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_room.setWordWrap(True)
        layout.addWidget(self.lbl_room)

        layout.addSpacing(16)

        # ── Narrative box ────────────────────────────────────
        self._narrative_frame = QFrame()
        self._narrative_frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame_layout = QVBoxLayout(self._narrative_frame)
        frame_layout.setContentsMargins(16, 16, 16, 16)
        self.lbl_narration = QLabel("")
        self.lbl_narration.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_narration.setWordWrap(True)
        frame_layout.addWidget(self.lbl_narration)
        layout.addWidget(self._narrative_frame)

        layout.addSpacing(16)

        # ── Room items row (chest icon + item names) ─────────
        self._items_row = QWidget()
        items_h = QHBoxLayout(self._items_row)
        items_h.setContentsMargins(0, 0, 0, 0)
        items_h.setSpacing(10)

        self._icon_chest = QLabel()
        px = _load_icon("chest_pixel.png")
        if px:
            self._icon_chest.setPixmap(px)
        self._icon_chest.setFixedSize(_ICON_SIZE, _ICON_SIZE)
        items_h.addStretch()
        items_h.addWidget(self._icon_chest)

        self.lbl_room_items = QLabel("")
        self.lbl_room_items.setWordWrap(True)
        self.lbl_room_items.setAlignment(Qt.AlignmentFlag.AlignCenter)
        items_h.addWidget(self.lbl_room_items)
        items_h.addStretch()

        self._items_row.setVisible(False)
        layout.addWidget(self._items_row)

        layout.addSpacing(8)

        # ── Monster row (combat only — monster icon + name + HP) ─
        self._monster_row = QWidget()
        monster_h = QHBoxLayout(self._monster_row)
        monster_h.setContentsMargins(0, 0, 0, 0)
        monster_h.setSpacing(10)

        self._icon_monster = QLabel()
        px = _load_icon("boss_icon.png")
        if px:
            self._icon_monster.setPixmap(px)
        self._icon_monster.setFixedSize(_ICON_SIZE, _ICON_SIZE)
        monster_h.addStretch()
        monster_h.addWidget(self._icon_monster)

        self.lbl_monster = QLabel("")
        self.lbl_monster.setWordWrap(True)
        self.lbl_monster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        monster_h.addWidget(self.lbl_monster)
        monster_h.addStretch()

        self._monster_row.setVisible(False)
        layout.addWidget(self._monster_row)

        layout.addStretch()

        # ── Exits pill ──────────────────────────────────────
        self.lbl_exits = QLabel("Exits: —")
        self.lbl_exits.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_exits.setWordWrap(True)
        layout.addWidget(self.lbl_exits)

        layout.addSpacing(8)

        # ── Status ──────────────────────────────────────────
        self.lbl_status = QLabel("Initializing...")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)

        layout.addSpacing(8)

    def _apply_styles(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR}; color: {TEXT_COLOR};")

        self.lbl_title.setStyleSheet(
            f"font-size: 28px; font-weight: bold; color: {ACCENT_COLOR}; "
            f"letter-spacing: 6px;"
        )
        self.lbl_room.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {ACCENT_COLOR};"
        )
        self._narrative_frame.setStyleSheet(
            "QFrame { background-color: rgba(30, 30, 50, 200); "
            "border-radius: 8px; border: 1px solid #3a3a5a; }"
        )
        self.lbl_narration.setStyleSheet(
            "font-size: 13px; font-style: italic; color: #a0a0b8;"
        )
        self.lbl_room_items.setStyleSheet(
            "font-size: 12px; color: #c0c0d8;"
        )
        self.lbl_monster.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {ACCENT_COLOR};"
        )
        self.lbl_exits.setStyleSheet(
            "font-size: 13px; color: #8888aa; letter-spacing: 1px; "
            "background-color: rgba(20, 20, 40, 200); "
            "border-radius: 12px; border: 1px solid #444466; "
            "padding: 6px 16px;"
        )
        self.lbl_status.setStyleSheet(
            f"font-size: 14px; font-style: italic; color: {STATUS_COLOR};"
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
                f"[{d.upper()}]  {name}" for d, name in exits.items()
            )
        else:
            exits_text = "(no exits)"
        self.lbl_exits.setText(f"Exits Path:   {exits_text}")

        # Room background image
        bg_image = room.get("bg_image", "")
        if bg_image:
            self.update_bg_image(bg_image)

    def set_status(self, text: str) -> None:
        """Connected to status change signals."""
        self.lbl_status.setText(text)

    def show_listening(self) -> None:
        """Called when mic recording begins."""
        self.lbl_status.setText("Listening...")

    def update_narration(self, text: str) -> None:
        """Displays the full narration text. Persists until the next narration replaces it."""
        self.lbl_narration.setText(text)

    def update_room_items(self, items: list[dict]) -> None:
        """Update the room items row. Shows ATK/DEF stat inline."""
        if items:
            parts = []
            for i in items:
                if i.get("type") == "weapon":
                    parts.append(f"{i['name']}  (ATK {i.get('damage', 0)})")
                elif i.get("type") == "armor":
                    parts.append(f"{i['name']}  (DEF {i.get('defense', 0)})")
                else:
                    parts.append(i["name"])
            self.lbl_room_items.setText("  |  ".join(parts))
            self._items_row.setVisible(True)
        else:
            self.lbl_room_items.setText("")
            self._items_row.setVisible(False)

    def show_monster_row(self, name: str, hp: int, max_hp: int) -> None:
        """Show enemy name and HP in the monster row during combat."""
        self.lbl_monster.setText(f"{name}   |   {hp}/{max_hp}")
        self._monster_row.setVisible(True)

    def hide_monster_row(self) -> None:
        """Hide the monster row when combat ends."""
        self._monster_row.setVisible(False)
        self.lbl_monster.setText("")
