"""
ui/map_panel.py — Phase 3.2  Live Dungeon Map Panel

A collapsible QGraphicsView-based side panel showing the dungeon graph.
Connected to AppSignals.map_state_changed for live updates.

Scene is built once (_build_scene). On each update_map() call only
the pen/brush and HTML text of existing items are mutated — no rebuild.

Z-order:
  0 — edge lines (behind nodes)
  1 — node background rects
  2 — node text items
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QPen, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsLineItem,
    QGraphicsOpacityEffect,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from config import ASSETS_DIR, BG_COLOR

_ICONS_DIR  = ASSETS_DIR / "icons"
_ICON_SIZE  = 28   # px for Player Status icons

_ITEM_ICONS_DIR = ASSETS_DIR / "item_icons"
_ITEM_ICON_SIZE = 42   # px — item slot card icons

# All inventory slots shown in the slider, in display order
_ALL_SLOTS: list[tuple[str, str, str]] = [
    # (slot_or_type_key, display_label, icon_file)
    ("weapon", "Weapon",  "weapon.png"),
    ("helmet", "Helmet",  "helmet.png"),
    ("suit",   "Suit",    "suit.png"),
    ("legs",   "Legs",    "legs.png"),
    ("shoes",  "Shoes",   "shoes.png"),
    ("cloak",  "Cloak",   "cloak.png"),
    ("shield", "Shield",  "shield.png"),
    ("key",    "Key",     "key.png"),
    ("potion", "Potion",  "potion.png"),
]

# ── Layout constants ───────────────────────────────────────────────────────────

PANEL_WIDTH = 450
SCENE_W     = 420
SCENE_H     = 520
NODE_W      = 130
NODE_H      = 90

# Centre of each node — used for edge drawing and to derive top-left rects
_NODE_CENTERS: dict[str, tuple[int, int]] = {
    "home": (210, 55),
    "a":    (100, 185),
    "b":    (320, 185),
    "boss": (210, 305),
    "c":    (80,  415),
    "d":    (340, 415),
    "t":    (210, 475),
}

# Top-left corner of each node rect (derived from centres)
_NODE_RECTS: dict[str, tuple[int, int]] = {
    rid: (cx - NODE_W // 2, cy - NODE_H // 2)
    for rid, (cx, cy) in _NODE_CENTERS.items()
}

# Undirected edges — drawn once at build time
_EDGES: list[tuple[str, str]] = [
    ("home", "a"),  ("home", "b"),
    ("a",    "b"),  ("a",    "boss"), ("a",  "t"),
    ("b",    "boss"),
    ("boss", "c"),  ("boss", "d"),   ("boss", "t"),
    ("c",    "t"),  ("d",    "t"),
]

# Room metadata (mirrors dungeon_map.json — static dungeon)
_ROOM_TYPES: dict[str, str] = {
    "home": "home",
    "a":    "normal",
    "b":    "normal",
    "boss": "boss",
    "c":    "normal",
    "d":    "normal",
    "t":    "exit",
}

_ROOM_NAMES: dict[str, str] = {
    "home": "Dungeon Gate",
    "a":    "Hall of Warriors",
    "b":    "Forbidden Library",
    "boss": "Guardian's Throne",
    "c":    "Underground Prison",
    "d":    "Forgotten Armory",
    "t":    "Dark Core",
}

_TYPE_FILL: dict[str, str] = {
    "home":   "#16213e",
    "normal": "#2a2a3a",
    "boss":   "#3a1010",
    "exit":   "#0d2b1a",
}

# Colours
_COL_EDGE         = "#3a3a4a"
_COL_BORDER_NORM  = "#444455"
_COL_BORDER_PLAY  = "#ffff00"   # player location — yellow, 3 px
_COL_BORDER_LOCK  = "#8855aa"   # locked room — purple, 2 px
_COL_BORDER_BOSS  = "#cc2222"   # boss alive — red, 2 px
_COL_FILL_DEAD    = "#1e1e1e"   # grayed-out cleared boss
_COL_NAME         = "#c8c8d8"
_COL_NAME_DIM     = "#606070"
_COL_BOSS_ALIVE   = "#dd4444"
_COL_MONSTER      = "#cc8833"
_COL_ITEM         = "#7799aa"
_COL_TITLE        = "#c0a060"
_COL_STATUS_BG    = "#16161e"   # darker bg for player status section


def _load_icon(name: str) -> QPixmap | None:
    px = QPixmap(str(_ICONS_DIR / name))
    if px.isNull():
        return None
    return px.scaled(
        _ICON_SIZE, _ICON_SIZE,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


class MapPanel(QWidget):
    """
    Right-side collapsible panel displaying the dungeon graph.

    Slot:
        update_map(payload: dict)  — connected to AppSignals.map_state_changed

    Payload schema:
        {
          "player_room": str,
          "rooms": {
            room_id: {
              "items":        [str, ...],   # item display names
              "monsters":     [str, ...],   # monster display names
              "boss":         str | None,   # boss display name
              "boss_cleared": bool,
              "locked":       bool,
            }
          }
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(PANEL_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background-color: {BG_COLOR};")

        # room_id → {"rect": QGraphicsRectItem, "text": QGraphicsTextItem}
        self._node_items: dict[str, dict] = {}

        self._build_ui()
        self._build_scene()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)

        # Title
        title = QLabel("DUNGEON MAP")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"font-size: 14px; font-weight: bold; letter-spacing: 3px; "
            f"color: {_COL_TITLE}; padding: 4px;"
        )
        outer.addWidget(title)

        # Graphics scene + view
        self._scene = QGraphicsScene(0, 0, SCENE_W, SCENE_H)
        self._scene.setBackgroundBrush(QBrush(QColor(BG_COLOR)))

        self._view = QGraphicsView(self._scene)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setStyleSheet(f"background-color: {BG_COLOR}; border: none;")
        self._view.setFixedWidth(PANEL_WIDTH - 16)
        self._view.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._view.setMinimumHeight(180)
        outer.addWidget(self._view, stretch=6)

        # Bottom row — toggle checkbox
        bottom = QHBoxLayout()
        bottom.setContentsMargins(4, 0, 4, 4)
        self._toggle_cb = QCheckBox("Show map")
        self._toggle_cb.setChecked(True)
        self._toggle_cb.setStyleSheet(
            f"font-size: 12px; color: {_COL_NAME_DIM}; padding: 2px;"
        )
        self._toggle_cb.toggled.connect(self._view.setVisible)
        bottom.addWidget(self._toggle_cb)
        bottom.addStretch()
        outer.addLayout(bottom)

        # ── Player Status section ──────────────────────────────────────────────
        self._build_status_section(outer)

    # ── Scene construction ─────────────────────────────────────────────────────

    def _build_scene(self) -> None:
        """Draw static edges then create persistent node items with placeholder text."""
        edge_pen = QPen(QColor(_COL_EDGE))
        edge_pen.setWidth(1)

        for r1, r2 in _EDGES:
            cx1, cy1 = _NODE_CENTERS[r1]
            cx2, cy2 = _NODE_CENTERS[r2]
            line = QGraphicsLineItem(cx1, cy1, cx2, cy2)
            line.setPen(edge_pen)
            line.setZValue(0)
            self._scene.addItem(line)

        for room_id, (nx, ny) in _NODE_RECTS.items():
            fill = _TYPE_FILL.get(_ROOM_TYPES[room_id], "#2a2a3a")

            rect_item = QGraphicsRectItem(nx, ny, NODE_W, NODE_H)
            rect_item.setBrush(QBrush(QColor(fill)))
            rect_item.setPen(QPen(QColor(_COL_BORDER_NORM)))
            rect_item.setZValue(1)
            self._scene.addItem(rect_item)

            text_item = QGraphicsTextItem()
            text_item.setPos(nx + 4, ny + 2)
            text_item.setTextWidth(NODE_W - 8)
            text_item.setZValue(2)
            text_item.setHtml(
                f'<span style="font-size:10px; font-weight:bold; color:{_COL_NAME};">'
                f"{_ROOM_NAMES[room_id]}</span>"
            )
            self._scene.addItem(text_item)

            self._node_items[room_id] = {"rect": rect_item, "text": text_item}

    # ── Public slot ────────────────────────────────────────────────────────────

    def update_map(self, payload: dict) -> None:
        """Redraw node borders and text to reflect current game state."""
        player_room = payload.get("player_room", "")
        rooms_data  = payload.get("rooms", {})

        for room_id, node in self._node_items.items():
            info         = rooms_data.get(room_id, {})
            room_type    = _ROOM_TYPES.get(room_id, "normal")
            is_player    = room_id == player_room
            is_locked    = info.get("locked", False)
            boss_name    = info.get("boss")
            boss_cleared = info.get("boss_cleared", False)
            items_list   = info.get("items", [])
            monsters     = info.get("monsters", [])

            self._update_appearance(
                node["rect"], room_type, is_player, is_locked, boss_name, boss_cleared
            )
            node["text"].setHtml(
                self._build_html(
                    room_id, is_locked, boss_name, boss_cleared,
                    items_list, monsters
                )
            )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _update_appearance(
        self,
        rect: QGraphicsRectItem,
        room_type: str,
        is_player: bool,
        is_locked: bool,
        boss_name: str | None,
        boss_cleared: bool,
    ) -> None:
        fill = _COL_FILL_DEAD if (room_type == "boss" and boss_cleared) \
               else _TYPE_FILL.get(room_type, "#2a2a3a")
        rect.setBrush(QBrush(QColor(fill)))

        if is_player:
            pen = QPen(QColor(_COL_BORDER_PLAY))
            pen.setWidth(3)
        elif is_locked:
            pen = QPen(QColor(_COL_BORDER_LOCK))
            pen.setWidth(2)
        elif room_type == "boss" and boss_name and not boss_cleared:
            pen = QPen(QColor(_COL_BORDER_BOSS))
            pen.setWidth(2)
        else:
            pen = QPen(QColor(_COL_BORDER_NORM))
            pen.setWidth(1)
        rect.setPen(pen)

    def _build_status_section(self, parent_layout: QVBoxLayout) -> None:
        """Build the Player Status panel appended below the map."""
        status_frame = QFrame()
        status_frame.setStyleSheet(
            f"QFrame {{ background-color: {_COL_STATUS_BG}; "
            f"border-top: 1px solid #2a2a3a; border-radius: 0px; }}"
        )
        sf_layout = QVBoxLayout(status_frame)
        sf_layout.setContentsMargins(12, 10, 12, 10)
        sf_layout.setSpacing(4)

        # Title
        ps_title = QLabel("PLAYER STATUS")
        ps_title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        ps_title.setStyleSheet(
            f"font-size: 13px; font-weight: bold; letter-spacing: 2px; "
            f"color: {_COL_TITLE}; background: transparent; border: none;"
        )
        sf_layout.addWidget(ps_title)

        # HP row: [heart icon] hp_label
        hp_row = QWidget()
        hp_row.setStyleSheet("background: transparent;")
        hp_h = QHBoxLayout(hp_row)
        hp_h.setContentsMargins(0, 4, 0, 0)
        hp_h.setSpacing(8)

        self._icon_heart = QLabel()
        px = _load_icon("heart.png")
        if px:
            self._icon_heart.setPixmap(px)
        self._icon_heart.setFixedSize(_ICON_SIZE, _ICON_SIZE)
        self._icon_heart.setStyleSheet("background: transparent; border: none;")
        hp_h.addWidget(self._icon_heart)

        self.lbl_ps_hp = QLabel("100/100")
        self.lbl_ps_hp.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #e06060; "
            "background: transparent; border: none;"
        )
        hp_h.addWidget(self.lbl_ps_hp)
        hp_h.addStretch()
        sf_layout.addWidget(hp_row)

        # Horizontal scroll area — all item slots (active / inactive)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:horizontal { height: 6px; background: #1a1a2a; border-radius: 3px; }"
            "QScrollBar::handle:horizontal { background: #444466; border-radius: 3px; }"
        )
        scroll.setFixedHeight(108)

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        inner_h = QHBoxLayout(inner)
        inner_h.setContentsMargins(4, 4, 4, 4)
        inner_h.setSpacing(6)

        self._slot_cards: dict[str, tuple[QFrame, QLabel, QLabel]] = {}
        for slot_key, label, icon_file in _ALL_SLOTS:
            card, icon_lbl, name_lbl = self._make_slot_card(label, icon_file)
            self._slot_cards[slot_key] = (card, icon_lbl, name_lbl)
            inner_h.addWidget(card)
        inner_h.addStretch()

        scroll.setWidget(inner)
        sf_layout.addWidget(scroll)
        sf_layout.addStretch()

        parent_layout.addWidget(status_frame, stretch=4)

    def _make_slot_card(
        self, label: str, icon_file: str
    ) -> tuple["QFrame", "QLabel", "QLabel"]:
        """Create an inventory slot card (inactive by default)."""
        card = QFrame()
        card.setFixedWidth(80)
        card.setStyleSheet(
            "QFrame { background-color: #141420; border: 1px solid #2a2a3a; border-radius: 6px; }"
        )
        v = QVBoxLayout(card)
        v.setContentsMargins(4, 4, 4, 6)
        v.setSpacing(2)

        slot_lbl = QLabel(label)
        slot_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        slot_lbl.setStyleSheet(
            "font-size: 9px; color: #555566; background: transparent; border: none;"
        )
        v.addWidget(slot_lbl)

        icon_lbl = QLabel()
        px = QPixmap(str(_ITEM_ICONS_DIR / icon_file))
        if not px.isNull():
            px = px.scaled(
                _ITEM_ICON_SIZE, _ITEM_ICON_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            icon_lbl.setPixmap(px)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        effect = QGraphicsOpacityEffect()
        effect.setOpacity(0.2)
        icon_lbl.setGraphicsEffect(effect)
        v.addWidget(icon_lbl)

        name_lbl = QLabel("")
        name_lbl.setWordWrap(True)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setStyleSheet(
            "font-size: 9px; color: #444455; background: transparent; border: none;"
        )
        v.addWidget(name_lbl)

        return card, icon_lbl, name_lbl

    def _build_html(
        self,
        room_id: str,
        is_locked: bool,
        boss_name: str | None,
        boss_cleared: bool,
        items_list: list[str],
        monsters: list[str],
    ) -> str:
        lock_str   = " \U0001f512" if is_locked else ""
        name_color = _COL_NAME_DIM if boss_cleared else _COL_NAME

        lines = [
            f'<span style="font-size:10px; font-weight:bold; color:{name_color};">'
            f"{_ROOM_NAMES[room_id]}{lock_str}</span>"
        ]

        if boss_name:
            if boss_cleared:
                lines.append(
                    f'<span style="font-size:8px; color:{_COL_NAME_DIM};">'
                    f"{boss_name} [dead]</span>"
                )
            else:
                lines.append(
                    f'<span style="font-size:8px; color:{_COL_BOSS_ALIVE};">'
                    f"{boss_name}</span>"
                )

        for m in monsters:
            lines.append(
                f'<span style="font-size:8px; color:{_COL_MONSTER};">{m}</span>'
            )

        for itm in items_list[:2]:
            lines.append(
                f'<span style="font-size:8px; color:{_COL_ITEM};">{itm}</span>'
            )
        if len(items_list) > 2:
            lines.append(
                f'<span style="font-size:7px; color:{_COL_NAME_DIM};">'
                f"+{len(items_list) - 2} more</span>"
            )

        return "<br/>".join(lines)

    # ── Player Status public slots ─────────────────────────────────────────────

    def update_player_hp(self, hp: int, max_hp: int) -> None:
        """Update the HP display in the Player Status panel."""
        self.lbl_ps_hp.setText(f"{hp}/{max_hp}")

    def update_player_status(self, payload: dict) -> None:
        """
        Slot for inventory_updated signal.
        payload = {"equipped": {slot: item_dict | None}, "bag": [item_dicts]}
        Updates each slot card to active (item equipped/in bag) or inactive.
        """
        equipped = payload.get("equipped", {})
        bag      = payload.get("bag", [])

        for slot_key, (card, icon_lbl, name_lbl) in self._slot_cards.items():

            if slot_key in ("key", "potion"):
                # Active when a matching item type is in the bag
                match = next((i for i in bag if i.get("type") == slot_key), None)
                active    = match is not None
                item_name = match["name"] if match else ""
            else:
                item = equipped.get(slot_key)
                # bare_hands counts as unequipped
                if slot_key == "weapon" and item and item.get("id") == "bare_hands":
                    active    = False
                    item_name = ""
                else:
                    active    = item is not None
                    item_name = item["name"] if item else ""

            if active:
                card.setStyleSheet(
                    "QFrame { background-color: #2a1020; border: 1px solid #aa2222; border-radius: 6px; }"
                )
                icon_lbl.graphicsEffect().setOpacity(1.0)
                name_lbl.setText(item_name)
                name_lbl.setStyleSheet(
                    "font-size: 9px; color: #c0c0d8; background: transparent; border: none;"
                )
            else:
                card.setStyleSheet(
                    "QFrame { background-color: #141420; border: 1px solid #2a2a3a; border-radius: 6px; }"
                )
                icon_lbl.graphicsEffect().setOpacity(0.2)
                name_lbl.setText("")
                name_lbl.setStyleSheet(
                    "font-size: 9px; color: #444455; background: transparent; border: none;"
                )
