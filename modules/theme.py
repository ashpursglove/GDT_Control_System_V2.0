


"""
modules/theme.py

Full dark-blue + vibrant-orange Qt stylesheet.
Ensures ALL widgets (including scroll areas, spin boxes, and group boxes)
inherit the dark theme consistently.
"""

VIBRANT_ORANGE = "#FF7A00"

DARK_BLUE_ORANGE_QSS = f"""
/* ------------------------
   GENERAL APPLICATION
-------------------------*/
QWidget {{
    background-color: #050B1A;
    color: #F5F5F5;
    font-size: 13px;
}}

QMainWindow {{
    background-color: #050B1A;
}}

QScrollArea {{
    background-color: #050B1A;
    border: none;
}}

QScrollArea QWidget {{
    background-color: #050B1A;
}}

QScrollBar:vertical {{
    background: #0B1020;
    width: 12px;
    margin: 0px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {VIBRANT_ORANGE};
    min-height: 20px;
    border-radius: 5px;
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    background: none;
    height: 0px;
}}

/* ------------------------
   GROUP BOXES
-------------------------*/
QGroupBox {{
    border: 1px solid #1F2A40;
    border-radius: 6px;
    margin-top: 10px;
    background-color: #0B1020;
    padding: 6px;
    color: {VIBRANT_ORANGE};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 2px 6px;
    color: {VIBRANT_ORANGE};
}}

/* ------------------------
   LABELS
-------------------------*/
QLabel {{
    color: #F5F5F5;
}}

/* ------------------------
   BUTTONS
-------------------------*/
QPushButton {{
    background-color: #12264A;
    color: #F5F5F5;
    border: 1px solid {VIBRANT_ORANGE};
    border-radius: 5px;
    padding: 6px 12px;
}}
QPushButton:hover {{
    background-color: #183364;
}}
QPushButton:pressed {{
    background-color: #0D1A33;
}}
QPushButton:disabled {{
    background-color: #30394F;
    border-color: #555;
    color: #888;
}}

/* ------------------------
   COMBO BOXES
-------------------------*/
QComboBox {{
    background-color: #0B1020;
    color: #F5F5F5;
    border: 1px solid #1F2A40;
    border-radius: 4px;
    padding: 4px;
}}
QComboBox QAbstractItemView {{
    background-color: #0B1020;
    selection-background-color: #12264A;
    selection-color: {VIBRANT_ORANGE};
}}





/* ------------------------
   SPIN BOXES (IMPROVED)
-------------------------*/
QSpinBox, QDoubleSpinBox {{
background-color: #0B1020;
color: #F5F5F5;
border: 1px solid #1F2A40;
border-radius: 4px;
padding: 2px 4px;
}}

/* Up/down buttons: lighter so the dark arrow is visible */
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background-color: #2A3F70;        /* brighter blue for contrast */
    border: 1px solid #FF7A00;        /* orange outline to match theme */
    width: 18px;
    padding: 0px;
}}

/* Keep the default arrow, but ensure it isn't hidden */
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    width: 10px;
    height: 10px;
    /* 'color' is ignored by Qt for these; contrast comes from the bg above */
}}

/* Hover states */
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: #3A538C;
    border: 1px solid #FF7A00;
}}

/* Pressed states */
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {{
    background-color: #1B2848;
}}














/* ------------------------
   TEXT EDIT / LOG VIEW
-------------------------*/
QTextEdit {{
    background-color: #050B1A;
    color: #F5F5F5;
    border: 1px solid #1F2A40;
}}

/* ------------------------
   TABS
-------------------------*/
QTabWidget::pane {{
    background: #050B1A;
    border: 1px solid #1F2A40;
}}

QTabBar::tab {{
    background: #0B1020;
    color: #F5F5F5;
    padding: 10px;
    border: 1px solid #1F2A40;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background: #12264A;
    color: {VIBRANT_ORANGE};
}}

QTabBar::tab:hover {{
    background: #183364;
    color: {VIBRANT_ORANGE};
}}

/* ------------------------
   STATUS BAR
-------------------------*/
QStatusBar {{
    background-color: #050B1A;
    color: #CCCCCC;
}}
QStatusBar::item {{
    border: none;
}}
"""
