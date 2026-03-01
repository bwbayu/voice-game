import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow, QMessageBox, QWidget, QHBoxLayout

from config import BG_COLOR, TEXT_COLOR
from ui.game_view import GameView
from ui.map_panel import MapPanel
from ui.signals import AppSignals


class MainWindow(QMainWindow):
    """
    Root window. Owns GameView and handles the hold-to-talk key events.
    Connects all AppSignals to UI slot methods.

    Key contract:
      - keyPressEvent(Space, not auto-repeat, not already recording)
            → self._recording = True
            → controller.on_recording_started()
      - keyReleaseEvent(Space, not auto-repeat, currently recording)
            → self._recording = False
            → controller.on_recording_stopped()

    The _recording flag prevents key-repeat events on Windows from
    calling on_recording_started() multiple times per press.
    """

    def __init__(self, signals: AppSignals, controller):
        super().__init__()
        self._signals    = signals
        self._controller = controller
        self._recording  = False

        self.setWindowTitle("Blind Dungeon")
        self.setMinimumSize(1200, 650)
        self.setStyleSheet(f"background-color: {BG_COLOR}; color: {TEXT_COLOR};")

        # Central widget — game view (left, stretches) + map panel (right, fixed width)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._game_view = GameView()
        layout.addWidget(self._game_view, stretch=1)

        self._map_panel = MapPanel()
        layout.addWidget(self._map_panel, stretch=0)

        self._connect_signals()

        # Grab keyboard focus so Space key events are received immediately
        self.setFocus()
        self.activateWindow()

    # ── Signal wiring ─────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        # state_updated feeds both the game view and the player HP in the status panel
        self._signals.state_updated.connect(self._on_state_updated)

        self._signals.narration_started.connect(
            lambda: self._game_view.set_status("Narrating...")
        )
        self._signals.narration_text.connect(self._game_view.update_narration)
        self._signals.narration_finished.connect(
            lambda: self._game_view.set_status("Ready  —  Hold [SPACE] to speak")
        )
        self._signals.listening_started.connect(
            self._game_view.show_listening
        )
        self._signals.processing_started.connect(
            lambda: self._game_view.set_status("Processing...")
        )
        self._signals.processing_finished.connect(
            lambda: self._game_view.set_status("Ready  —  Hold [SPACE] to speak")
        )
        self._signals.error_occurred.connect(self._on_error)
        self._signals.game_won.connect(self._on_game_won)
        self._signals.game_over.connect(self._on_game_over)

        # Phase 2 — combat + items
        self._signals.combat_started.connect(self._on_combat_started)
        self._signals.combat_updated.connect(self._on_combat_updated)
        self._signals.combat_ended.connect(self._game_view.hide_monster_row)
        self._signals.inventory_updated.connect(self._map_panel.update_player_status)
        self._signals.room_items_changed.connect(self._game_view.update_room_items)

        # Phase 3.2 — dungeon map panel
        self._signals.map_state_changed.connect(self._map_panel.update_map)

    # ── Key events (hold-to-talk) ─────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Reset game state on close so the next launch starts fresh."""
        self._controller.reset_game_state()
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:
        """
        Space key down → start recording.
        Guards:
          - isAutoRepeat(): Windows generates repeated keyPress events while
            a key is held. We must ignore these or start_recording is called
            many times per second.
          - self._recording: prevents double-triggering if somehow called twice.
        """
        if (
            event.key() == Qt.Key.Key_Space
            and not event.isAutoRepeat()
            and not self._recording
        ):
            self._recording = True
            self._game_view.show_listening()
            self._controller.on_recording_started()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        """Space key up → stop recording and trigger STT processing."""
        if (
            event.key() == Qt.Key.Key_Space
            and not event.isAutoRepeat()
            and self._recording
        ):
            self._recording = False
            self._controller.on_recording_stopped()
        else:
            super().keyReleaseEvent(event)

    # ── Signal slots ──────────────────────────────────────────────────────────

    def _on_error(self, message: str) -> None:
        logging.warning(f"MainWindow: error — {message}")
        self._game_view.set_status(f"⚠  {message}")

    def _on_game_won(self, room_name: str, wav_path: str) -> None:
        """Victory! Show a dialog after the TTS clip starts playing."""
        self._game_view.set_status("YOU ESCAPED THE DUNGEON!")
        QMessageBox.information(
            self,
            "Victory!",
            f"You have reached {room_name}.\n\n"
            "You escaped the dungeon and lived to tell the tale.\n\n"
            "(Close this dialog to play again.)",
        )
        self._controller.restart_after_death()

    def _on_game_over(self, narration_text: str, wav_path: str) -> None:
        """Player died. Show a dialog, then restart."""
        self._game_view.set_status("YOU DIED")
        QMessageBox.critical(
            self,
            "Game Over",
            f"{narration_text}\n\n(Close this dialog to play again.)",
        )
        self._controller.restart_after_death()

    def _on_state_updated(self, payload: dict) -> None:
        """Forward state to game view and sync player HP in the status panel."""
        self._game_view.update_state(payload)
        player = payload.get("player", {})
        self._map_panel.update_player_hp(
            player.get("hp", 0), player.get("max_hp", 0)
        )

    def _on_combat_started(self, payload: dict) -> None:
        """Show monster row in game view and update HP in player status panel."""
        self._game_view.show_monster_row(
            payload["name"], payload["enemy_hp"], payload["enemy_max_hp"]
        )
        self._map_panel.update_player_hp(payload["player_hp"], payload["player_max_hp"])
        self._game_view.set_status("IN COMBAT  —  Hold [SPACE] to attack")

    def _on_combat_updated(self, payload: dict) -> None:
        """Refresh monster row and player HP after each combat round."""
        enemy      = self._controller._current_enemy
        enemy_name = enemy["name"] if enemy else "Enemy"
        self._game_view.show_monster_row(
            enemy_name, payload["enemy_hp"], payload["enemy_max_hp"]
        )
        self._map_panel.update_player_hp(payload["player_hp"], payload["player_max_hp"])
