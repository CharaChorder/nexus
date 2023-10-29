import argparse
import os
from threading import Thread
from pathlib import Path
from typing import Literal

from PySide6.QtCore import Qt, QTranslator, QLocale
from PySide6.QtWidgets import QApplication, QPushButton, QStatusBar, QTableWidget, QTableWidgetItem, QMainWindow, \
    QDialog, QFileDialog, QDialogButtonBox, QVBoxLayout, QLabel, QMenu, QSystemTrayIcon
from PySide6.QtGui import QIcon, QAction

from nexus import __id__, __version__
from nexus.Freqlog import Freqlog
from nexus.ui.BanlistDialog import Ui_BanlistDialog
from nexus.ui.BanwordDialog import Ui_BanwordDialog
from nexus.ui.MainWindow import Ui_MainWindow
from nexus.style import Stylesheet, Colors

from nexus.Freqlog.Definitions import CaseSensitivity, WordMetadataAttr, WordMetadataAttrLabel, WordMetadata, \
    Defaults, ChordMetadataAttr, ChordMetadataAttrLabel, ChordMetadata

if os.name == 'nt':  # Needed for taskbar icon on Windows
    import ctypes

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{__id__}.{__version__}")


class MainWindow(QMainWindow, Ui_MainWindow):
    """Set up the main window. Required because Qt is a PITA."""

    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)


class BanlistDialog(QDialog, Ui_BanlistDialog):
    """Set up the banlist dialog. Required because Qt is a PITA."""

    def __init__(self):
        super(BanlistDialog, self).__init__()
        self.setupUi(self)


class BanwordDialog(QDialog, Ui_BanwordDialog):
    """Set up the banword dialog. Required because Qt is a PITA."""

    def __init__(self):
        super(BanwordDialog, self).__init__()
        self.setupUi(self)


class ConfirmDialog(QDialog):
    def __init__(self, title: str, message: str):
        super().__init__()
        self.setWindowTitle(title)
        buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        self.buttonBox = QDialogButtonBox(buttons)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.layout = QVBoxLayout()
        msg_label = QLabel(message)
        self.layout.addWidget(msg_label)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)


class Translator(QTranslator):
    """Custom translator"""

    def translate(self, context: str, source: str, disambiguation=None, n=-1):
        final = super().translate(context, source, disambiguation, n)  # type: ignore[no-untyped-call]
        if final:
            return final
        return source


