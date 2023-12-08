import argparse
import logging
import os
import signal
from threading import Thread
from pathlib import Path
from typing import Literal
import webbrowser

from cryptography import fernet as cryptography
from PySide6.QtCore import Qt, QTranslator, QLocale
from PySide6.QtWidgets import QApplication, QPushButton, QStatusBar, QTableWidget, QTableWidgetItem, QMainWindow, \
    QDialog, QFileDialog, QMenu, QSystemTrayIcon, QMessageBox, QInputDialog, QLineEdit
from PySide6.QtGui import QIcon, QAction

from nexus import __id__, __version__
from nexus.Freqlog import Freqlog
from nexus.ui.BanlistDialog import Ui_BanlistDialog
from nexus.ui.MainWindow import Ui_MainWindow
from nexus.style import Stylesheet, Colors

from nexus.Freqlog.Definitions import CaseSensitivity, WordMetadataAttr, WordMetadataAttrLabel, WordMetadata, \
    Defaults, ChordMetadataAttr, ChordMetadataAttrLabel, ChordMetadata
from nexus.Version import Version

if os.name == 'nt':  # Needed for taskbar icon on Windows
    import ctypes

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{__id__}.{__version__}")

StandardButton = QMessageBox.StandardButton


# TODO: see if we need to add a parent arg to any of these classes (for their super() calls)
class MainWindow(QMainWindow, Ui_MainWindow):
    """Set up the main window. Required because Qt is a PITA."""

    def __init__(self):
        super().__init__()
        self.setupUi(self)


