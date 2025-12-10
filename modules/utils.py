"""
modules/utils.py

Utility helpers shared across the application.

Designed to work on both Windows and Linux (e.g. Raspberry Pi OS),
and also when bundled with PyInstaller.
"""

import os
import sys
from typing import Optional


def _project_root_from_this_file() -> str:
    """
    Resolve the project root directory given this file's location.

    Assumes the structure:
        project_root/
            main.py
            modules/
                utils.py
            assets/
                ...

    So from modules/utils.py we go one level up to project_root.
    """
    this_file = os.path.abspath(__file__)
    modules_dir = os.path.dirname(this_file)
    project_root = os.path.dirname(modules_dir)
    return project_root


def resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource (icon, image, etc.).

    Works in three scenarios:
        1. Running from source on Windows.
        2. Running from source on Linux/Raspberry Pi.
        3. Running from a PyInstaller bundle (sys._MEIPASS present).

    Parameters
    ----------
    relative_path : str
        Path relative to the project root, e.g. "assets/icon.ico".

    Returns
    -------
    str
        Absolute filesystem path to the requested resource.
    """
    base_path: Optional[str]

    # PyInstaller sets _MEIPASS to the temp bundle directory
    if hasattr(sys, "_MEIPASS"):
        base_path = getattr(sys, "_MEIPASS")
    else:
        # When running from source, use the project root
        base_path = _project_root_from_this_file()

    return os.path.join(base_path, relative_path)
