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
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from config import BG_COLOR

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
        self._view.setFixedSize(PANEL_WIDTH - 16, SCENE_H + 4)
        outer.addWidget(self._view)

        outer.addStretch()

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
