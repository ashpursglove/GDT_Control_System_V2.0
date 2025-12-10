"""
modules/backend.py

Modbus backend with a QThread-based poller that scales to multiple reactors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

import datetime
import threading
from PyQt5.QtCore import QThread, pyqtSignal

from modules.modbus_devices import CwtBlPhSensor, As7341Controller


@dataclass
class ReactorConfig:
    """
    Configuration for a single reactor on the RS485 bus.
    """
    name: str
    ph_slave_id: int
    spectral_slave_id: int


class ModbusPoller(QThread):
    """
    QThread that polls Modbus devices for one reactor.

    Emits:
        reading_ready(dict)  - full data snapshot for this reactor.
        error(str)           - error messages suitable for status bar.
    """

    reading_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(
        self,
        port: str,
        reactor_config: ReactorConfig,
        poll_interval_ms: int = 1000,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._port = port
        self._config = reactor_config
        self._poll_interval_ms = max(100, poll_interval_ms)
        self._running = False

        self._lock = threading.Lock()
        self._target_led = 0
        self._target_relay = 0

    def set_poll_interval_ms(self, interval_ms: int) -> None:
        """
        Update the poll interval while running.
        """
        with self._lock:
            self._poll_interval_ms = max(100, interval_ms)

    def set_led_target(self, on: bool) -> None:
        """
        Request a new LED state to be written on the next loop.
        """
        with self._lock:
            self._target_led = 1 if on else 0

    def set_relay_target(self, on: bool) -> None:
        """
        Request a new relay state to be written on the next loop.
        """
        with self._lock:
            self._target_relay = 1 if on else 0

    def stop(self) -> None:
        """
        Stop the poll loop.
        """
        self._running = False

    def run(self) -> None:
        try:
            ph_sensor = CwtBlPhSensor(
                port=self._port,
                slave_address=self._config.ph_slave_id,
            )
            spectral = As7341Controller(
                port=self._port,
                slave_address=self._config.spectral_slave_id,
            )
        except Exception as exc:
            self.error.emit(f"Failed to open Modbus devices: {exc}")
            return

        self._running = True

        current_led = None  # type: ignore
        current_relay = None  # type: ignore

        while self._running:
            try:
                with self._lock:
                    led_target = self._target_led
                    relay_target = self._target_relay
                    interval_ms = self._poll_interval_ms

                # Apply pending control changes
                if current_led is None or led_target != current_led:
                    spectral.write_led(led_target)
                    current_led = led_target

                if current_relay is None or relay_target != current_relay:
                    spectral.write_relay(relay_target)
                    current_relay = relay_target

                # Read sensor values
                temp_c, ph = ph_sensor.read_all()
                light_values, status_word = spectral.read_spectral()

                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                data: Dict[str, Any] = {
                    "reactor": self._config.name,
                    "timestamp": timestamp,
                    "temperature": temp_c,
                    "pH": {"value": ph},
                    "light": light_values,
                    "relay": current_relay,
                    "led": current_led,
                    "status": status_word,
                }

                self.reading_ready.emit(data)

                if status_word != 0:
                    self.error.emit(f"AS7341 status word: {status_word}")
            except Exception as exc:
                self.error.emit(f"Modbus poll error: {exc}")

            self.msleep(interval_ms)
