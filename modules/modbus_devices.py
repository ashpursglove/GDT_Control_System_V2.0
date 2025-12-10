"""
modules/modbus_devices.py

Modbus device wrappers:

- CwtBlPhSensor: pH + temperature transmitter (slave: configurable).
- As7341Controller: AS7341 spectral + LED/relay (slave: configurable).
"""

from __future__ import annotations

from typing import Tuple, List

import minimalmodbus
import serial


class CwtBlPhSensor:
    """
    High-level driver for a single CWT-BL pH/temperature transmitter on RS485.
    """

    REG_TEMPERATURE = 0  # Holding register 40001
    REG_PH = 1           # Holding register 40002

    def __init__(
        self,
        port: str,
        slave_address: int = 1,
        baudrate: int = 9600,
        timeout: float = 0.5,
        debug: bool = False,
    ) -> None:
        instrument = minimalmodbus.Instrument(port, slave_address)  # type: ignore[arg-type]
        instrument.mode = minimalmodbus.MODE_RTU
        instrument.clear_buffers_before_each_transaction = True

        instrument.serial.baudrate = baudrate
        instrument.serial.bytesize = 8
        instrument.serial.parity = serial.PARITY_NONE
        instrument.serial.stopbits = 1
        instrument.serial.timeout = timeout

        instrument.debug = debug
        self._instrument = instrument

    def _read_register_scaled(
        self,
        register_address: int,
        decimals: int,
        signed: bool = False,
        function_code: int = 3,
    ) -> float:
        return self._instrument.read_register(
            registeraddress=register_address,
            number_of_decimals=decimals,
            functioncode=function_code,
            signed=signed,
        )

    def read_temperature_c(self) -> float:
        return self._read_register_scaled(
            register_address=self.REG_TEMPERATURE,
            decimals=1,
            signed=True,
        )

    def read_ph(self) -> float:
        return self._read_register_scaled(
            register_address=self.REG_PH,
            decimals=1,
            signed=False,
        )

    def read_all(self) -> Tuple[float, float]:
        temp = self.read_temperature_c()
        ph = self.read_ph()
        return temp, ph


class As7341Controller:
    """
    Controller for the AS7341-based board with LED/relay + spectral channels.

    Holding registers (0-based):
        0: REG_LED_CONTROL     (0 = OFF, !=0 = ON)
        1: REG_RELAY_CONTROL   (0 = OFF, !=0 = ON)
        2-9: REG_AS7341_F1..F8  spectral channels
        10: REG_AS7341_CLEAR
        11: REG_AS7341_NIR
        12: REG_AS7341_STATUS_WORD
    """

    REG_LED_CONTROL = 0
    REG_RELAY_CONTROL = 1
    REG_FIRST_SPECTRAL = 2
    NUM_SPECTRAL_REGS = 10  # F1..F8, CLEAR, NIR
    REG_STATUS_WORD = 12

    def __init__(
        self,
        port: str,
        slave_address: int = 50,
        baudrate: int = 9600,
        timeout: float = 0.5,
        debug: bool = False,
    ) -> None:
        instrument = minimalmodbus.Instrument(port, slave_address)  # type: ignore[arg-type]
        instrument.mode = minimalmodbus.MODE_RTU
        instrument.clear_buffers_before_each_transaction = True

        instrument.serial.baudrate = baudrate
        instrument.serial.bytesize = 8
        instrument.serial.parity = serial.PARITY_NONE
        instrument.serial.stopbits = 1
        instrument.serial.timeout = timeout

        instrument.debug = debug
        self._instrument = instrument

    def write_led(self, value: int) -> None:
        """
        Set LED state: 0 = off, 1 = on (any non-zero treated as on).
        """
        self._instrument.write_register(
            registeraddress=self.REG_LED_CONTROL,
            value=1 if value != 0 else 0,
            number_of_decimals=0,
            functioncode=6,
            signed=False,
        )

    def write_relay(self, value: int) -> None:
        """
        Set relay state: 0 = off, 1 = on.
        """
        self._instrument.write_register(
            registeraddress=self.REG_RELAY_CONTROL,
            value=1 if value != 0 else 0,
            number_of_decimals=0,
            functioncode=6,
            signed=False,
        )




    def read_spectral(self) -> Tuple[List[int], int]:
        """
        Read spectral channels and the status word.

        The hardware exposes:
            [F1, F2, F3, F4, F5, F6, F7, F8, CLEAR, NIR]

        For the GUI we *ignore* CLEAR, so we return:
            [F1, F2, F3, F4, F5, F6, F7, F8, NIR]

        Returns
        -------
        (values, status_word)
            values: list of 9 ints [F1..F8, NIR]
            status_word: 0 = OK, nonzero indicates errors.
        """
        raw_values = self._instrument.read_registers(
            registeraddress=self.REG_FIRST_SPECTRAL,
            number_of_registers=self.NUM_SPECTRAL_REGS,
            functioncode=3,
        )
        # raw_values: [F1, F2, F3, F4, F5, F6, F7, F8, CLEAR, NIR]
        if len(raw_values) >= 10:
            # Drop CLEAR (index 8), keep everything else
            values = raw_values[:8] + raw_values[9:]
        else:
            # Fallback: just return what we got; GUI will clamp to its channel count
            values = raw_values

        status_word = self._instrument.read_register(
            registeraddress=self.REG_STATUS_WORD,
            number_of_decimals=0,
            functioncode=3,
            signed=False,
        )
        return values, status_word

    # def read_spectral(self) -> Tuple[List[int], int]:
    #     """
    #     Read all spectral channels and the status word.

    #     Returns
    #     -------
    #     (values, status_word)
    #         values: list of 10 ints [F1..F8, CLEAR, NIR]
    #         status_word: 0 = OK, nonzero indicates errors.
    #     """
    #     values = self._instrument.read_registers(
    #         registeraddress=self.REG_FIRST_SPECTRAL,
    #         number_of_registers=self.NUM_SPECTRAL_REGS,
    #         functioncode=3,
    #     )
    #     status_word = self._instrument.read_register(
    #         registeraddress=self.REG_STATUS_WORD,
    #         number_of_decimals=0,
    #         functioncode=3,
    #         signed=False,
    #     )
    #     return values, status_word
