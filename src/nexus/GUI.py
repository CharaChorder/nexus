import argparse
from threading import Thread

from PySide6.QtWidgets import QApplication, QPushButton, QStatusBar, QTableWidget, QTableWidgetItem, QMainWindow, \
    QDialog

from nexus.Freqlog import Freqlog
from nexus.ui.BanlistDialog import Ui_BanlistDialog
from nexus.ui.MainWindow import Ui_MainWindow


class MainWindow(QMainWindow, Ui_MainWindow):
    """Required because Qt is a PITA."""

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)


class BanlistDialog(QDialog, Ui_BanlistDialog):
    """Required because Qt is a PITA."""

    def __init__(self, *args, **kwargs):
        super(BanlistDialog, self).__init__(*args, **kwargs)
        self.setupUi(self)


class GUI(object):

    def __init__(self, args: argparse.Namespace):
        self.app = QApplication([])
        self.window = MainWindow()

        # Components
        self.start_stop_button: QPushButton = self.window.findChild(QPushButton, "startStop")  # type: ignore[assign]
        self.refresh_button: QPushButton = self.window.findChild(QPushButton, "refresh")  # type: ignore[assign]
        self.banlist_button: QPushButton = self.window.findChild(QPushButton, "banlist")  # type: ignore[assign]
        self.chentry_table: QTableWidget = self.window.findChild(QTableWidget, "chentryTable")  # type: ignore[assign]
        self.chord_table: QTableWidget = self.window.findChild(QTableWidget, "chordTable")  # type: ignore[assign]
        self.statusbar: QStatusBar = self.window.findChild(QStatusBar, "statusbar")  # type: ignore[assign]

        # Signals
        self.start_stop_button.clicked.connect(self.start_stop)
        self.refresh_button.clicked.connect(self.refresh)
        self.banlist_button.clicked.connect(self.show_banlist)

        self.freqlog: Freqlog | None = None
        self.logging_thread: Thread | None = None
        self.args = args

    def start_logging(self):
        self.freqlog = Freqlog(self.args.freq_log_path)
        self.freqlog.start_logging()

    def stop_logging(self):
        self.freqlog.stop_logging()

    def start_stop(self):
        if self.start_stop_button.text() == "Start logging":
            # Update button to starting
            # TODO: fix signal blocking (not currently working)
            self.start_stop_button.blockSignals(True)
            self.start_stop_button.setEnabled(False)
            self.start_stop_button.setText("Starting...")
            self.start_stop_button.setStyleSheet("background-color: yellow")
            self.window.repaint()

            # Start freqlogging
            self.logging_thread = Thread(target=self.start_logging)
            self.logging_thread.start()

            # Update button to stop
            while not (self.freqlog and self.freqlog.is_logging):
                pass
            self.start_stop_button.setText("Stop logging")
            self.start_stop_button.setStyleSheet("background-color: red")
            self.start_stop_button.setEnabled(True)
            self.start_stop_button.blockSignals(False)
            self.statusbar.showMessage("Logging started")
            self.window.repaint()
        else:
            # Update button to stopping
            self.start_stop_button.setText("Stopping...")
            self.start_stop_button.setStyleSheet("background-color: yellow")
            self.start_stop_button.blockSignals(True)
            self.start_stop_button.setEnabled(False)
            self.window.repaint()

            # Stop freqlogging
            Thread(target=self.stop_logging).start()

            # Update button to start
            self.logging_thread.join()
            self.start_stop_button.setText("Start logging")
            self.start_stop_button.setStyleSheet("background-color: green")
            self.start_stop_button.setEnabled(True)
            self.start_stop_button.blockSignals(False)
            self.statusbar.showMessage("Logging stopped")
            self.window.repaint()

    def refresh(self):
        self.freqlog = Freqlog(self.args.freq_log_path)
        words = self.freqlog.list_words()
        self.chentry_table.setRowCount(len(words))
        for i, word in enumerate(words):
            self.chentry_table.setItem(i, 0, QTableWidgetItem(word.word))
            self.chentry_table.setItem(i, 1, QTableWidgetItem(str(word.frequency)))
            self.chentry_table.setItem(
                i, 2, QTableWidgetItem(str(word.last_used.isoformat(sep=" ", timespec="seconds"))))
            self.chentry_table.setItem(i, 3, QTableWidgetItem(str(word.average_speed)[2:-3]))
        self.chentry_table.resizeColumnsToContents()
        self.statusbar.showMessage(f"Loaded {len(words)} freqlogged words")

    def show_banlist(self):
        banlist_case, banlist_caseless = self.freqlog.list_banned_words()
        dialog = BanlistDialog()
        dialog.banlistTable.setRowCount(len(banlist_case) + len(banlist_caseless))
        for i, word in enumerate(banlist_case):
            dialog.banlistTable.setItem(i, 0, QTableWidgetItem(word.word))
            dialog.banlistTable.setItem(i, 1,
                                        QTableWidgetItem(str(word.date_added.isoformat(sep=" ", timespec="seconds"))))
            dialog.banlistTable.setItem(i, 2, QTableWidgetItem("Sensitive"))
        for i, word in enumerate(banlist_caseless):
            dialog.banlistTable.setItem(i + len(banlist_case), 0, QTableWidgetItem(word.word))
            dialog.banlistTable.setItem(i + len(banlist_case), 1,
                                        QTableWidgetItem(str(word.date_added.isoformat(sep=" ", timespec="seconds"))))
            dialog.banlistTable.setItem(i + len(banlist_case), 2, QTableWidgetItem("Insensitive"))
        dialog.banlistTable.resizeColumnsToContents()
        dialog.exec()

    def exec(self):
        self.window.show()
        self.refresh()
        self.app.exec()
