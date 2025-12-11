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
    QDoubleSpinBox,
    QScrollArea,
)


from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtCore import Qt

from pyqtgraph import PlotWidget, mkPen, BarGraphItem

from modules.backend import ModbusPoller, ReactorConfig
from modules.utils import resource_path





# Harvesting calibration defaults for the green channel.
# These are just starting values; the user can override them in the Calibration section.
HARVEST_DEFAULT_START_INTENSITY = 1000   # intensity where harvesting starts (> 0%)
HARVEST_DEFAULT_FULL_INTENSITY = 10000   # intensity where harvesting reaches 100%
GREEN_CHANNEL_INDEX = 4                  # zero-based index into "light" list for green





# # Harvesting-rate calibration
# HARVEST_NONE_VALUE = 1295   # when green sensor reads this -> 0 kg/h
# HARVEST_FULL_VALUE = 20     # when green sensor reads this or less -> full harvest
# HARVEST_MAX_KG_PER_HOUR = 3.0
# GREEN_CHANNEL_INDEX = 4     # zero-based index into "light" list for green


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


        # Calibration parameters (per reactor)
        self.green_start_intensity: int = HARVEST_DEFAULT_START_INTENSITY
        self.green_full_intensity: int = HARVEST_DEFAULT_FULL_INTENSITY
        self.temp_offset: float = 0.0  # °C, applied as temp_corrected = raw + offset
        self.ph_offset: float = 0.0    # pH units, applied as ph_corrected = raw + offset


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

        # ----------------------
        # Reactor 1 tab (scrollable)
        # ----------------------
        self.dashboard_tab = QWidget()
        dashboard_layout = QVBoxLayout()

        # Content that will live inside the scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        content_widget = QWidget()
        content_layout = QVBoxLayout()

        self.top_bar = self._create_top_bar()
        self.dashboard = self._create_dashboard()
        self.calibration_group = self._create_calibration_group()

        content_layout.addLayout(self.top_bar)
        content_layout.addWidget(self.dashboard)
        content_layout.addWidget(self.calibration_group)
        content_layout.addStretch(1)

        content_widget.setLayout(content_layout)
        scroll_area.setWidget(content_widget)

        dashboard_layout.addWidget(scroll_area)
        self.dashboard_tab.setLayout(dashboard_layout)

        # ----------------------
        # Data / log tab
        # ----------------------
        self.serial_data_tab = QWidget()
        serial_data_layout = QVBoxLayout()
        self.serial_data_view = QLabel("Incoming Data Snapshot:")
        self.serial_data_area = QTextEdit()
        self.serial_data_area.setReadOnly(True)
        serial_data_layout.addWidget(self.serial_data_view)
        serial_data_layout.addWidget(self.serial_data_area)
        self.serial_data_tab.setLayout(serial_data_layout)

        # ----------------------
        # Configuration tab (COM port etc.)
        # ----------------------
        self.config_tab = self._create_config_tab()

        # Add tabs (order matters; config goes at the end)
        self.tabs.addTab(self.dashboard_tab, "Reactor 1")
        self.tabs.addTab(self.serial_data_tab, "Sensor Data Log")
        self.tabs.addTab(self.config_tab, "Configuration")

        central_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Status bar
        self.statusBar().showMessage("Ready")



    def _create_top_bar(self) -> QHBoxLayout:
        """
        Create the top toolbar for the reactor view.

        Note:
        - COM port selection has been moved to the Configuration tab.
        - This bar now focuses on poll interval, slave IDs, and control buttons.
        """
        layout = QHBoxLayout()

        # Poll interval selection
        self.poll_label = QLabel("Poll interval:")
        self.poll_combo = QComboBox()
        self.poll_combo.addItem("0.5 s", 500)
        self.poll_combo.addItem("1.0 s", 1000)
        self.poll_combo.addItem("2.0 s", 2000)
        self.poll_combo.addItem("5.0 s", 5000)
        self.poll_combo.addItem("10 s", 10000)
        self.poll_combo.addItem("30 s", 30000)
        self.poll_combo.addItem("1 min", 60000)
        self.poll_combo.setCurrentIndex(1)  # default: 1.0 s

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

        # Layout arrangement
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






    def _create_config_tab(self) -> QWidget:
        """
        Create the Configuration tab.

        Currently holds:
        - COM port selection
        - Refresh ports button

        This is also where we can add more reactor/global config later.
        """
        tab = QWidget()
        layout = QVBoxLayout()

        row = QHBoxLayout()

        self.com_label = QLabel("Serial port:")
        self.com_dropdown = QComboBox()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._refresh_com_ports)

        row.addWidget(self.com_label)
        row.addWidget(self.com_dropdown)
        row.addWidget(self.refresh_button)
        row.addStretch(1)

        layout.addLayout(row)
        layout.addStretch(1)

        tab.setLayout(layout)

        # Populate ports once the widgets exist
        self._refresh_com_ports()

        return tab





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
        """
        Build the main dashboard with time-series graphs and spectral views.

        Notes:
        - Spectral data:
            Backend provides 9 values: [F1..F8, NIR] with CLEAR already removed.
        - All spectral labels are colour/wavelength; CLEAR is not shown in the GUI.
        """
        dashboard = QGroupBox("Sensor Dashboard")
        layout = QGridLayout()
        self.spectral_curves = []

        # Helper to define the standard time-series graphs
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
        add_graph("Harvesting Rate (%)", "Harvest %", "y", (0, 2))
        # add_graph("Harvesting Rate (kg/h)", "kg/h", "y", (0, 2))

        # Spectral colours and labels (CLEAR is intentionally omitted)
        # Order matches backend: [F1, F2, F3, F4, F5, F6, F7, F8, NIR]
        self.spectral_colors = [
            (148, 0, 211),   # Violet – 415nm (F1)
            (75, 0, 130),    # Indigo – 445nm (F2)
            (0, 0, 255),     # Blue – 480nm   (F3)
            (0, 255, 255),   # Cyan – 515nm   (F4)
            (0, 255, 0),     # Green – 555nm  (F5)
            (173, 255, 47),  # Yellow – 590nm (F6)
            (255, 165, 0),   # Orange – 630nm (F7)
            (255, 69, 0),    # Red – 680nm    (F8)
            (139, 0, 0),     # Near IR – 740nm (NIR)
        ]

        self.channel_labels = [
            "Violet – 415nm",
            "Indigo – 445nm",
            "Blue – 480nm",
            "Cyan – 515nm",
            "Green – 555nm",
            "Yellow – 590nm",
            "Orange – 630nm",
            "Red – 680nm",
            "Near IR – 740nm",
        ]

        # Multi-Spectral Analysis (line plot)
        self.multi_spectral_analysis_plot = PlotWidget(title="Multi-Spectral Analysis")
        self.multi_spectral_analysis_plot.setLabel("left", "Intensity")
        self.multi_spectral_analysis_plot.setLabel("bottom", "Channel")
        self.multi_spectral_analysis_plot.addLegend()
        self.plots["Multi-Spectral Analysis"] = self.multi_spectral_analysis_plot

        # One curve per spectral channel, all labelled with colour/wavelength
        for color, label in zip(self.spectral_colors, self.channel_labels):
            pen = mkPen(color=color, width=2)
            curve = self.multi_spectral_analysis_plot.plot(pen=pen, name=label)
            self.spectral_curves.append(curve)

        layout.addWidget(self.multi_spectral_analysis_plot, 1, 0, 1, 3)

        # Real-time bar graph snapshot (also no CLEAR)
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




    def _create_calibration_group(self) -> QGroupBox:
        """
        Build the calibration section for this reactor.

        - Green (555 nm) harvesting calibration:
            * Start intensity: where harvesting begins (> 0%).
            * Full intensity: where harvesting reaches 100%.
        - Linear offsets:
            * Temperature offset (raw °C + offset).
            * pH offset (raw pH + offset).
        """
        group = QGroupBox("Calibration")
        layout = QGridLayout()

        # Green harvesting calibration
        row = 0
        layout.addWidget(QLabel("Green channel (555 nm) calibration"), row, 0, 1, 2)
        row += 1

        layout.addWidget(QLabel("Start intensity (0% → >0%):"), row, 0)
        self.green_start_spin = QSpinBox()
        self.green_start_spin.setRange(0, 65535)
        self.green_start_spin.setValue(self.green_start_intensity)
        self.green_start_spin.valueChanged.connect(
            lambda v: setattr(self, "green_start_intensity", int(v))
        )
        layout.addWidget(self.green_start_spin, row, 1)
        row += 1

        layout.addWidget(QLabel("Full intensity (100%):"), row, 0)
        self.green_full_spin = QSpinBox()
        self.green_full_spin.setRange(1, 65535)
        self.green_full_spin.setValue(self.green_full_intensity)
        self.green_full_spin.valueChanged.connect(
            lambda v: setattr(self, "green_full_intensity", int(v))
        )
        layout.addWidget(self.green_full_spin, row, 1)
        row += 1

        # Temperature offset
        layout.addWidget(QLabel("Temperature offset (°C):"), row, 0)
        self.temp_offset_spin = QDoubleSpinBox()
        self.temp_offset_spin.setDecimals(2)
        self.temp_offset_spin.setRange(-20.0, 20.0)
        self.temp_offset_spin.setSingleStep(0.1)
        self.temp_offset_spin.setValue(self.temp_offset)
        self.temp_offset_spin.valueChanged.connect(
            lambda v: setattr(self, "temp_offset", float(v))
        )
        layout.addWidget(self.temp_offset_spin, row, 1)
        row += 1

        # pH offset
        layout.addWidget(QLabel("pH offset (pH units):"), row, 0)
        self.ph_offset_spin = QDoubleSpinBox()
        self.ph_offset_spin.setDecimals(3)
        self.ph_offset_spin.setRange(-2.0, 2.0)
        self.ph_offset_spin.setSingleStep(0.01)
        self.ph_offset_spin.setValue(self.ph_offset)
        self.ph_offset_spin.valueChanged.connect(
            lambda v: setattr(self, "ph_offset", float(v))
        )
        layout.addWidget(self.ph_offset_spin, row, 1)
        row += 1

        # Small explanatory note
        note = QLabel(
            "Harvest % is 0 below Start, ramps linearly to 100 at Full.\n"
            "Temperature and pH offsets are applied as: corrected = raw + offset."
        )
        note.setWordWrap(True)
        layout.addWidget(note, row, 0, 1, 2)

        group.setLayout(layout)
        return group





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



        # Temperature with linear offset
        temp_raw = data.get("temperature", None)
        if temp_raw is not None:
            temp_corrected = temp_raw + self.temp_offset
            self._update_graph("Temperature (°C)", temp_corrected)

        # pH with linear offset
        ph_obj = data.get("pH", {})
        if isinstance(ph_obj, dict) and "value" in ph_obj:
            ph_raw = ph_obj["value"]
            ph_corrected = ph_raw + self.ph_offset
            self._update_graph("pH Value", ph_corrected)

        # Harvesting rate from green spectral channel, as %
        light = data.get("light", [])
        if isinstance(light, list) and len(light) > GREEN_CHANNEL_INDEX:
            raw_green = light[GREEN_CHANNEL_INDEX]

            start = self.green_start_intensity
            full = self.green_full_intensity
            # Avoid divide-by-zero or inverted ranges
            if full <= start:
                full = start + 1

            if raw_green < start:
                harvest_pct = 0.0
            elif raw_green >= full:
                harvest_pct = 100.0
            else:
                harvest_pct = (raw_green - start) * 100.0 / (full - start)

            self._update_graph("Harvesting Rate (%)", harvest_pct)


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
            "Harvesting Rate (%)",
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
                    temp_raw = entry.get("temperature", "")
                    temperature = ""
                    if temp_raw != "":
                        try:
                            temperature = float(temp_raw) + self.temp_offset
                        except Exception:
                            temperature = temp_raw

                    ph_obj = entry.get("pH", {})
                    ph_value = ""
                    if isinstance(ph_obj, dict):
                        raw_ph = ph_obj.get("value", "")
                        if raw_ph != "":
                            try:
                                ph_value = float(raw_ph) + self.ph_offset
                            except Exception:
                                ph_value = raw_ph

                    # timestamp = entry.get("timestamp", "")
                    # temperature = entry.get("temperature", "")
                    # ph_obj = entry.get("pH", {})
                    # ph_value = ""
                    # if isinstance(ph_obj, dict):
                    #     ph_value = ph_obj.get("value", "")

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
