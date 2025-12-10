"""
modules/gui.py

PyQt5 GUI for the GDT Reactor Monitoring and Control System.

- IndustrialHMIMonitor(QMainWindow) is the main window.
- Uses ModbusPoller (QThread) for scalable backend polling.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional

import datetime
import json
import csv

import numpy as np
import serial.tools.list_ports
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QGridLayout,
    QGroupBox,
    QTabWidget,
    QTextEdit,
    QFileDialog,
    QSpinBox,
)
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtCore import Qt

from pyqtgraph import PlotWidget, mkPen, BarGraphItem

from modules.backend import ModbusPoller, ReactorConfig
from modules.utils import resource_path


# Harvesting-rate calibration
HARVEST_NONE_VALUE = 1295   # when green sensor reads this -> 0 kg/h
HARVEST_FULL_VALUE = 20     # when green sensor reads this or less -> full harvest
HARVEST_MAX_KG_PER_HOUR = 3.0
GREEN_CHANNEL_INDEX = 4     # zero-based index into "light" list for green


class IndustrialHMIMonitor(QMainWindow):
    """
    Main window for a single-reactor monitoring and control GUI.
    """

    def __init__(self) -> None:
        super().__init__()

        self.graphs: Dict[str, Any] = {}
        self.plots: Dict[str, PlotWidget] = {}
        self.spectral_curves: List[Any] = []
        self.spectral_bar_values: List[float] = []

        self.time_index: int = 0
        self.logged_data: List[Dict[str, Any]] = []

        self.poller: Optional[ModbusPoller] = None
        self.relay_state: bool = False
        self.led_state: bool = False

        self._init_ui()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        self.setWindowTitle("GDT Reactor Monitoring and Control System")
        self.setGeometry(100, 100, 1400, 850)

        icon_path = resource_path("assets/icon.ico")
        self.setWindowIcon(QIcon(icon_path))

        self.tabs = QTabWidget()

        # Dashboard tab
        self.dashboard_tab = QWidget()
        dashboard_layout = QVBoxLayout()
        self.top_bar = self._create_top_bar()
        self.dashboard = self._create_dashboard()
        dashboard_layout.addLayout(self.top_bar)
        dashboard_layout.addWidget(self.dashboard)
        self.dashboard_tab.setLayout(dashboard_layout)

        # Serial data / log tab
        self.serial_data_tab = QWidget()
        serial_data_layout = QVBoxLayout()
        self.serial_data_view = QLabel("Incoming Data Snapshot:")
        self.serial_data_area = QTextEdit()
        self.serial_data_area.setReadOnly(True)
        serial_data_layout.addWidget(self.serial_data_view)
        serial_data_layout.addWidget(self.serial_data_area)
        self.serial_data_tab.setLayout(serial_data_layout)

        self.tabs.addTab(self.dashboard_tab, "Live Data")
        self.tabs.addTab(self.serial_data_tab, "Sensor Data Log")

        central_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Status bar
        self.statusBar().showMessage("Ready")

    def _create_top_bar(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        # COM port selection
        self.com_label = QLabel("Port:")
        self.com_dropdown = QComboBox()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._refresh_com_ports)
        self._refresh_com_ports()

        # Poll interval selection
        self.poll_label = QLabel("Poll interval:")
        self.poll_combo = QComboBox()
        self.poll_combo.addItem("0.5 s", 500)
        self.poll_combo.addItem("1.0 s", 1000)
        self.poll_combo.addItem("2.0 s", 2000)
        self.poll_combo.addItem("5.0 s", 5000)
        self.poll_combo.setCurrentIndex(1)

        # Slave IDs
        self.ph_id_label = QLabel("pH/Temp ID:")
        self.ph_id_spin = QSpinBox()
        self.ph_id_spin.setRange(1, 247)
        self.ph_id_spin.setValue(22)

        self.spectral_id_label = QLabel("Spectral ID:")
        self.spectral_id_spin = QSpinBox()
        self.spectral_id_spin.setRange(1, 247)
        self.spectral_id_spin.setValue(50)

        # Start / Stop
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_monitoring)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_monitoring)

        # Relay control
        self.relay_button = QPushButton("Circ Pump: OFF")
        self.relay_button.setCheckable(True)
        self.relay_button.clicked.connect(self.toggle_relay)

        # LED control
        self.led_button = QPushButton("Light Source: OFF")
        self.led_button.setCheckable(True)
        self.led_button.clicked.connect(self.toggle_led)

        # Export
        self.export_button = QPushButton("Export to CSV")
        self.export_button.clicked.connect(self.export_to_csv)

        layout.addWidget(self.com_label)
        layout.addWidget(self.com_dropdown)
        layout.addWidget(self.refresh_button)
        layout.addSpacing(15)

        layout.addWidget(self.poll_label)
        layout.addWidget(self.poll_combo)
        layout.addSpacing(15)

        layout.addWidget(self.ph_id_label)
        layout.addWidget(self.ph_id_spin)
        layout.addWidget(self.spectral_id_label)
        layout.addWidget(self.spectral_id_spin)
        layout.addSpacing(15)

        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.relay_button)
        layout.addWidget(self.led_button)
        layout.addWidget(self.export_button)

        layout.addStretch(1)
        return layout

    def _refresh_com_ports(self) -> None:
        """
        Populate or refresh the list of available serial ports.
        """
        current = self.com_dropdown.currentText()
        self.com_dropdown.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.com_dropdown.addItem(p.device)

        # Try to keep the previous selection if still available
        index = self.com_dropdown.findText(current)
        if index >= 0:
            self.com_dropdown.setCurrentIndex(index)

    def _create_dashboard(self) -> QGroupBox:
        dashboard = QGroupBox("Sensor Dashboard")
        layout = QGridLayout()
        self.spectral_curves = []

        def add_graph(title: str, y_label: str, pen_color: str, position: tuple) -> None:
            pw = PlotWidget(title=title)
            pw.setLabel("left", y_label)
            curve = pw.plot(pen=pen_color)
            self.graphs[title] = curve
            self.plots[title] = pw
            layout.addWidget(pw, *position)

        # Main time-series graphs
        add_graph("Temperature (°C)", "Temperature (°C)", "g", (0, 0))
        add_graph("pH Value", "pH", "b", (0, 1))
        add_graph("Harvesting Rate (kg/h)", "kg/h", "y", (0, 2))

        # Spectral colours and labels
        self.spectral_colors = [
            (148, 0, 211),   # F1
            (75, 0, 130),    # F2
            (0, 0, 255),     # F3
            (0, 255, 255),   # F4
            (0, 255, 0),     # F5 (Green)
            (173, 255, 47),  # F6
            (255, 165, 0),   # F7
            (255, 69, 0),    # F8
            (255, 0, 0),     # CLEAR
            (139, 0, 0),     # NIR
        ]

        self.channel_labels = [
            "F1",
            "F2",
            "F3",
            "F4",
            "Green – 555nm",
            "F6",
            "F7",
            "F8",
            "CLEAR",
            "NIR",
        ]

        # Multi-Spectral Analysis (line plot)
        self.multi_spectral_analysis_plot = PlotWidget(title="Multi-Spectral Analysis")
        self.multi_spectral_analysis_plot.setLabel("left", "Intensity")
        self.multi_spectral_analysis_plot.setLabel("bottom", "Channel index")
        self.multi_spectral_analysis_plot.addLegend()
        self.plots["Multi-Spectral Analysis"] = self.multi_spectral_analysis_plot

        for color, label in zip(self.spectral_colors, self.channel_labels):
            pen = mkPen(color=color, width=2)
            curve = self.multi_spectral_analysis_plot.plot(pen=pen, name=label)
            self.spectral_curves.append(curve)

        layout.addWidget(self.multi_spectral_analysis_plot, 1, 0, 1, 3)

        # Real-time bar graph snapshot
        self.spectral_bar_values = [0] * len(self.channel_labels)
        self.spectral_bar_plot = PlotWidget(title="Multi-Spectral Snapshot")
        self.spectral_bar_plot.setLabel("left", "Intensity")
        self.spectral_bar_plot.setLabel("bottom", "Channel")
        self.spectral_bar_plot.setYRange(0, 4095)

        x_positions = list(range(len(self.channel_labels)))
        self.spectral_bar_item = BarGraphItem(
            x=x_positions,
            height=self.spectral_bar_values,
            width=0.6,
            brushes=[QColor(*color) for color in self.spectral_colors],
        )
        self.spectral_bar_plot.addItem(self.spectral_bar_item)

        ax = self.spectral_bar_plot.getAxis("bottom")
        ax.setTicks([list(zip(x_positions, self.channel_labels))])

        layout.addWidget(self.spectral_bar_plot, 2, 0, 1, 3)

        dashboard.setLayout(layout)
        return dashboard

    # ------------------------------------------------------------------
    # Monitoring control
    # ------------------------------------------------------------------
    def start_monitoring(self) -> None:
        """
        Start Modbus polling on the selected COM port.
        """
        port = self.com_dropdown.currentText()
        if not port:
            self.statusBar().showMessage("No COM port selected.")
            return

        poll_ms = int(self.poll_combo.currentData())
        ph_id = self.ph_id_spin.value()
        spectral_id = self.spectral_id_spin.value()

        reactor_cfg = ReactorConfig(
            name="Reactor 1",
            ph_slave_id=ph_id,
            spectral_slave_id=spectral_id,
        )

        # Clean up existing poller if needed
        if self.poller is not None:
            self.poller.stop()
            self.poller.wait()

        self.poller = ModbusPoller(
            port=port,
            reactor_config=reactor_cfg,
            poll_interval_ms=poll_ms,
            parent=self,
        )
        self.poller.reading_ready.connect(self.handle_reading)
        self.poller.error.connect(self._handle_backend_error)
        self.poller.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.statusBar().showMessage(f"Started Modbus polling on {port}.")

    def stop_monitoring(self) -> None:
        """
        Stop Modbus polling.
        """
        if self.poller is not None:
            self.poller.stop()
            self.poller.wait()
            self.poller = None

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.statusBar().showMessage("Stopped Modbus polling.")

    def _handle_backend_error(self, message: str) -> None:
        """
        Display backend errors in the status bar and also log them.
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.statusBar().showMessage(message)
        self.serial_data_area.append(f"[{timestamp}] ERROR: {message}\n")

    # ------------------------------------------------------------------
    # Control buttons
    # ------------------------------------------------------------------
    def toggle_relay(self) -> None:
        """
        Toggle the relay (circulation pump) state.
        """
        self.relay_state = not self.relay_state
        state_text = "ON" if self.relay_state else "OFF"
        self.relay_button.setText(f"Circ Pump: {state_text}")
        if self.poller is not None:
            self.poller.set_relay_target(self.relay_state)

    def toggle_led(self) -> None:
        """
        Toggle the LED (light source) state.
        """
        self.led_state = not self.led_state
        state_text = "ON" if self.led_state else "OFF"
        self.led_button.setText(f"Light Source: {state_text}")
        if self.poller is not None:
            self.poller.set_led_target(self.led_state)

    # ------------------------------------------------------------------
    # Data handling
    # ------------------------------------------------------------------
    def handle_reading(self, data: Dict[str, Any]) -> None:
        """
        Receive a full reading dict from the backend and update UI + logs.
        """
        timestamp = data.get("timestamp", "")
        pretty_json = json.dumps(data, indent=4)
        self.serial_data_area.append(f"[{timestamp}]\n{pretty_json}\n")

        self.logged_data.append(data)

        # Trim the text area if it grows too large
        if self.serial_data_area.document().blockCount() > 500:
            cursor = self.serial_data_area.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.select(cursor.BlockUnderCursor)
            cursor.removeSelectedText()

        self.update_dashboard(data)

    def update_dashboard(self, data: Dict[str, Any]) -> None:
        """
        Update graphs and button states from a reading dict.
        """
        # Mirror relay / LED state
        if "relay" in data:
            self.relay_state = bool(data["relay"])
            self.relay_button.setChecked(self.relay_state)
            self.relay_button.setText(
                f"Circ Pump: {'ON' if self.relay_state else 'OFF'}"
            )

        if "led" in data:
            self.led_state = bool(data["led"])
            self.led_button.setChecked(self.led_state)
            self.led_button.setText(
                f"Light Source: {'ON' if self.led_state else 'OFF'}"
            )

        self.time_index += 1

        # Temperature and pH
        if "temperature" in data:
            self._update_graph("Temperature (°C)", data["temperature"])

        ph_obj = data.get("pH", {})
        if isinstance(ph_obj, dict) and "value" in ph_obj:
            self._update_graph("pH Value", ph_obj["value"])

        # Harvesting rate from green spectral channel
        light = data.get("light", [])
        if isinstance(light, list) and len(light) > GREEN_CHANNEL_INDEX:
            raw_green = light[GREEN_CHANNEL_INDEX]
            kg_hr = (
                (HARVEST_NONE_VALUE - raw_green)
                * HARVEST_MAX_KG_PER_HOUR
                / (HARVEST_NONE_VALUE - HARVEST_FULL_VALUE)
            )
            kg_hr = max(0.0, min(HARVEST_MAX_KG_PER_HOUR, kg_hr))
            self._update_graph("Harvesting Rate (kg/h)", kg_hr)

        # Spectral time-series curves
        if isinstance(light, list):
            for i, val in enumerate(light[: len(self.spectral_curves)]):
                curve = self.spectral_curves[i]
                x_old, y_old = curve.getData()
                xs = list(x_old) if x_old is not None else []
                ys = list(y_old) if y_old is not None else []
                xs.append(self.time_index)
                ys.append(val)
                x_arr = np.array(xs[-100:], dtype=float)
                y_arr = np.array(ys[-100:], dtype=float)
                curve.setData(x=x_arr, y=y_arr)

        # Bar graph snapshot
        if isinstance(light, list):
            vals = light[: len(self.channel_labels)]
            self.spectral_bar_values = vals
            self.spectral_bar_plot.removeItem(self.spectral_bar_item)
            self.spectral_bar_item = BarGraphItem(
                x=list(range(len(vals))),
                height=vals,
                width=0.6,
                brushes=[QColor(*c) for c in self.spectral_colors],
            )
            self.spectral_bar_plot.addItem(self.spectral_bar_item)

        # Scroll the time axis for the main plots
        start = max(0, self.time_index - 30)
        for key in [
            "Temperature (°C)",
            "pH Value",
            "Harvesting Rate (kg/h)",
            "Multi-Spectral Analysis",
        ]:
            pw = self.plots.get(key)
            if pw is not None:
                pw.setXRange(start, self.time_index, padding=0)

    def _update_graph(self, graph_title: str, value: float) -> None:
        curve = self.graphs.get(graph_title)
        if curve is None:
            return

        x_old, y_old = curve.getData()
        xs = list(x_old) if x_old is not None else []
        ys = list(y_old) if y_old is not None else []
        xs.append(self.time_index)
        ys.append(value)

        x_arr = np.array(xs[-100:], dtype=float)
        y_arr = np.array(ys[-100:], dtype=float)
        curve.setData(x=x_arr, y=y_arr)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def export_to_csv(self) -> None:
        """
        Export logged data to CSV (temperature, pH, spectral channels).
        """
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Logged Data",
            "",
            "CSV Files (*.csv);;All Files (*)",
            options=options,
        )

        if not file_path:
            return

        try:
            with open(file_path, mode="w", newline="") as file:
                writer = csv.writer(file)

                headers = [
                    "Timestamp",
                    "Temperature (°C)",
                    "pH Value",
                ]

                spectral_headers = self.channel_labels
                headers.extend(spectral_headers)

                writer.writerow(headers)

                for entry in self.logged_data:
                    timestamp = entry.get("timestamp", "")
                    temperature = entry.get("temperature", "")
                    ph_obj = entry.get("pH", {})
                    ph_value = ""
                    if isinstance(ph_obj, dict):
                        ph_value = ph_obj.get("value", "")

                    light = entry.get("light", [])
                    if isinstance(light, list):
                        light_values = light[: len(spectral_headers)]
                    else:
                        light_values = [""] * len(spectral_headers)

                    row = [timestamp, temperature, ph_value] + light_values
                    writer.writerow(row)

            self.statusBar().showMessage("Data exported successfully.")
        except Exception as exc:
            self.statusBar().showMessage(f"Error exporting data: {exc}")