class BanlistDialog(QDialog, Ui_BanlistDialog):
    """Set up the banlist dialog. Required because Qt is a PITA."""

    def __init__(self):
        super().__init__()
        self.setupUi(self)


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
        if self.translator.load(QLocale(), 'i18n', '_', os.path.join(script_parent_path, 'translations')):
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
        self.quit_tray_menu_action.triggered.connect(self.graceful_quit)
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
        self.window.actionQuit.triggered.connect(self.graceful_quit)
        self.window.actionNexus_Dark.triggered.connect(lambda: self.set_style('Nexus_Dark'))
        self.window.actionQt_Default.triggered.connect(lambda: self.set_style('Fusion'))
        self.window.actionPlatform_Default.triggered.connect(lambda: self.set_style('Default'))
        self.window.actionBanlist.triggered.connect(self.show_banlist)
        self.window.actionExport.triggered.connect(self.export)

        # Signals
        self.start_stop_button.clicked.connect(self.start_stop)
        self.window.refreshButton.clicked.connect(self.refresh)

        # Window close button
        self.window.closeEvent = lambda event: self.window.hide()  # FIXME: this is quitting instead of hiding

        # Set default number of entries
        self.window.chentry_entries_input.setValue(Defaults.DEFAULT_NUM_WORDS_GUI)
        self.window.chord_entries_input.setValue(Defaults.DEFAULT_NUM_WORDS_GUI)

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

        # Delete word action
        deleteword_action = self.chentry_context_menu.addAction(self.translator.translate("GUI", "Delete"))
        deleteword_action.triggered.connect(self.delete_entry)

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

        # Auto-refresh
        self.window.chord_entries_input.valueChanged.connect(self.refresh_chord_table)
        self.window.chentry_entries_input.valueChanged.connect(self.refresh_chentry_table)
        self.window.chord_search_input.textChanged.connect(self.refresh_chord_table)
        self.window.chentry_search_input.textChanged.connect(self.refresh_chentry_table)
        self.chord_table.horizontalHeader().sectionClicked.connect(self.refresh_chord_table)
        self.chentry_table.horizontalHeader().sectionClicked.connect(self.refresh_chentry_table)

        # Chord table right click menu
        self.chord_context_menu = QMenu(self.chord_table)
        self.chord_table.contextMenuEvent = lambda event: self.chord_context_menu.exec_(event.globalPos())

        # Ban chord action
        banchord_action = self.chord_context_menu.addAction(
            self.translator.translate("GUI", "Ban and delete"))
        banchord_action.triggered.connect(lambda: self.banword(is_chord=True))

        # Delete chord action
        deletechord_action = self.chord_context_menu.addAction(self.translator.translate("GUI", "Delete"))
        deletechord_action.triggered.connect(lambda: self.delete_entry(is_chord=True))

        # Styles
        self.default_style: str = self.app.style().name()
        self.set_style('Nexus_Dark')

        self.freqlog: Freqlog | None = None  # for logging
        self.temp_freqlog: Freqlog | None = None  # for other operations
        self.password = None
        self.logging_thread: Thread | None = None
        self.start_stop_button_started = False
        self.args = args

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
            try:
                self.freqlog = Freqlog(self.args.freqlog_db_path, lambda _: self.password, loggable=True)
            except Exception as e:
                QMessageBox.critical(self.window, self.tr("GUI", "Error"),
                                     self.tr("GUI", "Error opening database: {}").format(e))
                self.graceful_quit()
                raise
        self.freqlog.start_logging()

    def stop_logging(self):
        if self.freqlog:
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
            # FIXME: Replace this with something to prevent spam-clicking the button restarting logging
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

    def refresh_chentry_table(self, show_status: bool = True) -> list[WordMetadata]:
        """Refresh just the chentry table"""

        # Save and disable sorting
        self.chentry_table.setSortingEnabled(False)
        chentry_sort_by = self.chentry_table.horizontalHeader().sortIndicatorSection()
        chentry_sort_order = self.chentry_table.horizontalHeader().sortIndicatorOrder()

        # Clear table
        self.chentry_table.setRowCount(0)

        # Add entries to the table
        words = self.temp_freqlog.list_words(limit=self.window.chentry_entries_input.value(),
                                             sort_by=self.chentry_columns[chentry_sort_by],
                                             reverse=chentry_sort_order == Qt.SortOrder.DescendingOrder,
                                             case=CaseSensitivity.INSENSITIVE,
                                             search=self.window.chentry_search_input.text())

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

        # Populate table
        for i, w in enumerate(words):
            _insert_chentry_row(i, w)

        # Resize view
        self.chentry_table.setRowCount(len(words))
        self.chentry_table.resizeColumnsToContents()

        # Restore sorting
        self.chentry_table.setSortingEnabled(True)
        self.chentry_table.sortByColumn(chentry_sort_by, chentry_sort_order)

        if show_status:
            # Update status
            num_words = self.temp_freqlog.num_words(CaseSensitivity.INSENSITIVE)
            self.statusbar.showMessage(self.tr("GUI", "Loaded {}/{} freqlogged words").format(len(words), num_words))

        return words

    def refresh_chord_table(self, show_status: bool = True) -> list[ChordMetadata]:
        """Refresh just the chord table"""

        # Save and disable sorting
        self.chord_table.setSortingEnabled(False)
        chord_sort_by = self.chord_table.horizontalHeader().sortIndicatorSection()
        chord_sort_order = self.chord_table.horizontalHeader().sortIndicatorOrder()

        # Clear table
        self.chord_table.setRowCount(0)

        # Add entries to the table
        chords = self.temp_freqlog.list_logged_chords(limit=self.window.chord_entries_input.value(),
                                                      sort_by=self.chord_columns[chord_sort_by],
                                                      reverse=chord_sort_order == Qt.SortOrder.DescendingOrder,
                                                      search=self.window.chord_search_input.text())

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

        # Populate table
        for i, c in enumerate(chords):
            _insert_chord_row(i, c)

        # Resize view
        self.chord_table.setRowCount(len(chords))
        self.chord_table.resizeColumnsToContents()

        # Restore sorting
        self.chord_table.setSortingEnabled(True)
        self.chord_table.sortByColumn(chord_sort_by, chord_sort_order)

        if show_status:
            # Update status
            num_chords = self.temp_freqlog.num_logged_chords()
            if self.temp_freqlog.num_chords is None:
                self.statusbar.showMessage(self.tr("GUI", "Loaded {}/{} logged chords "
                                                          "(no CharaChorder device with chords connected)").format(
                    len(chords), num_chords))
            else:
                self.statusbar.showMessage(self.tr("GUI", "Loaded {}/{} logged chords "
                                                          "(+ {} unused chords on device)").format(
                    len(chords), num_chords, self.temp_freqlog.num_chords - num_chords))

        return chords

    def refresh(self):
        """Controller for refresh button - refresh both tables"""
        words = self.refresh_chentry_table(False)
        chords = self.refresh_chord_table(False)

        # Update status
        num_words = self.temp_freqlog.num_words(CaseSensitivity.INSENSITIVE)
        num_chords = self.temp_freqlog.num_logged_chords()
        if self.temp_freqlog.num_chords is None:
            self.statusbar.showMessage(self.tr("GUI", "Loaded {}/{} freqlogged words, {}/{} logged chords "
                                                      "(no CharaChorder device with chords connected)").format(
                len(words), num_words, len(chords), num_chords))
        else:  # FIXME: this is an inaccurate count of chords, because chords on device can be modified (i.e. + shift)
            self.statusbar.showMessage(self.tr("GUI", "Loaded {}/{} freqlogged words, {}/{} logged chords "
                                                      "(+ {} unused chords on device)").format(
                len(words), num_words, len(chords), num_chords, self.temp_freqlog.num_chords - num_chords))

    def show_banlist(self):
        """Controller for banlist button"""
        bl_dialog = BanlistDialog()

        def _refresh_banlist():
            """Refresh banlist table"""
            banlist = self.temp_freqlog.list_banned_words()
            bl_dialog.banlistTable.setRowCount(len(banlist))
            for i, word in enumerate(banlist):
                bl_dialog.banlistTable.setItem(i, 0, QTableWidgetItem(word.word))
                bl_dialog.banlistTable.setItem(i, 1, QTableWidgetItem(
                    str(word.date_added.isoformat(sep=" ", timespec="seconds"))))
            bl_dialog.banlistTable.resizeColumnsToContents()

        _refresh_banlist()

        def _banword():
            """Controller for banword button"""
            word, ok = QInputDialog.getText(self.window, self.tr("GUI", "Ban word"), self.tr("GUI", "Word to ban:"))
            if ok and word:
                # Truncate word for display if too long
                display_word = word if len(word) <= 20 else word[:17] + "…" + word[-3:]

                # Ban word
                res = self.temp_freqlog.ban_word(word)
                self.statusbar.showMessage(self.tr("GUI", "Banned '{}'").format(display_word) if res else
                                           self.tr("GUI", "'{}' already banned").format(display_word))
                _refresh_banlist()

        def _remove_banword():
            """Controller for remove button in banlist dialog"""
            # Get currently selected row(s)
            selected_rows = bl_dialog.banlistTable.selectionModel().selectedRows()
            if len(selected_rows) == 0:
                return

            # Get word(s) from selected row(s)
            selected_words = [bl_dialog.banlistTable.item(row.row(), 0).text() for row in selected_rows]
            display_word = None
            if len(selected_words) == 1:
                display_word = selected_words[0]

                # Truncate word for display if too long
                display_word = display_word if len(display_word) <= 20 else display_word[:17] + "…" + display_word[-3:]
                confirm_text = self.tr("GUI", "Unban '{}'?".format(display_word))
            else:
                confirm_text = self.tr("GUI", "Unban {} words?".format(len(selected_words)))

            if QMessageBox.question(self.window, self.tr("GUI", "Confirm unban"),
                                    confirm_text.format(len(selected_words)), StandardButton.Yes | StandardButton.No,
                                    defaultButton=StandardButton.No) == StandardButton.Yes:
                res = self.temp_freqlog.unban_words(selected_words).count(True)
                if len(selected_words) == 1:
                    self.statusbar.showMessage(self.tr("GUI", "Unbanned '{}'").format(display_word) if res else
                                               self.tr("GUI", "'{}' not banned").format(display_word))
                elif res == 0:
                    self.statusbar.showMessage(self.tr("GUI", "None of the selected words were banned"))
                else:
                    self.statusbar.showMessage(
                        self.tr("GUI", "Unbanned {}/{} selected words").format(res, len(selected_words)))
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
        selected_words = [table.item(row.row(), 0).text() for row in table.selectionModel().selectedRows()]
        display_word = None
        if len(selected_words) == 1:
            # Truncate word for display if too long
            word = selected_words[0]
            display_word = word if len(word) <= 20 else word[:17] + "…" + word[-3:]
            confirm_text = self.tr("GUI", "Ban and delete '{}'?".format(display_word))
        else:
            if is_chord:
                confirm_text = self.tr("GUI", "Ban and delete {} chords?".format(len(selected_words)))
            else:
                confirm_text = self.tr("GUI", "Ban and delete {} words?".format(len(selected_words)))

        if QMessageBox.question(self.window, self.tr("GUI", "Confirm ban"),
                                confirm_text.format(len(selected_words)), StandardButton.Yes | StandardButton.No,
                                defaultButton=StandardButton.No) == StandardButton.Yes:
            res = self.temp_freqlog.ban_words(selected_words).count(True)
            self.refresh()
            if len(selected_words) == 1:
                self.statusbar.showMessage(self.tr("GUI", "Banned '{}'").format(display_word) if res else
                                           self.tr("GUI", "'{}' already banned").format(display_word))
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

    def delete_entry(self, is_chord=False):
        """Controller for right click menu/delete key delete entry"""
        # Get word(s) from selected row(s)
        table = self.chord_table if is_chord else self.chentry_table
        selected_words = ([table.item(row.row(), 0).text() for row in table.selectionModel().selectedRows()]
                          if is_chord else {table.item(row.row(), 0).text(): CaseSensitivity.INSENSITIVE for row in
                                            table.selectionModel().selectedRows()})
        display_word = None
        if len(selected_words) == 1:
            # Truncate word for display if too long
            word = list(selected_words.keys())[0]
            display_word = word if len(word) <= 20 else word[:17] + "…" + word[-3:]
            confirm_text = self.tr("GUI", "Delete '{}'?".format(display_word))
        else:
            if is_chord:
                confirm_text = self.tr("GUI", "Delete {} chords?".format(len(selected_words)))
            else:
                confirm_text = self.tr("GUI", "Delete {} words?".format(len(selected_words)))

        if QMessageBox.question(self.window, self.tr("GUI", "Confirm delete"),
                                confirm_text.format(len(selected_words)), StandardButton.Yes | StandardButton.No,
                                defaultButton=StandardButton.No) == StandardButton.Yes:
            if is_chord:
                res = self.temp_freqlog.delete_logged_chords(selected_words).count(True)
            else:
                res = self.temp_freqlog.delete_words(selected_words).count(True)
            self.refresh()
            if len(selected_words) == 1:
                self.statusbar.showMessage(self.tr("GUI", "Deleted '{}'").format(display_word) if res else
                                           self.tr("GUI", "'{}' not found").format(display_word))
            elif res == 0:
                if is_chord:
                    self.statusbar.showMessage(self.tr("GUI", "None of the selected chords were found"))
                else:
                    self.statusbar.showMessage(self.tr("GUI", "None of the selected words were found"))
            else:
                if is_chord:
                    self.statusbar.showMessage(
                        self.tr("GUI", "Deleted {}/{} selected chords").format(res, len(selected_words)))
                else:
                    self.statusbar.showMessage(
                        self.tr("GUI", "Deleted {}/{} selected words").format(res, len(selected_words)))

    def prompt_for_upgrade(self, db_version: Version) -> None:
        """Prompt user to upgrade"""
        if QMessageBox.question(
                self.window, self.tr("GUI", "Database Upgrade"),
                self.tr("GUI", "You are running version {} of nexus, but your database is on version {}.\n"
                               "Backup your database before pressing 'Yes' to upgrade your database, or press 'No' "
                               "to exit without upgrading.").format(__version__, db_version),
                StandardButton.Yes | StandardButton.No, defaultButton=StandardButton.No) == StandardButton.No:
            raise PermissionError("Database upgrade cancelled")

    def prompt_for_password(self, new: bool = False) -> str:
        """
        Prompt for password
        :param new: Whether to ask for a new password
        """
        while True:
            try:
                password, ok = QInputDialog.getText(
                    self.window, self.tr("GUI", "Banlist Password"),
                    self.tr("GUI", "Choose a new password to encrypt your banlist with:") if new else
                    self.tr("GUI", "Enter your banlist password:"), QLineEdit.EchoMode.Password)
                if not ok:
                    raise InterruptedError("Password prompt cancelled")
                if new:
                    if len(password) < 8:
                        if (QMessageBox.warning(self.window, self.tr("GUI", "Password too short"),
                                                self.tr("GUI", "Password should be at least 8 characters long.\n"
                                                               "Continue without securely encrypting your banlist?"),
                                                StandardButton.Yes | StandardButton.No, defaultButton=StandardButton.No)
                                == StandardButton.No):
                            raise InterruptedError("Password prompt cancelled")
                    confirm_password, ok = QInputDialog.getText(self.window, self.tr("GUI", "Banlist Password"),
                                                                self.tr("GUI", "Confirm your banlist password:"),
                                                                QLineEdit.EchoMode.Password)
                    if not ok:
                        raise InterruptedError("Password prompt cancelled")
                    if password != confirm_password:
                        raise ValueError("Passwords do not match")
                self.password = password
                return password
            except ValueError as e:
                QMessageBox.critical(self.window, self.tr("GUI", "Error"), str(e))
                logging.error(e)
                continue
            except InterruptedError:
                raise

    def graceful_quit(self):
        """Quit gracefully"""
        if self.freqlog:
            self.freqlog.stop_logging()
        self.freqlog = None
        self.app.quit()

    def exec(self):
        """Start the GUI"""
        # Handle SIGINT
        signal.signal(signal.SIGINT, self.graceful_quit)

        # Start GUI
        self.window.show()

        # Check for updates
        outdated, latest_version = Version.fetch_latest_nexus_version()
        if outdated is True:
            # TODO: Update automatically if the current version is outdated
            if latest_version is None:
                QMessageBox.warning(
                    self.window, self.tr("GUI", "Update check failed"),
                    self.tr("GUI",
                            "Update check failed, there may be a new version of Nexus available. The latest version "
                            "can be found at https://github.com/CharaChorder/nexus/releases/latest"))
            else:
                if QMessageBox.information(
                        self.window, self.tr("GUI", "Update available"),
                        self.tr("GUI", "Version {} of Nexus is available!\n(You are running v{})").format(
                            latest_version, __version__),
                        buttons=StandardButton.Ok | StandardButton.Open) == StandardButton.Open:
                    webbrowser.open("https://github.com/CharaChorder/nexus/releases/latest")
                    return  # Don't start Nexus if the user opens the release page

        # Initialize backend
        while True:
            try:
                self.temp_freqlog = Freqlog(self.args.freqlog_db_path, self.prompt_for_password, loggable=False,
                                            upgrade_callback=self.prompt_for_upgrade)  # for other operations
                break
            except cryptography.InvalidToken:
                QMessageBox.critical(self.window, self.tr("GUI", "Error"),
                                     self.tr("GUI", "Incorrect password"))
                logging.error("Incorrect password")
            except Exception as e:
                QMessageBox.critical(self.window, self.tr("GUI", "Error"),
                                     self.tr("GUI", "Error opening database: {}").format(e))
                raise

        # Refresh and enter event loop
        self.refresh()
        self.app.exec()
