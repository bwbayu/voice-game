"""
Voice of the Dungeon — Phase 1 entry point.

Startup sequence:
  1. Create QApplication
  2. Instantiate AppSignals (must be on main thread before any QThread starts)
  3. Instantiate GameController (loads map, state, AI clients, audio)
  4. Instantiate MainWindow (wires signals to UI slots)
  5. Show window
  6. QTimer.singleShot(100ms) → controller.start_game()
     The 100ms delay ensures Qt's event loop is running before the first
     QThread (NarrationWorker) is spawned.
"""

import logging
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from game.game_controller import GameController
from ui.main_window import MainWindow
from ui.signals import AppSignals

# Configure basic logging for development visibility
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Voice of the Dungeon")

    # Signal bus — must exist on main thread before any workers start
    signals = AppSignals()

    # GameController owns all subsystems; initialised on main thread
    controller = GameController(signals)

    # MainWindow wires AppSignals to UI slots
    window = MainWindow(signals, controller)
    window.show()

    # Trigger first room narration after the event loop is running
    QTimer.singleShot(100, controller.start_game)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
