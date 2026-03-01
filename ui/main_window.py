import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow, QMessageBox, QVBoxLayout, QWidget

from config import BG_COLOR, TEXT_COLOR, FONT_BODY
from ui.game_view import GameView
from ui.signals import AppSignals

class MainWindow(QMainWindow):
    """
    Root window in Portrait/Mobile-style. Owns GameView and handles hold-to-talk.
    MapPanel has been completely removed to focus on the cinematic UI.
    """

    def __init__(self, signals: AppSignals, controller):
        super().__init__()
        self._signals    = signals
        self._controller = controller
        self._recording  = False

        self.setWindowTitle("Voice of the Dungeon")
        self.setWindowIcon(QIcon("assets/icons/boss_icon.png"))
        # Format Portrait: Lebar 480px, Tinggi 850px
        self.setMinimumSize(520, 900)
        self.resize(480, 850)
        
        # Menggunakan fallback font Lora/Georgia
        self.setStyleSheet(f"background-color: {BG_COLOR}; color: {TEXT_COLOR}; font-family: 'Lora', 'Georgia', serif;")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._game_view = GameView()
        layout.addWidget(self._game_view)

        self._connect_signals()

        self.setFocus()
        self.activateWindow()

    # ── Signal wiring ─────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._signals.state_updated.connect(self._on_state_updated)

        self._signals.narration_started.connect(lambda: self._game_view.set_status("Narrating..."))
        self._signals.narration_text.connect(self._game_view.update_narration)
        self._signals.narration_finished.connect(lambda: self._game_view.set_status("Ready  —  Hold [SPACE] to speak"))
        self._signals.listening_started.connect(self._game_view.show_listening)
        self._signals.processing_started.connect(lambda: self._game_view.set_status("Processing..."))
        self._signals.processing_finished.connect(lambda: self._game_view.set_status("Ready  —  Hold [SPACE] to speak"))
        self._signals.error_occurred.connect(self._on_error)
        self._signals.game_won.connect(self._on_game_won)
        self._signals.game_over.connect(self._on_game_over)

        # Phase 2 — combat + items (Dialihkan ke GameView)
        self._signals.combat_started.connect(self._on_combat_started)
        self._signals.combat_updated.connect(self._on_combat_updated)
        self._signals.combat_ended.connect(self._game_view.hide_monster_row)
        self._signals.inventory_updated.connect(self._game_view.update_player_status)
        self._signals.room_items_changed.connect(self._game_view.update_room_items)

    # ── Key events (hold-to-talk) ─────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._controller.reset_game_state()
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat() and not self._recording:
            self._recording = True
            self._game_view.show_listening()
            self._controller.on_recording_started()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat() and self._recording:
            self._recording = False
            self._controller.on_recording_stopped()
        else:
            super().keyReleaseEvent(event)

    # ── Signal slots ──────────────────────────────────────────────────────────

    def _on_error(self, message: str) -> None:
        logging.warning(f"MainWindow: error — {message}")
        self._game_view.set_status(f"⚠  {message}")

    def _on_game_won(self, room_name: str, wav_path: str) -> None:
        self._game_view.set_status("YOU ESCAPED THE DUNGEON!")
        QMessageBox.information(self, "Victory!", f"You reached {room_name}.\n\nYou escaped the dungeon.\n\n(Close to play again.)")
        self._controller.restart_after_death()

    def _on_game_over(self, narration_text: str, wav_path: str) -> None:
        self._game_view.set_status("YOU DIED")
        QMessageBox.critical(self, "Game Over", f"{narration_text}\n\n(Close to play again.)")
        self._controller.restart_after_death()

    def _on_state_updated(self, payload: dict) -> None:
        self._game_view.update_state(payload)
        player = payload.get("player", {})
        self._game_view.update_player_hp(player.get("hp", 0), player.get("max_hp", 0))

    def _on_combat_started(self, payload: dict) -> None:
        self._game_view.show_monster_row(payload["name"], payload["enemy_hp"], payload["enemy_max_hp"])
        self._game_view.update_player_hp(payload["player_hp"], payload["player_max_hp"])
        self._game_view.set_status("IN COMBAT  —  Hold [SPACE] to attack")

    def _on_combat_updated(self, payload: dict) -> None:
        enemy = self._controller._current_enemy
        enemy_name = enemy["name"] if enemy else "Enemy"
        self._game_view.show_monster_row(enemy_name, payload["enemy_hp"], payload["enemy_max_hp"])
        self._game_view.update_player_hp(payload["player_hp"], payload["player_max_hp"])