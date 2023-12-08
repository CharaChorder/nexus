class Colors:
    button_dark_red = '#550000'
    button_dark_yellow = '#777700'
    button_dark_green = '#005500'
    button_light_red = '#cf0000'
    button_light_yellow = '#ffcf00'
    button_light_green = '#00cf00'


class Stylesheet:
    # noinspection SpellCheckingInspection
    dark = '''
        * {
            background-color: #0b0b0b;
            color: #ffffff;
        }

        QPushButton {
            background: #111111;
            padding: 5px;
            padding-left: 15px;
            padding-right: 15px;
            border: 1px solid #222222;
        }
        QPushButton::hover {
            background: #222222;
        }

        QStatusBar {
            background-color: #222222;
        }

        QGroupBox {
            border: 1px solid #333333;
            border-radius: 5px;
            margin-top: 0.5em;
        }
        QGroupBox:title {
            color: #ffffff;
            left: 10px;
            subcontrol-origin: margin;
        }

        QTableWidget {
            background-color: #00000000;
        }

        QHeaderView::section {
            background-color: #111111;
            border: 0;
            border-left: 1px solid #333333;
            padding-left: 5px;
            padding-right: 5px;
        }
        QHeaderView::section::first { border-left: 0; }

        QScrollBar {
            border: 1px solid red;
        }
        QScrollBar:horizontal {
            border: 0px solid #999999;
            background: transparent;
            height: 10px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:horizontal {
            min-width: 0px;
            border: 0px solid red;
            border-radius: 4px;
            background-color: #333333;
        }
        QScrollBar::add-line:horizontal {
            width: 0px;
            subcontrol-position: bottom;
            subcontrol-origin: margin;
        }
        QScrollBar::sub-line:horizontal {
            width: 0 px;
            subcontrol-position: top;
            subcontrol-origin: margin;
        }

        QScrollBar:vertical {
            border: 0px solid #999999;
            background: transparent;
            width: 10px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:vertical {
            min-height: 0px;
            border: 0px solid red;
            border-radius: 4px;
            background-color: #333333;
        }
        QScrollBar::add-line:vertical {
            height: 0px;
            subcontrol-position: bottom;
            subcontrol-origin: margin;
        }
        QScrollBar::sub-line:vertical {
            height: 0 px;
            subcontrol-position: top;
            subcontrol-origin: margin;
        }

        QScrollBar::add-page, QScrollBar::sub-page {
            background: none;
        }

        QMenuBar::item {
            background: transparent;
        }
        QMenuBar::item:selected {
            background: #222222;
        }
        QMenu::item:selected {
            background: #222222;
        }
        '''
