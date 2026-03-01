from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter

from config import BG_COLOR, TEXT_COLOR, ACCENT_COLOR, STATUS_COLOR, DIM_COLOR

_LABEL_BG = "background-color: rgba(0, 0, 0, 160); padding: 4px 8px; border-radius: 4px;"


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

        # ── Player HP (always visible) ───────────────────────
        self.lbl_player_hp = QLabel("HP: —")
        self.lbl_player_hp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_player_hp)

        layout.addSpacing(24)

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

        layout.addSpacing(12)

        # ── Room items ───────────────────────────────────────
        self.lbl_room_items = QLabel("")
        self.lbl_room_items.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_room_items.setWordWrap(True)
        layout.addWidget(self.lbl_room_items)

        layout.addSpacing(4)

        # ── Equipped weapon ──────────────────────────────────
        self.lbl_weapon = QLabel("Weapon: [none]")
        self.lbl_weapon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_weapon.setWordWrap(True)
        layout.addWidget(self.lbl_weapon)

        layout.addSpacing(2)

        # ── Equipped armor ───────────────────────────────────
        self.lbl_armor = QLabel("Armor: [none]")
        self.lbl_armor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_armor.setWordWrap(True)
        layout.addWidget(self.lbl_armor)

        layout.addSpacing(2)

        # ── Bag (keys) ───────────────────────────────────────
        self.lbl_bag = QLabel("")
        self.lbl_bag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_bag.setWordWrap(True)
        layout.addWidget(self.lbl_bag)

        layout.addStretch()

        # ── Live transcript (shown while listening) ──────────
        self.lbl_transcript = QLabel("")
        self.lbl_transcript.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_transcript.setWordWrap(True)
        self.lbl_transcript.setVisible(False)
        layout.addWidget(self.lbl_transcript)

        layout.addSpacing(12)

        # ── Boss combat HP (shown only during combat) ────────
        self.lbl_combat = QLabel("")
        self.lbl_combat.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_combat.setVisible(False)
        layout.addWidget(self.lbl_combat)

        layout.addSpacing(6)

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
            f"font-size: 28px; font-weight: bold; color: {ACCENT_COLOR}; "
            f"letter-spacing: 6px; {_LABEL_BG}"
        )
        self.lbl_player_hp.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {STATUS_COLOR}; {_LABEL_BG}"
        )
        self.lbl_room.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {ACCENT_COLOR}; {_LABEL_BG}"
        )
        self.lbl_exits.setStyleSheet(
            f"font-size: 13px; color: #8888aa; letter-spacing: 1px; {_LABEL_BG}"
        )
        self.lbl_narration.setStyleSheet(
            f"font-size: 13px; font-style: italic; color: #a0a0b8; {_LABEL_BG}"
        )
        self.lbl_room_items.setStyleSheet(
            f"font-size: 12px; color: #707088; {_LABEL_BG}"
        )
        for lbl in (self.lbl_weapon, self.lbl_armor, self.lbl_bag):
            lbl.setStyleSheet(f"font-size: 12px; color: #707088; {_LABEL_BG}")
        self.lbl_transcript.setStyleSheet(
            f"font-size: 13px; font-style: italic; color: #70c090; {_LABEL_BG}"
        )
        self.lbl_combat.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {ACCENT_COLOR}; {_LABEL_BG}"
        )
        self.lbl_status.setStyleSheet(
            f"font-size: 14px; font-style: italic; color: {STATUS_COLOR}; {_LABEL_BG}"
        )
        self.lbl_hint.setStyleSheet(
            f"font-size: 11px; color: {DIM_COLOR}; letter-spacing: 2px; {_LABEL_BG}"
        )

    # ── Slots ─────────────────────────────────────────────────────────────────

    def update_state(self, payload: dict) -> None:
        """
        Connected to AppSignals.state_updated.
        payload = {"room": {...}, "exits": {direction: room_id}, "player": {...}}
        """
        room   = payload["room"]
        exits  = payload["exits"]
        player = payload.get("player", {})

        self.lbl_room.setText(room["name"])

        if exits:
            exits_text = "   |   ".join(
                f"[{d.upper()}]" for d in exits.keys()
            )
        else:
            exits_text = "(no exits)"
        self.lbl_exits.setText(f"Exits:  {exits_text}")

        # Player HP
        hp     = player.get("hp", "—")
        max_hp = player.get("max_hp", "—")
        self.lbl_player_hp.setText(f"HP: {hp}/{max_hp}")

        # Room background image
        bg_image = room.get("bg_image", "")
        if bg_image:
            self.update_bg_image(bg_image)

    def update_player_hp(self, hp: int, max_hp: int) -> None:
        """Direct HP update — called during combat when state_updated is not re-emitted."""
        self.lbl_player_hp.setText(f"HP: {hp}/{max_hp}")

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
        """Show the latest partial transcript (set semantics — Deepgram sends full partials)."""
        self.lbl_transcript.setText(text)

    def update_narration(self, text: str) -> None:
        """Displays the full narration text. Persists until the next narration replaces it."""
        self.lbl_narration.setText(text)

    def update_room_items(self, items: list[dict]) -> None:
        """Update the room items label. Shows ATK/DEF stat inline."""
        if items:
            parts = []
            for i in items:
                if i.get("type") == "weapon":
                    parts.append(f"{i['name']} (ATK {i.get('damage', 0)})")
                elif i.get("type") == "armor":
                    parts.append(f"{i['name']} (DEF {i.get('defense', 0)})")
                else:
                    parts.append(i["name"])
            self.lbl_room_items.setText("Items here:  " + "  |  ".join(parts))
        else:
            self.lbl_room_items.setText("")

    def update_inventory(self, payload: dict) -> None:
        """Update equipment display. payload = {"equipped": {slot: item_dict|None}, "bag": [...]}"""
        equipped = payload.get("equipped", {})
        bag      = payload.get("bag", [])

        w = equipped.get("weapon")
        self.lbl_weapon.setText(
            f"Weapon: {w['name']}  (ATK {w.get('damage', 0)})" if w else "Weapon: [none]"
        )

        _ARMOR_SLOTS = ("helmet", "suit", "legs", "shoes", "cloak", "shield")
        parts = [
            f"{slot.title()}: {equipped[slot]['name']} (DEF {equipped[slot].get('defense', 0)})"
            for slot in _ARMOR_SLOTS if equipped.get(slot)
        ]
        self.lbl_armor.setText("Armor: " + "  |  ".join(parts) if parts else "Armor: [none]")

        self.lbl_bag.setText(
            "Bag: " + "  |  ".join(i["name"] for i in bag) if bag else ""
        )

    def show_combat_status(
        self,
        player_hp: int,
        player_max: int,
        boss_hp: int,
        boss_max: int,
        boss_name: str,
    ) -> None:
        """Show boss HP bar during fights; also update persistent player HP label."""
        self.lbl_combat.setText(f"{boss_name}: {boss_hp}/{boss_max}")
        self.lbl_combat.setVisible(True)
        self.lbl_player_hp.setText(f"HP: {player_hp}/{player_max}")

    def hide_combat_status(self) -> None:
        """Hide the boss HP bar when not in combat."""
        self.lbl_combat.setVisible(False)
        self.lbl_combat.setText("")

    def _hide_transcript(self) -> None:
        self.lbl_transcript.setVisible(False)
        self.lbl_transcript.setText("")
