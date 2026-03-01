from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QScrollArea, QProgressBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QLinearGradient, QColor, QBrush

from config import (
    BG_COLOR, TEXT_COLOR, ACCENT_COLOR, STATUS_COLOR, 
    CRIMSON_RED, DIM_COLOR, ASSETS_DIR
)

_ICONS_DIR = ASSETS_DIR / "icons"
_ICON_SIZE  = 28
_MONSTER_ICON_SIZE = 48 # Ikon monster dibuat lebih besar

_ITEM_ICONS_DIR = ASSETS_DIR / "item_icons"
_ITEM_ICON_SIZE = 42

# Font Stacks
_FONT_TITLE = "'Cinzel', 'Georgia', serif"
_FONT_BODY  = "'Lora', 'Georgia', 'Times New Roman', serif"

_SLOT_ICON: dict[str, str] = {
    "weapon": "weapon.png",
    "helmet": "helmet.png",
    "suit":   "suit.png",
    "legs":   "legs.png",
    "shoes":  "shoes.png",
    "cloak":  "cloak.png",
    "shield": "shield.png",
    "key":    "key.png",
    "potion": "potion.png",
}

_ALL_SLOTS: list[tuple[str, str, str]] = [
    ("weapon", "Weapon",  "weapon.png"),
    ("helmet", "Helmet",  "helmet.png"),
    ("suit",   "Armor",   "suit.png"),
    ("legs",   "Legs",    "legs.png"),
    ("shoes",  "Shoes",   "shoes.png"),
    ("cloak",  "Cloak",   "cloak.png"),
    ("shield", "Shield",  "shield.png"),
    ("key",    "Key",     "key.png"),
    ("potion", "Potion",  "potion.png"),
]

# Tambahkan direktori baru untuk gambar musuh
_MONSTERS_DIR = ASSETS_DIR / "monsters"

# Mapping Nama Musuh ke ID Gambar (berdasarkan JSON)
_MONSTER_IMG_MAP = {
    "The Dark Guardian": "guardian.png",
    "Wandering Shade": "shade.png",
    "Dungeon Crawler": "crawler.png"
}

def _load_monster_image(name: str, size: int) -> QPixmap | None:
    """Memuat gambar monster dengan resolusi tinggi."""
    filename = _MONSTER_IMG_MAP.get(name)
    if filename:
        px = QPixmap(str(_MONSTERS_DIR / filename))
        if not px.isNull():
            # Menggunakan SmoothTransformation agar gambar besar tidak pecah
            return px.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    
    # Fallback tetap menggunakan boss_icon
    px = QPixmap(str(_ICONS_DIR / "boss_icon.png"))
    if not px.isNull():
        return px.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return None

def _load_icon(name: str, size: int = _ICON_SIZE) -> QPixmap | None:
    px = QPixmap(str(_ICONS_DIR / name))
    if px.isNull(): return None
    return px.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

