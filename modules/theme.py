"""
modules/theme.py

Dark blue + orange Qt stylesheet.
"""

DARK_BLUE_ORANGE_QSS = """
QMainWindow {
    background-color: #050B1A;
    color: #F5F5F5;
}

QTabWidget::pane {
    background: #050B1A;
    border: 1px solid #1F2A40;
}

QTabBar::tab {
    background: #0B1020;
    color: #F5F5F5;
    padding: 8px 14px;
    border: 1px solid #1F2A40;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #12264A;
    color: #FFA733;
    border-bottom-color: #12264A;
}

QGroupBox {
    color: #FFA733;
    border: 1px solid #1F2A40;
    border-radius: 5px;
    margin-top: 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}

QLabel {
    color: #F5F5F5;
}

QPushButton {
    background-color: #12264A;
    color: #F5F5F5;
    border: 1px solid #FFA733;
    border-radius: 5px;
    padding: 5px 10px;
}

QPushButton:hover {
    background-color: #183364;
}

QPushButton:pressed {
    background-color: #0D1A33;
}

QPushButton:disabled {
    background-color: #30394F;
    border-color: #555555;
    color: #888888;
}

QComboBox {
    background-color: #0B1020;
    color: #F5F5F5;
    border: 1px solid #1F2A40;
    border-radius: 4px;
    padding: 2px 6px;
}

QComboBox QAbstractItemView {
    background-color: #0B1020;
    color: #F5F5F5;
    selection-background-color: #12264A;
    selection-color: #FFA733;
}

QSpinBox {
    background-color: #0B1020;
    color: #F5F5F5;
    border: 1px solid #1F2A40;
    border-radius: 4px;
    padding: 2px 4px;
}

QTextEdit {
    background-color: #050B1A;
    color: #F5F5F5;
    border: 1px solid #1F2A40;
}

QStatusBar {
    background-color: #050B1A;
    color: #CCCCCC;
}

QStatusBar::item {
    border: none;
}
"""