class GUI(object):
    """Nexus GUI"""

    def __init__(self, args: argparse.Namespace):
        """Initialize GUI"""
        self.app = QApplication([])
        self.window = MainWindow()

        script_parent_path = str(Path(__file__).resolve().parent)

        # Translation
        self.translator: Translator = Translator(self.app)
        if self.translator.load(QLocale.system(), 'i18n', '_', os.path.join(script_parent_path, 'translations')):
            self.app.installTranslator(self.translator)
        self.tr = self.translator.translate

        # System tray
        self.nexus_icon = QIcon(":images/icon.ico")
        self.tray = QSystemTrayIcon()
        self.tray.activated.connect(self.show_hide)
        self.tray.setIcon(self.nexus_icon)
        self.tray.setVisible(True)

        # System tray menu
        self.tray_menu = QMenu()
        self.start_stop_tray_menu_action = QAction(self.tr("GUI", "Start/stop logging"))
        self.quit_tray_menu_action = QAction(self.tr("GUI", "Quit"))
        self.start_stop_tray_menu_action.triggered.connect(self.start_stop)
        self.quit_tray_menu_action.triggered.connect(self.app.quit)
        self.tray_menu.addAction(self.start_stop_tray_menu_action)
        self.tray_menu.addAction(self.quit_tray_menu_action)
        self.tray.setContextMenu(self.tray_menu)

        # Set window icon - required for Wayland
        self.app.setDesktopFileName(f"{__id__}")

        # Components
        self.start_stop_button: QPushButton = self.window.startStopButton
        self.chentry_table: QTableWidget = self.window.chentryTable
        self.chord_table: QTableWidget = self.window.chordTable
        self.statusbar: QStatusBar = self.window.statusbar

        # Menu bar
        self.window.actionQuit.triggered.connect(self.app.quit)
        self.window.actionNexus_Dark.triggered.connect(lambda: self.set_style('Nexus_Dark'))
        self.window.actionQt_Default.triggered.connect(lambda: self.set_style('Fusion'))
        self.window.actionPlatform_Default.triggered.connect(lambda: self.set_style('Default'))
        self.window.actionBanlist.triggered.connect(self.show_banlist)
        self.window.actionExport.triggered.connect(self.export)

        # Signals
        self.start_stop_button.clicked.connect(self.start_stop)
        self.window.refreshButton.clicked.connect(self.refresh)

        # Set default number of entries
        self.window.entries_input.setValue(Defaults.DEFAULT_NUM_WORDS_GUI)

        # Columns of chentry table
        self.chentry_columns = [WordMetadataAttr.word, WordMetadataAttr.score, WordMetadataAttr.average_speed,
                                WordMetadataAttr.frequency, WordMetadataAttr.last_used]
        self.chentry_table.setColumnCount(len(self.chentry_columns))
        self.chentry_table.setHorizontalHeaderLabels(
            [self.tr("GUI", WordMetadataAttrLabel[col]) for col in self.chentry_columns])
        self.chentry_table.sortByColumn(1, Qt.SortOrder.DescendingOrder)

        # Chentry table right click menu
        self.chentry_context_menu = QMenu(self.chentry_table)
        self.chentry_table.contextMenuEvent = lambda event: self.chentry_context_menu.exec_(event.globalPos())

        # Ban word action
        banword_action = self.chentry_context_menu.addAction(
            self.translator.translate("GUI", "Ban and delete"))
        banword_action.triggered.connect(self.banword)

        # Chentry table keyboard shortcuts
        # TODO: These need to be reimplemented by subclassing QTableWidget and QLineInput
        # def chentry_event_handler(event):
        #     match event.key(), event.modifiers():
        #         case Qt.Key_Delete, None:  # Delete bans word
        #             self.banword()
        #         case Qt.Key_C, Qt.ControlModifier:  # Ctrl+C copies selected row(s)
        #             selected_rows = self.chentry_table.selectionModel().selectedRows()
        #             if len(selected_rows) == 0:
        #                 return
        #             data = '\n'.join('\t'.join([self.chentry_table.item(row.row(), col).text()
        #                                         for col, _ in enumerate(self.columns) for row in selected_rows]))
        #             QApplication.clipboard().setText(data)
        #         case Qt.Key_A, Qt.ControlModifier:  # Ctrl+A selects all rows
        #             self.chentry_table.selectAll()
        #         case Qt.Key_Escape, None:  # Escape clears selection
        #             self.chentry_table.clearSelection()
        #         case Qt.Key_F, Qt.ControlModifier:  # Ctrl+F focuses search input
        #             self.window.search_input.setFocus()
        #         case Qt.Key_R, Qt.ControlModifier:  # Ctrl+R refreshes
        #             self.refresh()
        #         case Qt.Key_Enter, Qt.ControlModifier:  # Ctrl+Enter starts/stops logging
        #             self.start_stop()
        # self.chentry_table.keyPressEvent = chentry_event_handler
        #
        # # Search input keyboard shortcuts
        # def search_input_event_handler(event):
        #     match event.key(), event.modifiers():
        #         case Qt.Key_Escape, None:  # Escape clears search
        #             self.window.search_input.clear()
        #         case Qt.Key_Enter, None:  # Enter refreshes
        #             self.refresh()
        # self.window.search_input.keyPressEvent = search_input_event_handler

        # Columns of chord table
        self.chord_columns = [ChordMetadataAttr.chord, ChordMetadataAttr.score, ChordMetadataAttr.frequency]
        self.chord_table.setColumnCount(len(self.chord_columns))
        self.chord_table.setHorizontalHeaderLabels(
            [self.tr("GUI", ChordMetadataAttrLabel[col]) for col in self.chord_columns])
        self.chord_table.sortByColumn(1, Qt.SortOrder.DescendingOrder)

        # Chord table right click menu
        self.chord_context_menu = QMenu(self.chord_table)
        self.chord_table.contextMenuEvent = lambda event: self.chord_context_menu.exec_(event.globalPos())

        # Ban chord action
        banchord_action = self.chord_context_menu.addAction(
            self.translator.translate("GUI", "Ban and delete"))
        banchord_action.triggered.connect(lambda: self.banword(is_chord=True))

        # Styles
        self.default_style: str = self.app.style().name()
        self.set_style('Nexus_Dark')

        self.freqlog: Freqlog | None = None  # for logging
        self.temp_freqlog: Freqlog = Freqlog(args.freqlog_db_path, loggable=False)  # for other operations
        self.logging_thread: Thread | None = None
        self.start_stop_button_started = False
        self.args = args

        # Auto-refresh - must go at the end
        self.window.entries_input.valueChanged.connect(self.refresh)
        self.window.search_input.textChanged.connect(self.refresh)

    def show_hide(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if not self.window.isVisible():
                self.window.show()
            else:
                self.window.hide()

    def set_style(self, style: Literal['Nexus_Dark', 'Fusion', 'Default']):
        self.app.setStyleSheet('')
        if style == 'Default':
            self.app.setStyle(self.default_style)
        else:
            self.app.setStyle('Fusion')
        if style == 'Nexus_Dark':
            self.app.setStyleSheet(Stylesheet.dark)
        self.window.update()

    def start_logging(self):
        if not self.freqlog:
            self.freqlog = Freqlog(self.args.freqlog_db_path, loggable=True)
        self.freqlog.start_logging()

    def stop_logging(self):
        self.freqlog.stop_logging()
        self.freqlog = None

    def start_stop(self):
        """Controller for start/stop logging button"""
        self.start_stop_button.setEnabled(False)
        self.start_stop_button.setStyleSheet("background-color: " + Colors.button_dark_yellow)
        if not self.start_stop_button_started:
            # Update button to starting
            self.start_stop_button.setText(self.tr("GUI", "Starting..."))
            self.window.repaint()

            # Start freqlogging
            self.logging_thread = Thread(target=self.start_logging)
            self.logging_thread.start()

            # Wait until logging starts
            # TODO: Replace this with something to prevent spam-clicking the button restarting logging
            while not (self.freqlog and self.freqlog.is_logging):
                pass

            # Update button to stop
            self.start_stop_button.setText(self.tr("GUI", "Stop logging"))
            self.start_stop_button.setStyleSheet("background-color: " + Colors.button_dark_red)
            self.statusbar.showMessage(self.tr("GUI", "Logging started"))
        else:  # start_stop_button started
            self.start_stop_button.setText(self.tr("GUI", "Stopping..."))
            self.window.repaint()

            # Stop freqlogging
            Thread(target=self.stop_logging).start()

            # Wait until logging stops
            self.logging_thread.join()  # TODO: try and not block the UI thread, however briefly

            # Update button to start
            self.start_stop_button.setText(self.tr("GUI", "Start logging"))
            self.start_stop_button.setStyleSheet("background-color: " + Colors.button_dark_green)
            self.statusbar.showMessage(self.tr("GUI", "Logging stopped"))
        self.start_stop_button.setEnabled(True)
        self.window.repaint()
        self.start_stop_button_started = not self.start_stop_button_started

    def refresh(self):
        """Controller for refresh button"""
        # Save and disable sorting
        self.chentry_table.setSortingEnabled(False)
        chentry_sort_by = self.chentry_table.horizontalHeader().sortIndicatorSection()
        chentry_sort_order = self.chentry_table.horizontalHeader().sortIndicatorOrder()
        chord_sort_by = self.chord_table.horizontalHeader().sortIndicatorSection()
        chord_sort_order = self.chord_table.horizontalHeader().sortIndicatorOrder()

        # Clear tables
        self.chentry_table.setRowCount(0)
        self.chord_table.setRowCount(0)

        # Add entries to the tables
        words = self.temp_freqlog.list_words(limit=self.window.entries_input.value(),
                                             sort_by=self.chentry_columns[chentry_sort_by],
                                             reverse=chentry_sort_order == Qt.SortOrder.DescendingOrder,
                                             case=CaseSensitivity.INSENSITIVE, search=self.window.search_input.text())
        chords = self.temp_freqlog.list_logged_chords(limit=self.window.entries_input.value(),
                                                      sort_by=self.chord_columns[chord_sort_by],
                                                      reverse=chord_sort_order == Qt.SortOrder.DescendingOrder,
                                                      search=self.window.search_input.text())

        def _insert_chentry_row(row: int, word: WordMetadata):
            """Insert a row into the chentry table"""
            self.chentry_table.insertRow(row)
            self.chentry_table.setItem(row, 0, QTableWidgetItem(word.word))
            item = QTableWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, word.score)
            self.chentry_table.setItem(row, 1, item)
            item = QTableWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, str(word.average_speed)[2:-3])
            self.chentry_table.setItem(row, 2, item)
            item = QTableWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, word.frequency)
            self.chentry_table.setItem(row, 3, item)
            item = QTableWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, word.last_used.isoformat(sep=" ", timespec="seconds"))
            self.chentry_table.setItem(row, 4, item)

        def _insert_chord_row(row: int, chord: ChordMetadata):
            """Insert a row into the chord table"""
            self.chord_table.insertRow(row)
            self.chord_table.setItem(row, 0, QTableWidgetItem(chord.chord))
            item = QTableWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, chord.score)
            self.chord_table.setItem(row, 1, item)
            item = QTableWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, chord.frequency)
            self.chord_table.setItem(row, 2, item)

        # Populate tables
        for i, w in enumerate(words):
            _insert_chentry_row(i, w)
        for i, c in enumerate(chords):
            _insert_chord_row(i, c)

        # Resize views
        self.chentry_table.setRowCount(len(words))
        self.chentry_table.resizeColumnsToContents()
        self.chord_table.setRowCount(len(chords))
        self.chord_table.resizeColumnsToContents()

        # Restore sorting
        self.chentry_table.setSortingEnabled(True)
        self.chentry_table.sortByColumn(chentry_sort_by, chentry_sort_order)
        self.chord_table.setSortingEnabled(True)
        self.chord_table.sortByColumn(chord_sort_by, chord_sort_order)

        # Update status
        num_words = self.temp_freqlog.num_words(CaseSensitivity.INSENSITIVE)
        num_chords = self.temp_freqlog.num_logged_chords()
        if self.temp_freqlog.num_chords is None:
            self.statusbar.showMessage(self.tr("GUI", "Loaded {}/{} freqlogged words, {}/{} logged chords "
                                                      "(no CharaChorder device with chords connected)").format(
                len(words), num_words, len(chords), num_chords))
        else:  # TODO: this is an inaccurate count of chords, because chords on device can be modified (i.e. + shift)
            self.statusbar.showMessage(self.tr("GUI", "Loaded {}/{} freqlogged words, {}/{} logged chords "
                                                      "(+ {} unused chords on device)").format(
                len(words), num_words, len(chords), num_chords, self.temp_freqlog.num_chords - num_chords))

    def show_banlist(self):
        """Controller for banlist button"""
        bl_dialog = BanlistDialog()

        def _refresh_banlist():
            """Refresh banlist table"""
            banlist_case, banlist_caseless = self.temp_freqlog.list_banned_words()
            bl_dialog.banlistTable.setRowCount(len(banlist_case) + len(banlist_caseless))
            for i, word in enumerate(banlist_case):
                bl_dialog.banlistTable.setItem(i, 0, QTableWidgetItem(word.word))
                bl_dialog.banlistTable.setItem(i, 1,
                                               QTableWidgetItem(
                                                   str(word.date_added.isoformat(sep=" ", timespec="seconds"))))
                bl_dialog.banlistTable.setItem(i, 2, QTableWidgetItem("Sensitive"))
            for i, word in enumerate(banlist_caseless):
                bl_dialog.banlistTable.setItem(i + len(banlist_case), 0, QTableWidgetItem(word.word))
                bl_dialog.banlistTable.setItem(i + len(banlist_case), 1,
                                               QTableWidgetItem(
                                                   str(word.date_added.isoformat(sep=" ", timespec="seconds"))))
                bl_dialog.banlistTable.setItem(i + len(banlist_case), 2, QTableWidgetItem("Insensitive"))
            bl_dialog.banlistTable.resizeColumnsToContents()

        _refresh_banlist()

        def _banword():
            """Controller for banword button"""
            bw_dialog = BanwordDialog()

            def _add_banword():
                """Controller for add button in banword dialog"""
                word = bw_dialog.wordInput.text()
                if bw_dialog.sensitive.isChecked():
                    res = self.temp_freqlog.ban_word(word, CaseSensitivity.SENSITIVE)
                elif bw_dialog.firstChar.isChecked():
                    res = self.temp_freqlog.ban_word(word, CaseSensitivity.FIRST_CHAR)
                else:
                    res = self.temp_freqlog.ban_word(word, CaseSensitivity.INSENSITIVE)
                self.statusbar.showMessage(self.tr("GUI", "Banned '{}'").format(word) if res else
                                           self.tr("GUI", "'{}' already banned").format(word))

            # Connect Ok button to add_banword
            bw_dialog.buttonBox.accepted.connect(_add_banword)
            bw_dialog.exec()
            _refresh_banlist()

        def _remove_banword():
            """Controller for remove button in banlist dialog"""
            # Get currently selected row(s)
            selected_rows = bl_dialog.banlistTable.selectionModel().selectedRows()
            if len(selected_rows) == 0:
                return

            # Get word(s) from selected row(s)
            selected_words = {}
            for row in selected_rows:
                selected_words[
                    bl_dialog.banlistTable.item(row.row(), 0).text()
                ] = (CaseSensitivity.SENSITIVE if bl_dialog.banlistTable.item(row.row(), 2).text() == "Sensitive"
                     else CaseSensitivity.INSENSITIVE)
            if len(selected_words) > 1:
                confirm_text = self.tr("GUI", "Unban {} words?".format(len(selected_words)))
            else:
                confirm_text = self.tr("GUI", "Unban '{}'?".format(list(selected_words.keys())[0]))

            def _confirm_unban():
                """Controller for OK button in confirm dialog"""
                res = self.temp_freqlog.unban_words(selected_words).count(True)
                if len(selected_words) == 1:
                    word = list(selected_words.keys())[0]
                    self.statusbar.showMessage(self.tr("GUI", "Unbanned '{}'").format(word) if res else
                                               self.tr("GUI", "'{}' not banned").format(word))
                elif res == 0:
                    self.statusbar.showMessage(self.tr("GUI", "None of the selected words were banned"))
                else:
                    self.statusbar.showMessage(
                        self.tr("GUI", "Unbanned {}/{} selected words").format(res, len(selected_words)))

            conf_dialog = ConfirmDialog(self.tr("GUI", "Confirm unban"), confirm_text.format(len(selected_words)))
            conf_dialog.buttonBox.accepted.connect(_confirm_unban)
            conf_dialog.exec()
            _refresh_banlist()

        bl_dialog.addButton.clicked.connect(_banword)
        bl_dialog.removeButton.clicked.connect(_remove_banword)
        bl_dialog.exec()

    def export(self):
        """Controller for export button"""
        # Words
        filename = QFileDialog.getSaveFileName(self.window, "Export words to CSV", "", "CSV (*.csv)")[0]
        if filename:
            if not filename.endswith(".csv"):
                filename += ".csv"
            num_exported = self.temp_freqlog.export_words_to_csv(filename)
            self.statusbar.showMessage(
                self.tr("GUI", "Exported {} entries to {}".format(num_exported, filename)))

        # Chords
        filename = QFileDialog.getSaveFileName(self.window, "Export chords to CSV", "", "CSV (*.csv)")[0]
        if filename:
            if not filename.endswith(".csv"):
                filename += ".csv"
            num_exported = self.temp_freqlog.export_chords_to_csv(filename)
            self.statusbar.showMessage(
                self.tr("GUI", "Exported {} entries to {}".format(num_exported, filename)))

    def banword(self, is_chord=False):
        """Controller for right click menu/delete key banword"""
        # Get word(s) from selected row(s)
        table = self.chord_table if is_chord else self.chentry_table
        selected_words = {table.item(row.row(), 0).text(): CaseSensitivity.INSENSITIVE for row in
                          table.selectionModel().selectedRows()}
        if len(selected_words) > 1:
            if is_chord:
                confirm_text = self.tr("GUI", "Ban and delete {} chords?".format(len(selected_words)))
            else:
                confirm_text = self.tr("GUI", "Ban and delete {} words?".format(len(selected_words)))
        else:
            confirm_text = self.tr("GUI", "Ban and delete '{}'?".format(list(selected_words.keys())[0]))

        def _confirm_ban():
            """Controller for OK button in confirm dialog"""
            res = self.temp_freqlog.ban_words(selected_words).count(True)
            self.refresh()
            if len(selected_words) == 1:
                word = list(selected_words.keys())[0]
                self.statusbar.showMessage(self.tr("GUI", "Banned '{}'").format(word) if res else
                                           self.tr("GUI", "'{}' already banned").format(word))
            elif res == 0:
                if is_chord:
                    self.statusbar.showMessage(self.tr("GUI", "All of the selected chords were already banned"))
                else:
                    self.statusbar.showMessage(self.tr("GUI", "All of the selected words were already banned"))
            else:
                if is_chord:
                    self.statusbar.showMessage(
                        self.tr("GUI", "Banned and deleted {}/{} selected chords").format(res, len(selected_words)))
                else:
                    self.statusbar.showMessage(
                        self.tr("GUI", "Banned and deleted {}/{} selected words").format(res, len(selected_words)))

        conf_dialog = ConfirmDialog(self.tr("GUI", "Confirm ban"), confirm_text.format(len(selected_words)))
        conf_dialog.buttonBox.accepted.connect(_confirm_ban)
        conf_dialog.exec()

    def exec(self):
        """Start the GUI"""
        self.window.show()
        self.refresh()
        self.app.exec()