class RoomImageWidget(QWidget):
    """Custom widget for top-half image with Combat Dimming and Large Monster Overlay."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap: QPixmap | None = None
        self.setFixedHeight(350) 
        self._is_combat = False # Flag untuk efek dimming
        self._build_monster_overlay()

    def _build_monster_overlay(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.monster_container = QWidget()
        self.monster_container.setStyleSheet("background: transparent;")
        
        overlay_layout = QVBoxLayout(self.monster_container)
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setSpacing(12)

        # 1. Nama Monster (Warna Emas/Putih + Shadow Tebal agar terbaca)
        self.lbl_m_name = QLabel("Unknown Threat")
        self.lbl_m_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_m_name.setWordWrap(True)
        # Menggunakan warna ACCENT_COLOR agar kontras dengan background gelap
        self.lbl_m_name.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {ACCENT_COLOR}; "
            f"background: transparent; border: none; font-family: {_FONT_TITLE};"
        )
        
        # Shadow dibuat sangat tebal (Blur 15, Offset 0) untuk menciptakan 'outline' hitam
        name_shadow = QGraphicsDropShadowEffect(self)
        name_shadow.setBlurRadius(15)
        name_shadow.setColor(QColor(0, 0, 0, 255))
        name_shadow.setOffset(0, 0)
        self.lbl_m_name.setGraphicsEffect(name_shadow)
        overlay_layout.addWidget(self.lbl_m_name)

        # 2. Visual HP Bar (Banner Transparan Halus di belakangnya)
        self.bar_m_hp = QProgressBar()
        self.bar_m_hp.setFixedWidth(220)
        self.bar_m_hp.setFixedHeight(18)
        self.bar_m_hp.setTextVisible(True)
        self.bar_m_hp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bar_m_hp.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(0, 0, 0, 200);
                border: 1px solid {ACCENT_COLOR};
                border-radius: 4px;
                color: #FFFFFF;
                font-size: 12px;
                font-weight: bold;
                font-family: {_FONT_BODY};
            }}
            QProgressBar::chunk {{
                background-color: {CRIMSON_RED};
                border-radius: 3px;
            }}
        """)
        
        hp_layout = QHBoxLayout()
        hp_layout.addStretch()
        hp_layout.addWidget(self.bar_m_hp)
        hp_layout.addStretch()
        overlay_layout.addLayout(hp_layout)

        # 3. Ikon / Gambar Monster (Sangat Besar: 280px)
        self.lbl_m_icon = QLabel()
        self.lbl_m_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_m_icon.setStyleSheet("background: transparent; border: none;")
        
        img_shadow = QGraphicsDropShadowEffect(self)
        img_shadow.setBlurRadius(25)
        img_shadow.setColor(QColor(0, 0, 0, 200))
        img_shadow.setOffset(0, 5)
        self.lbl_m_icon.setGraphicsEffect(img_shadow)
        
        overlay_layout.addWidget(self.lbl_m_icon)

        main_layout.addWidget(self.monster_container)
        self.monster_container.setVisible(False)

    def set_image(self, path: str) -> None:
        self.pixmap = QPixmap(path)
        self.update()

    def show_monster(self, name: str, hp: int, max_hp: int):
        self._is_combat = True
        self.lbl_m_name.setText(name)
        self.bar_m_hp.setMaximum(max_hp)
        self.bar_m_hp.setValue(hp)
        self.bar_m_hp.setFormat(f"{hp} / {max_hp} HP")
        
        # Scale Up Monster ke 280px agar mendominasi layar
        px = _load_monster_image(name, 300)
        if px: 
            self.lbl_m_icon.setPixmap(px)
        
        self.monster_container.setVisible(True)
        self.update() # Memicu paintEvent untuk efek dimming

    def hide_monster(self):
        self._is_combat = False
        self.monster_container.setVisible(False)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if self.pixmap and not self.pixmap.isNull():
            scaled = self.pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            crop_x = (scaled.width() - self.width()) // 2
            crop_y = (scaled.height() - self.height()) // 2
            painter.drawPixmap(0, 0, scaled, crop_x, crop_y, self.width(), self.height())
            
        # EFEK DIMMING: Jika sedang combat, tambahkan layer hitam transparan di atas background
        if self._is_combat:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 140)) # 140/255 kegelapan
            
        # Fade-out gradient ke arah UI bawah (selalu ada)
        grad = QLinearGradient(0, self.height() - 80, 0, self.height())
        grad.setColorAt(0, QColor(11, 12, 16, 0))
        grad.setColorAt(1, QColor(11, 12, 16, 255))
        painter.fillRect(self.rect(), QBrush(grad))


