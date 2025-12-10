

from dataclasses import dataclass
from typing import Dict, Any, Callable, Tuple

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

    Behaviour:
    ----------
    - Runs in its own thread (GUI stays responsive).
    - Each cycle:
        * Applies any pending LED/relay target changes.
        * Reads pH/temperature from the pH transmitter.
        * Reads spectral data + status word from the AS7341 board.
        * Emits one 'reading_ready' dict if both reads succeed.

    - If a Modbus call fails:
        * It is retried up to `max_retries` times for that cycle.
        * If still failing after retries:
            - An 'error' signal is emitted.
            - No reading is emitted for that cycle.
            - The loop continues; next cycle tries again.

    Signals:
    --------
    reading_ready(dict)  - full data snapshot for this reactor.
    error(str)           - error messages suitable for status bar/log.
    """

    reading_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(
        self,
        port: str,
        reactor_config: ReactorConfig,
        poll_interval_ms: int = 1000,
        max_retries: int = 3,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._port = port
        self._config = reactor_config
        self._poll_interval_ms = max(100, poll_interval_ms)
        self._max_retries = max(1, max_retries)
        self._running = False

        # Targets for LED/relay written by GUI thread
        self._lock = threading.Lock()
        self._target_led = 0
        self._target_relay = 0

    # ------------------------------------------------------------------
    # Public control API (called from GUI thread)
    # ------------------------------------------------------------------
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
        Stop the poll loop. The thread will exit after the current cycle.
        """
        self._running = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _with_retries(self, label: str, func: Callable[[], Any]) -> Any:
        """
        Execute `func` with simple retry-on-exception logic.

        Parameters
        ----------
        label : str
            Human-readable label for error messages (e.g. "read spectral").
        func : callable
            Function with no arguments to call.

        Returns
        -------
        Any
            Whatever `func()` returns on success.

        Raises
        ------
        Exception
            The last exception if all retries fail.
        """
        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                return func()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                self.error.emit(
                    f"{label} failed (attempt {attempt}/{self._max_retries}): {exc}"
                )
        # If we get here, all retries failed
        raise last_exc if last_exc is not None else RuntimeError(
            f"{label} failed after {self._max_retries} attempts"
        )

    # ------------------------------------------------------------------
    # Thread entry point
    # ------------------------------------------------------------------
    def run(self) -> None:
        """
        Main poll loop.

        - Creates the Modbus instruments.
        - Loops until `stop()` is called.
        """
        try:
            ph_sensor = CwtBlPhSensor(
                port=self._port,
                slave_address=self._config.ph_slave_id,
            )
            spectral = As7341Controller(
                port=self._port,
                slave_address=self._config.spectral_slave_id,
            )
        except Exception as exc:  # noqa: BLE001
            self.error.emit(f"Failed to open Modbus devices on {self._port}: {exc}")
            return

        self._running = True

        current_led: int | None = None
        current_relay: int | None = None

        while self._running:
            # Snapshot config/targets under lock
            with self._lock:
                led_target = self._target_led
                relay_target = self._target_relay
                interval_ms = self._poll_interval_ms

            try:
                # ------------------------------------------------------
                # Apply pending LED/relay changes with retries
                # ------------------------------------------------------
                if current_led is None or led_target != current_led:
                    self._with_retries(
                        "write LED",
                        lambda: spectral.write_led(led_target),
                    )
                    current_led = led_target

                if current_relay is None or relay_target != current_relay:
                    self._with_retries(
                        "write relay",
                        lambda: spectral.write_relay(relay_target),
                    )
                    current_relay = relay_target

                # ------------------------------------------------------
                # Read sensors with retries
                # ------------------------------------------------------
                def _read_ph_all() -> Tuple[float, float]:
                    return ph_sensor.read_all()

                def _read_spectral() -> Tuple[list[int], int]:
                    return spectral.read_spectral()

                temp_c, ph = self._with_retries("read pH/temperature", _read_ph_all)
                light_values, status_word = self._with_retries(
                    "read spectral", _read_spectral
                )

                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                data: Dict[str, Any] = {
                    "reactor": self._config.name,
                    "timestamp": timestamp,
                    "temperature": temp_c,
                    "pH": {"value": ph},
                    "light": light_values,   # list of 9 ints (F1..F8, NIR; CLEAR removed)
                    "relay": current_relay,
                    "led": current_led,
                    "status": status_word,
                }

                self.reading_ready.emit(data)

                if status_word != 0:
                    self.error.emit(f"AS7341 status word: {status_word}")

            except Exception as exc:  # noqa: BLE001
                # Any failure after retries is reported; we skip emitting a reading
                self.error.emit(f"Modbus poll cycle failed: {exc}")

            # Wait until next cycle
            self.msleep(interval_ms)
