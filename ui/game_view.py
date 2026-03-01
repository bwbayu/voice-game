from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QLinearGradient, QColor, QBrush

from config import (
    BG_COLOR, TEXT_COLOR, ACCENT_COLOR, STATUS_COLOR, 
    CRIMSON_RED, DIM_COLOR, ASSETS_DIR
)

_ICONS_DIR = ASSETS_DIR / "icons"
_ICON_SIZE  = 28

# Font Stacks (Target Font -> Fallback)
_FONT_TITLE = "'Cinzel', 'Georgia', serif"
_FONT_BODY  = "'Lora', 'Georgia', 'Times New Roman', serif"

def _load_icon(name: str) -> QPixmap | None:
    px = QPixmap(str(_ICONS_DIR / name))
    if px.isNull(): return None
    return px.scaled(_ICON_SIZE, _ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

class RoomImageWidget(QWidget):
    """Custom widget to display the top-half image with center cropping and fade-out gradient."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap: QPixmap | None = None
        self.setFixedHeight(350) # Tinggi gambar di-fix 350px

    def set_image(self, path: str) -> None:
        self.pixmap = QPixmap(path)
        self.update()

    def paintEvent(self, event) -> None:
        if self.pixmap and not self.pixmap.isNull():
            painter = QPainter(self)
            # Resize dengan KeepAspectRatioByExpanding agar menutupi seluruh area tanpa gepeng
            scaled = self.pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            crop_x = (scaled.width() - self.width()) // 2
            crop_y = (scaled.height() - self.height()) // 2
            painter.drawPixmap(0, 0, scaled, crop_x, crop_y, self.width(), self.height())
            
            # Gradasi di bagian bawah gambar agar menyatu mulus ke UI hitam
            grad = QLinearGradient(0, self.height() - 60, 0, self.height())
            grad.setColorAt(0, QColor(11, 12, 16, 0))
            grad.setColorAt(1, QColor(11, 12, 16, 255))
            painter.fillRect(self.rect(), QBrush(grad))

class GameView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._apply_styles()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 1. Top Half: Image Container ──
        self._image_widget = RoomImageWidget()
        main_layout.addWidget(self._image_widget)

        # ── 2. Bottom Half: UI Container ──
        self._ui_container = QWidget()
        ui_layout = QVBoxLayout(self._ui_container)
        ui_layout.setContentsMargins(30, 10, 30, 30)
        
        # Title & Room
        self.lbl_title = QLabel("B L I N D   D U N G E O N")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ui_layout.addWidget(self.lbl_title)

        self.lbl_room = QLabel("—")
        self.lbl_room.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_room.setWordWrap(True)
        # Drop Shadow elegan untuk nama ruangan
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 2)
        self.lbl_room.setGraphicsEffect(shadow)
        ui_layout.addWidget(self.lbl_room)

        ui_layout.addSpacing(20)

        # Narration
        self.lbl_narration = QLabel("")
        self.lbl_narration.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_narration.setWordWrap(True)
        self.lbl_narration.setMinimumHeight(100)
        ui_layout.addWidget(self.lbl_narration)
        
        ui_layout.addStretch()

        # Item & Monster Rows
        self._items_row = QWidget()
        items_h = QHBoxLayout(self._items_row)
        items_h.setContentsMargins(0, 0, 0, 0)
        self.lbl_room_items = QLabel("")
        self.lbl_room_items.setAlignment(Qt.AlignmentFlag.AlignCenter)
        items_h.addWidget(self.lbl_room_items)
        self._items_row.setVisible(False)
        ui_layout.addWidget(self._items_row)

        self._monster_row = QWidget()
        monster_h = QHBoxLayout(self._monster_row)
        monster_h.setContentsMargins(0, 0, 0, 0)
        self.lbl_monster = QLabel("")
        self.lbl_monster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        monster_h.addWidget(self.lbl_monster)
        self._monster_row.setVisible(False)
        ui_layout.addWidget(self._monster_row)

        ui_layout.addSpacing(15)

        # Exits & Mic Status
        self.lbl_exits = QLabel("Exits: —")
        self.lbl_exits.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ui_layout.addWidget(self.lbl_exits)

        self.lbl_status = QLabel("Initializing...")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ui_layout.addWidget(self.lbl_status)

        ui_layout.addSpacing(15)

        # ── 3. Player Dashboard (Bottom Section) ──
        self._build_dashboard(ui_layout)

        main_layout.addWidget(self._ui_container)

    def _build_dashboard(self, parent_layout: QVBoxLayout) -> None:
        self.dashboard_frame = QFrame()
        dash_layout = QVBoxLayout(self.dashboard_frame)
        dash_layout.setContentsMargins(15, 15, 15, 10)
        dash_layout.setSpacing(6)

        # HP Row
        hp_h = QHBoxLayout()
        icon_heart = QLabel()
        px_heart = _load_icon("heart.png")
        if px_heart: icon_heart.setPixmap(px_heart)
        self.lbl_ps_hp = QLabel("100/100 HP")
        hp_h.addWidget(icon_heart)
        hp_h.addWidget(self.lbl_ps_hp)
        hp_h.addStretch()
        dash_layout.addLayout(hp_h)

        # Equipment Text
        self.lbl_ps_equip = QLabel("Weapon: [none]  |  Armor: [none]")
        self.lbl_ps_bag = QLabel("Bag: Empty")
        dash_layout.addWidget(self.lbl_ps_equip)
        dash_layout.addWidget(self.lbl_ps_bag)

        parent_layout.addWidget(self.dashboard_frame)

    def _apply_styles(self) -> None:
        self._ui_container.setStyleSheet(f"background-color: {BG_COLOR};")
        
        self.lbl_title.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {ACCENT_COLOR}; "
            f"letter-spacing: 6px; font-family: {_FONT_TITLE};"
        )
        self.lbl_room.setStyleSheet(
            f"font-size: 26px; font-weight: normal; color: #FFFFFF;"
            f"font-family: {_FONT_TITLE};"
        )
        self.lbl_narration.setStyleSheet(
            f"font-size: 18px; font-style: italic; color: {TEXT_COLOR}; "
            f"line-height: 140%; font-family: {_FONT_BODY};"
        )
        self.lbl_room_items.setStyleSheet(f"font-size: 13px; color: {ACCENT_COLOR}; font-family: {_FONT_BODY};")
        self.lbl_monster.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {CRIMSON_RED}; font-family: {_FONT_BODY};")
        
        self.lbl_exits.setStyleSheet(
            f"font-size: 12px; color: {DIM_COLOR}; letter-spacing: 2px; "
            f"font-family: {_FONT_TITLE}; border-top: 1px solid rgba(212, 175, 55, 0.2); padding-top: 10px;"
        )
        self.lbl_status.setStyleSheet(f"font-size: 13px; color: {STATUS_COLOR}; font-style: italic; font-family: {_FONT_BODY};")

        # Dashboard Styling
        self.dashboard_frame.setStyleSheet(
            f"QFrame {{ border-top: 1px solid rgba(255, 255, 255, 0.1); background-color: rgba(20, 22, 30, 0.5); border-radius: 8px; }}"
        )
        self.lbl_ps_hp.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {CRIMSON_RED}; font-family: {_FONT_TITLE}; border: none; background: transparent;")
        self.lbl_ps_equip.setStyleSheet(f"font-size: 12px; color: {DIM_COLOR}; border: none; background: transparent; font-family: {_FONT_BODY};")
        self.lbl_ps_bag.setStyleSheet(f"font-size: 12px; color: {DIM_COLOR}; border: none; background: transparent; font-family: {_FONT_BODY};")

    # ── Slots ─────────────────────────────────────────────────────────────────
    def update_state(self, payload: dict) -> None:
        room  = payload["room"]
        exits = payload["exits"]
        self.lbl_room.setText(room["name"])
        if exits:
            self.lbl_exits.setText(f"Paths:  " + "  •  ".join(f"[{d.upper()}]" for d in exits.keys()))
        else:
            self.lbl_exits.setText("No Way Out.")
            
        if room.get("bg_image", ""):
            self._image_widget.set_image(room["bg_image"])

    def set_status(self, text: str) -> None:
        self.lbl_status.setText(text)
        
    def show_listening(self) -> None:
        self.lbl_status.setText("••• Listening •••")
        self.lbl_status.setStyleSheet(f"font-size: 13px; color: #00FFCC; font-style: italic; font-family: {_FONT_BODY};")

    def update_narration(self, text: str) -> None:
        self.lbl_status.setStyleSheet(f"font-size: 13px; color: {STATUS_COLOR}; font-style: italic; font-family: {_FONT_BODY};")
        self.lbl_narration.setText(text)

    def update_room_items(self, items: list[dict]) -> None:
        if items:
            parts = [f"Found: {i['name']}" for i in items]
            self.lbl_room_items.setText("  |  ".join(parts))
            self._items_row.setVisible(True)
        else:
            self._items_row.setVisible(False)

    def show_monster_row(self, name: str, hp: int, max_hp: int) -> None:
        self.lbl_monster.setText(f"⚔️ {name}  [ {hp}/{max_hp} HP ]")
        self._monster_row.setVisible(True)

    def hide_monster_row(self) -> None:
        self._monster_row.setVisible(False)

    # ── Dashboard Slots ──
    def update_player_hp(self, hp: int, max_hp: int) -> None:
        self.lbl_ps_hp.setText(f"{hp}/{max_hp} HP")

    def update_player_status(self, payload: dict) -> None:
        equipped = payload.get("equipped", {})
        bag = payload.get("bag", [])

        w = equipped.get("weapon")
        w_text = f"{w['name']} (ATK {w.get('damage', 0)})" if w else "[none]"
        
        armors = [f"{equipped[s]['name']}" for s in ("helmet", "suit", "legs", "shoes", "cloak", "shield") if equipped.get(s)]
        a_text = ", ".join(armors) if armors else "[none]"
        
        self.lbl_ps_equip.setText(f"Weapon: {w_text}   |   Armor: {a_text}")
        self.lbl_ps_bag.setText("Bag: " + ", ".join(i["name"] for i in bag) if bag else "Bag: Empty")