class GameView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._slot_cards: dict[str, tuple[QFrame, QLabel, QLabel]] = {}
        self._build_ui()
        self._apply_styles()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 1. Top Half: Image Container + Monster Overlay ──
        self._image_widget = RoomImageWidget()
        main_layout.addWidget(self._image_widget)

        # ── 2. Bottom Half: UI Container ──
        self._ui_container = QWidget()
        ui_layout = QVBoxLayout(self._ui_container)
        ui_layout.setContentsMargins(25, 10, 25, 25)
        
        # Room Name (Judul "BLIND DUNGEON" Dihapus)
        self.lbl_room = QLabel("—")
        self.lbl_room.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_room.setWordWrap(True)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 2)
        self.lbl_room.setGraphicsEffect(shadow)
        ui_layout.addWidget(self.lbl_room)

        ui_layout.addSpacing(15)

        # Narration
        self.lbl_narration = QLabel("")
        self.lbl_narration.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_narration.setWordWrap(True)
        self.lbl_narration.setMinimumHeight(80)
        ui_layout.addWidget(self.lbl_narration)
        
        ui_layout.addStretch()

        # Item Found Rows (Cards format)
        self._items_row = QWidget()
        items_h = QHBoxLayout(self._items_row)
        items_h.setContentsMargins(0, 0, 0, 0)
        items_h.setSpacing(8)
        items_h.addStretch()
        items_h.addStretch() 
        self._items_layout = items_h
        self._items_row.setVisible(False)
        ui_layout.addWidget(self._items_row)

        ui_layout.addSpacing(15)

        # Exits & Mic Status
        self.lbl_exits = QLabel("Exits: —")
        self.lbl_exits.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ui_layout.addWidget(self.lbl_exits)

        self.lbl_status = QLabel("Initializing...")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ui_layout.addWidget(self.lbl_status)

        ui_layout.addSpacing(15)

        # ── 3. Player Dashboard ──
        self._build_dashboard(ui_layout)
        main_layout.addWidget(self._ui_container)

    def _build_dashboard(self, parent_layout: QVBoxLayout) -> None:
        self.dashboard_frame = QFrame()
        dash_layout = QVBoxLayout(self.dashboard_frame)
        dash_layout.setContentsMargins(15, 10, 15, 10)
        dash_layout.setSpacing(8)

        # HP Row
        hp_row = QWidget()
        hp_h = QHBoxLayout(hp_row)
        hp_h.setContentsMargins(0, 0, 0, 0)
        
        self._icon_heart = QLabel()
        px = _load_icon("heart.png")
        if px: self._icon_heart.setPixmap(px)
        
        self.lbl_ps_hp = QLabel("100/100 HP")
        hp_h.addWidget(self._icon_heart)
        hp_h.addWidget(self.lbl_ps_hp)
        hp_h.addStretch()
        dash_layout.addWidget(hp_row)

        # Horizontal Scroll Area for Inventory Slots
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:horizontal { height: 4px; background: rgba(0,0,0,0.5); border-radius: 2px; }"
            f"QScrollBar::handle:horizontal {{ background: {ACCENT_COLOR}; border-radius: 2px; }}"
        )
        scroll.setFixedHeight(105)

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        inner_h = QHBoxLayout(inner)
        inner_h.setContentsMargins(0, 4, 0, 4)
        inner_h.setSpacing(6)

        for slot_key, label, icon_file in _ALL_SLOTS:
            card, icon_lbl, name_lbl = self._make_slot_card(label, icon_file)
            self._slot_cards[slot_key] = (card, icon_lbl, name_lbl)
            inner_h.addWidget(card)
        inner_h.addStretch()

        scroll.setWidget(inner)
        dash_layout.addWidget(scroll)

        parent_layout.addWidget(self.dashboard_frame)

    def _make_item_card(self, item: dict) -> QFrame:
        card = QFrame()
        card.setFixedWidth(75)
        card.setStyleSheet(f"QFrame {{ background-color: transparent; border: 1px solid {ACCENT_COLOR}; border-radius: 6px; }}")
        v = QVBoxLayout(card)
        v.setContentsMargins(4, 6, 4, 6)
        v.setSpacing(4)

        icon_lbl = QLabel()
        icon_key  = item.get("slot") or item.get("type", "")
        icon_name = _SLOT_ICON.get(icon_key, "")
        if icon_name:
            px = QPixmap(str(_ITEM_ICONS_DIR / icon_name))
            if not px.isNull():
                px = px.scaled(_ITEM_ICON_SIZE, _ITEM_ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                icon_lbl.setPixmap(px)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        v.addWidget(icon_lbl)

        name_lbl = QLabel(item["name"])
        name_lbl.setWordWrap(True)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setStyleSheet("font-size: 9px; color: #c0c0d8; background: transparent; border: none; font-family: 'Lora', serif;")
        v.addWidget(name_lbl)
        return card

    def _make_slot_card(self, label: str, icon_file: str) -> tuple[QFrame, QLabel, QLabel]:
        card = QFrame()
        card.setFixedWidth(75)
        card.setStyleSheet("QFrame { background-color: rgba(20, 20, 32, 0.6); border: 1px solid #2a2a3a; border-radius: 6px; }")
        v = QVBoxLayout(card)
        v.setContentsMargins(4, 4, 4, 6)
        v.setSpacing(2)

        slot_lbl = QLabel(label)
        slot_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        slot_lbl.setStyleSheet(f"font-size: 9px; color: {DIM_COLOR}; background: transparent; border: none; font-family: 'Cinzel', serif;")
        v.addWidget(slot_lbl)

        icon_lbl = QLabel()
        px = QPixmap(str(_ITEM_ICONS_DIR / icon_file))
        if not px.isNull():
            px = px.scaled(_ITEM_ICON_SIZE, _ITEM_ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
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
        name_lbl.setStyleSheet("font-size: 9px; color: #444455; background: transparent; border: none; font-family: 'Lora', serif;")
        v.addWidget(name_lbl)

        return card, icon_lbl, name_lbl

    def _apply_styles(self) -> None:
        self._ui_container.setStyleSheet(f"background-color: {BG_COLOR};")
        
        # lbl_title dihapus, langsung styling judul ruangan
        self.lbl_room.setStyleSheet(f"font-size: 26px; font-weight: normal; color: #FFFFFF; font-family: {_FONT_TITLE};")
        self.lbl_narration.setStyleSheet(f"font-size: 14px; font-style: italic; color: {TEXT_COLOR}; line-height: 140%; font-family: {_FONT_BODY};")
        
        self.lbl_exits.setStyleSheet(f"font-size: 11px; color: {DIM_COLOR}; letter-spacing: 2px; font-family: {_FONT_TITLE}; border-top: 1px solid rgba(212, 175, 55, 0.2); padding-top: 10px;")
        self.lbl_status.setStyleSheet(f"font-size: 13px; color: {STATUS_COLOR}; font-style: italic; font-family: {_FONT_BODY};")

        self.dashboard_frame.setStyleSheet("QFrame { border-top: 1px solid rgba(255, 255, 255, 0.1); background-color: rgba(15, 16, 20, 0.8); border-radius: 8px; }")
        self.lbl_ps_hp.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {CRIMSON_RED}; font-family: {_FONT_TITLE}; border: none; background: transparent;")

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
        while self._items_layout.count() > 0:
            child = self._items_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

        if items:
            self._items_layout.addStretch()
            for item in items:
                self._items_layout.addWidget(self._make_item_card(item))
            self._items_layout.addStretch()
            self._items_row.setVisible(True)
        else:
            self._items_row.setVisible(False)

    def show_monster_row(self, name: str, hp: int, max_hp: int) -> None:
        # Alih-alih di bawah, sekarang kita tembak ke overlay di gambar!
        self._image_widget.show_monster(name, hp, max_hp)

    def hide_monster_row(self) -> None:
        # Sembunyikan overlay monster
        self._image_widget.hide_monster()

    # ── Dashboard Slots ──
    def update_player_hp(self, hp: int, max_hp: int) -> None:
        self.lbl_ps_hp.setText(f"{hp}/{max_hp} HP")

    def update_player_status(self, payload: dict) -> None:
        equipped = payload.get("equipped", {})
        bag      = payload.get("bag", [])

        for slot_key, (card, icon_lbl, name_lbl) in self._slot_cards.items():
            if slot_key in ("key", "potion"):
                match = next((i for i in bag if i.get("type") == slot_key), None)
                active    = match is not None
                item_name = match["name"] if match else ""
            else:
                item = equipped.get(slot_key)
                if slot_key == "weapon" and item and item.get("id") == "bare_hands":
                    active, item_name = False, ""
                else:
                    active, item_name = item is not None, item["name"] if item else ""

            if active:
                card.setStyleSheet(f"QFrame {{ background-color: rgba(212, 175, 55, 0.08); border: 1px solid {ACCENT_COLOR}; border-radius: 6px; }}")
                icon_lbl.graphicsEffect().setOpacity(1.0)
                name_lbl.setText(item_name)
                name_lbl.setStyleSheet(f"font-size: 9px; color: {TEXT_COLOR}; background: transparent; border: none; font-family: 'Lora', serif;")
            else:
                card.setStyleSheet("QFrame { background-color: rgba(20, 20, 32, 0.6); border: 1px solid #2a2a3a; border-radius: 6px; }")
                icon_lbl.graphicsEffect().setOpacity(0.2)
                name_lbl.setText("")
                name_lbl.setStyleSheet("font-size: 9px; color: #444455; background: transparent; border: none;")