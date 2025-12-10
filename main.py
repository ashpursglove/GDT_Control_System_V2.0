"""
main.py

Entry point for the GDT Reactor Monitoring and Control System.
"""

import sys
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QTimer, QRect
from PyQt5.QtGui import QFont, QPixmap, QPainter, QColor

from modules.gui import IndustrialHMIMonitor
from modules.utils import resource_path
from modules.theme import DARK_BLUE_ORANGE_QSS


class CustomSplashScreen(QWidget):
    """
    Simple custom splash screen with rounded corners and logo.
    """

    def __init__(
        self,
        width: int = 700,
        height: int = 425,
        corner_radius: int = 50,
        logo_path: str = "",
        text_message: str = "",
        copyright_message: str = "",
    ) -> None:
        super().__init__()
        self._corner_radius = corner_radius
        self._logo_path = logo_path
        self._text_message = text_message
        self._copyright_message = copyright_message

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(width, height)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()

        # Dark blue background
        color = QColor("#050B1A")
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, self._corner_radius, self._corner_radius)

        # Draw logo
        pixmap = QPixmap(self._logo_path).scaled(
            self.width() // 2,
            self.height() // 3,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        logo_x = (self.width() - pixmap.width()) // 2
        logo_y = self.height() // 4
        painter.drawPixmap(logo_x, logo_y, pixmap)

        # Draw main text
        font = QFont("Segoe UI", 20)
        painter.setFont(font)
        painter.setPen(Qt.white)
        painter.drawText(self.rect(), Qt.AlignBottom | Qt.AlignHCenter, self._text_message)

        # Draw copyright
        copyright_font = QFont("Segoe UI", 10)
        painter.setFont(copyright_font)
        bottom_margin = 10
        copyright_rect = QRect(
            0,
            self.height() - 40 + bottom_margin,
            self.width(),
            40,
        )
        painter.drawText(copyright_rect, Qt.AlignCenter, self._copyright_message)

        painter.end()


def main() -> None:
    app = QApplication(sys.argv)

    # Global font
    app_font = QFont("Segoe UI")
    app_font.setPointSize(10)
    app.setFont(app_font)

    # Dark blue + orange theme
    app.setStyleSheet(DARK_BLUE_ORANGE_QSS)

    # Splash setup
    logo_path = resource_path("assets/logo_full.png")
    text_message = "GDT Reactor Monitoring and Control System\n\n"
    copyright_message = "Code Copyright \u00A9 of Green Desert Tech\n"

    splash = CustomSplashScreen(
        width=700,
        height=425,
        corner_radius=50,
        logo_path=logo_path,
        text_message=text_message,
        copyright_message=copyright_message,
    )
    splash.show()

    # Create main window
    main_window = IndustrialHMIMonitor()

    splash_duration_ms = 3000

    QTimer.singleShot(splash_duration_ms, splash.close)
    QTimer.singleShot(splash_duration_ms, main_window.show)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
