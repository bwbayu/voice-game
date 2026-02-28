import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QTextEdit, QGroupBox,
    QSplitter, QStatusBar
)
from PyQt6.QtCore import Qt


# ─────────────────────────────────────────────
#  PATHS — adjust if you move the JSON files
# ─────────────────────────────────────────────
MAP_FILE    = Path(__file__).parent / "dungeon_map.json"
PLAYER_FILE = Path(__file__).parent / "player_state.json"


# ─────────────────────────────────────────────
#  GAME STATE — pure logic, no UI dependency
# ─────────────────────────────────────────────
class GameState:
    """
    Manages map data and player state.
    All mutations go through this class so the UI
    just calls methods and re-reads state.
    """

    def __init__(self, map_file: Path, player_file: Path):
        self.map_file    = map_file
        self.player_file = player_file
        self._map        = self._load(map_file)
        self._player     = self._load(player_file)

    # ── I/O ──────────────────────────────────
    def _load(self, path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self):
        """Persist current player state back to JSON."""
        with open(self.player_file, "w", encoding="utf-8") as f:
            json.dump(self._player, f, indent=2, ensure_ascii=False)

    # ── Read helpers ─────────────────────────
    @property
    def rooms(self) -> dict:
        return self._map["dungeon_map"]

    @property
    def player(self) -> dict:
        return self._player["player"]

    def current_room(self) -> dict:
        return self.rooms[self.player["current_room"]]

    def available_exits(self) -> dict:
        """Returns {direction: room_id} for the current room."""
        return self.current_room().get("exits", {})

    def items_in_room(self) -> list:
        return self.current_room().get("items", [])

    # ── Actions ──────────────────────────────
    def move(self, direction: str) -> tuple[bool, str]:
        """
        Attempt to move in a direction.
        Returns (success: bool, message: str).
        """
        exits = self.available_exits()
        if direction not in exits:
            return False, f"Tidak ada jalan ke arah '{direction}'."

        target_room_id = exits[direction]
        self.player["current_room"] = target_room_id
        self.player["last_action"]  = f"bergerak ke arah {direction}"
        return True, f"Kamu bergerak ke arah {direction}."

    def pick_up(self, item: str) -> tuple[bool, str]:
        """
        Pick up an item from the current room into inventory.
        Returns (success: bool, message: str).
        """
        room_items = self.current_room().get("items", [])
        if item not in room_items:
            return False, f"Item '{item}' tidak ada di ruangan ini."

        room_items.remove(item)
        self.player["inventory"].append(item)
        self.player["last_action"] = f"mengambil {item}"
        return True, f"Kamu mengambil '{item}'."


# ─────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────
class MainWindow(QMainWindow):

    def __init__(self, game: GameState):
        super().__init__()
        self.game = game
        self.setWindowTitle("Dungeon Explorer — Dev View")
        self.setMinimumSize(800, 560)
        self._build_ui()
        self._refresh()

    # ── Build UI ─────────────────────────────
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter)

        # ── Left panel: room info + exits ────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(8)

        room_group = QGroupBox("Ruangan Saat Ini")
        room_vbox  = QVBoxLayout(room_group)
        self.lbl_room_name = QLabel()
        self.lbl_room_name.setWordWrap(True)
        self.txt_room_desc = QTextEdit()
        self.txt_room_desc.setReadOnly(True)
        self.txt_room_desc.setFixedHeight(70)
        room_vbox.addWidget(self.lbl_room_name)
        room_vbox.addWidget(self.txt_room_desc)
        left_layout.addWidget(room_group)

        exits_group = QGroupBox("Jalan Keluar")
        self.exits_layout = QVBoxLayout(exits_group)
        left_layout.addWidget(exits_group)

        items_group = QGroupBox("Item di Ruangan")
        items_vbox  = QVBoxLayout(items_group)
        self.list_room_items = QListWidget()
        self.list_room_items.setFixedHeight(100)
        self.btn_pickup = QPushButton("Ambil Item yang Dipilih")
        self.btn_pickup.clicked.connect(self._on_pickup)
        items_vbox.addWidget(self.list_room_items)
        items_vbox.addWidget(self.btn_pickup)
        left_layout.addWidget(items_group)

        left_layout.addStretch()
        splitter.addWidget(left)

        # ── Right panel: player state + log ──
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setSpacing(8)

        player_group = QGroupBox("Status Pemain")
        player_vbox  = QVBoxLayout(player_group)
        self.lbl_health      = QLabel()
        self.lbl_current_room = QLabel()
        self.lbl_last_action = QLabel()
        self.lbl_last_action.setWordWrap(True)
        player_vbox.addWidget(self.lbl_health)
        player_vbox.addWidget(self.lbl_current_room)
        player_vbox.addWidget(self.lbl_last_action)
        right_layout.addWidget(player_group)

        inv_group = QGroupBox("Inventori")
        inv_vbox  = QVBoxLayout(inv_group)
        self.list_inventory = QListWidget()
        inv_vbox.addWidget(self.list_inventory)
        right_layout.addWidget(inv_group)

        log_group = QGroupBox("Log Aksi")
        log_vbox  = QVBoxLayout(log_group)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        log_vbox.addWidget(self.txt_log)
        right_layout.addWidget(log_group)

        splitter.addWidget(right)
        splitter.setSizes([420, 360])

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    # ── Refresh UI from game state ────────────
    def _refresh(self):
        p    = self.game.player
        room = self.game.current_room()

        # Room info
        self.lbl_room_name.setText(f"<b>{room['name']}</b>")
        self.txt_room_desc.setText(room["description"])

        # Exits — rebuild buttons each refresh
        for i in reversed(range(self.exits_layout.count())):
            widget = self.exits_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        exits = self.game.available_exits()
        if exits:
            for direction, target_id in exits.items():
                target_name = self.game.rooms[target_id]["name"]
                btn = QPushButton(f"[{direction.upper()}]  →  {target_name}")
                btn.clicked.connect(lambda _, d=direction: self._on_move(d))
                self.exits_layout.addWidget(btn)
        else:
            self.exits_layout.addWidget(QLabel("Tidak ada jalan keluar."))

        # Room items
        self.list_room_items.clear()
        for item in self.game.items_in_room():
            self.list_room_items.addItem(item)

        # Player status
        self.lbl_health.setText(f"❤️  Health       : {p['health']}")
        self.lbl_current_room.setText(f"📍 Lokasi       : {p['current_room']}")
        self.lbl_last_action.setText(f"🕹️  Aksi Terakhir: {p['last_action']}")

        # Inventory
        self.list_inventory.clear()
        if p["inventory"]:
            for item in p["inventory"]:
                self.list_inventory.addItem(item)
        else:
            self.list_inventory.addItem("(kosong)")

    def _log(self, message: str):
        self.txt_log.append(f"▸ {message}")

    # ── Action handlers ───────────────────────
    def _on_move(self, direction: str):
        success, msg = self.game.move(direction)
        self._log(msg)
        if success:
            self.game.save()
            self._refresh()
            self.status_bar.showMessage(msg, 3000)

    def _on_pickup(self):
        selected = self.list_room_items.currentItem()
        if not selected:
            self._log("Pilih item terlebih dahulu.")
            return
        success, msg = self.game.pick_up(selected.text())
        self._log(msg)
        if success:
            self.game.save()
            self._refresh()
            self.status_bar.showMessage(msg, 3000)


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app   = QApplication(sys.argv)
    game  = GameState(MAP_FILE, PLAYER_FILE)
    window = MainWindow(game)
    window.show()
    sys.exit(app.exec())