import sys

import time

import csv

from pathlib import Path



from datetime import datetime, timedelta, timezone

from math import radians, sin, cos, sqrt, atan2







import serial.tools.list_ports















from PySide6.QtCore import QTimer, Qt, QThread







from PySide6.QtWidgets import (







    QApplication,







    QComboBox,







    QGroupBox,







    QHBoxLayout,







    QLabel,







    QMainWindow,







    QMessageBox,







    QPlainTextEdit,







    QPushButton,







    QVBoxLayout,







    QWidget,







)















from serial_worker import SerialWorker







from protocol.packet_parser import PacketParser







from protocol.telemetry import TelemetryDecoder



from map_widget import MapWidget























class MainWindow(QMainWindow):















    def __init__(self):







        super().__init__()















        # =====================================================







        # WINDOW







        # =====================================================















        self.setWindowTitle("HAB Ground Station")







        self.resize(1400, 900)















        # =====================================================







        # SERIAL VARIABLES







        # =====================================================















        self.serial_thread = None







        self.serial_worker = None







        # =====================================================







        # TIME DISPLAY







        # =====================================================







        # IST = UTC+05:30







        self.ist_timezone = timezone(



            timedelta(hours=5, minutes=30)



        )







        self.last_data_time = None



        # =====================================================

        # CSV FLIGHT LOGGER

        # =====================================================



        self.log_dir = Path(__file__).resolve().parent / "logs"

        self.log_dir.mkdir(parents=True, exist_ok=True)



        log_timestamp = datetime.now(self.ist_timezone).strftime("%Y%m%d_%H%M%S")

        self.log_file_path = self.log_dir / f"HAB_Log_{log_timestamp}.csv"



        self.log_file = open(

            self.log_file_path,

            "w",

            newline="",

            encoding="utf-8"

        )



        self.csv_writer = csv.writer(self.log_file)



        self.csv_writer.writerow([

            "TIME (IST)",

            "ALT (m)",

            "LAT (deg)",

            "LON (deg)",

            "HORIZONTAL DISP (m)",

            "SPEED (m/s)",

            "TEMP (C)",

            "PRESSURE (mbar)",

            "RSSI (dBm)",

            "BATTERY (V)",

            "HEATER",

            "PITCH (deg)",

            "ROLL (deg)",

            "YAW RATE (deg/s)"

        ])

        self.log_file.flush()



        # =====================================================

        # =====================================================
        # IMAGE RECEIVER / IMAGE LOGGER
        # =====================================================

        self.image_dir = Path(__file__).resolve().parent / "images"
        self.image_dir.mkdir(parents=True, exist_ok=True)

        self.image_log_dir = Path(__file__).resolve().parent / "image_logs"
        self.image_log_dir.mkdir(parents=True, exist_ok=True)

        image_log_timestamp = datetime.now(self.ist_timezone).strftime("%Y%m%d_%H%M%S")
        self.image_log_file_path = self.image_log_dir / f"HAB_Image_Log_{image_log_timestamp}.csv"
        self.image_log_file = open(self.image_log_file_path, "w", newline="", encoding="utf-8")
        self.image_csv_writer = csv.writer(self.image_log_file)
        self.image_csv_writer.writerow([
            "SESSION", "TIME (IST)", "PACKET ID", "CRC", "DATA BYTES", "DATA HEX",
            "ALT (m)", "LAT (deg)", "LON (deg)", "RSSI (dBm)"
        ])
        self.image_log_file.flush()

        self.IMAGE_TOTAL_PACKETS = 610
        self.IMAGE_DATA_BYTES = 58
        self.IMAGE_PACKET_LENGTH = 63
        self.IMAGE_PACKET_TYPE = 0x05
        self.IMAGE_LAST_ID = self.IMAGE_TOTAL_PACKETS - 1

        self.image_session_number = 0
        self.image_active = False
        self.image_packets = {}
        self.image_received_ids = set()
        self.image_crc_errors = 0
        self.image_duplicate_packets = 0
        self.image_session_started = None
        self.image_session_altitude = None
        self.image_session_latitude = None
        self.image_session_longitude = None
        self.image_session_rssi = None
        self.image_last_saved_path = None
        self.last_telemetry = {}

        # Barometric estimated-altitude reference.
        # The first valid beacon is treated as 0 m. GPS altitude is
        # intentionally NOT used as the barometric altitude reference.
        self.est_alt_reference_pressure = None

        # JPEG retransmission state.
        # After the first image pass reaches packet 609, the GUI waits for
        # the next telemetry beacon before requesting missing packet IDs.
        self.image_missing_ids = []
        self.image_current_request_ids = []
        self.image_waiting_for_beacon = False
        self.image_first_pass_complete = False
        self.image_last_packet_time = None

        # Retransmission request delay:
        # A qualifying beacon starts a 1-second timer. The actual missing-ID
        # request is sent only when this timer expires.
        self.retransmission_timer = QTimer(self)
        self.retransmission_timer.setSingleShot(True)
        self.retransmission_timer.timeout.connect(
            self.send_retransmission_request_after_beacon
        )

        # GPS MAP FILTER

        # =====================================================



        self.last_valid_lat = None

        self.last_valid_lon = None

        self.last_valid_gps_time = None



        # Launch site / horizontal displacement

        self.launch_lat = None

        self.launch_lon = None



        # Maximum physically allowed balloon speed for map updates

        # 100 m/s = 360 km/h

        self.max_gps_speed_mps = 100.0















        # =====================================================







        # PACKET PARSER







        # =====================================================















        self.packet_parser = PacketParser()
        self.est_alt_reference_pressure = None




        # Reset GPS map filter for a new connection

        self.last_valid_lat = None

        self.last_valid_lon = None

        self.last_valid_gps_time = None















        # =====================================================







        # TELEMETRY DECODER







        # =====================================================















        self.telemetry_decoder = TelemetryDecoder()















        # =====================================================







        # BUILD GUI







        # =====================================================















        self.setup_ui()







        # Live IST clock







        self.clock_timer = QTimer(self)







        self.clock_timer.timeout.connect(



            self.update_time_display



        )







        self.update_time_display()







        self.clock_timer.start(1000)















        # =====================================================







        # DETECT COM PORTS







        # =====================================================















        self.refresh_ports()















    # =========================================================







    # SETUP GUI







    # =========================================================















    def setup_ui(self):















        # -----------------------------------------------------







        # CENTRAL WIDGET







        # -----------------------------------------------------















        central_widget = QWidget()















        self.setCentralWidget(







            central_widget







        )















        main_layout = QVBoxLayout(







            central_widget







        )















        # =====================================================







        # CONNECTION BAR







        # =====================================================















        connection_box = QGroupBox(







            "Ground Station Connection"







        )















        connection_layout = QHBoxLayout(







            connection_box







        )















        # -----------------------------------------------------







        # PORT







        # -----------------------------------------------------















        port_label = QLabel(







            "Port:"







        )















        self.port_combo = QComboBox()















        self.port_combo.setMinimumWidth(







            100







        )















        # -----------------------------------------------------







        # REFRESH BUTTON







        # -----------------------------------------------------















        self.refresh_button = QPushButton(







            "↻"







        )















        self.refresh_button.setFixedWidth(







            50







        )















        # -----------------------------------------------------







        # BAUD







        # -----------------------------------------------------















        baud_label = QLabel(







            "Baud:"







        )















        self.baud_combo = QComboBox()















        self.baud_combo.addItems([







            "9600",







            "19200",







            "38400",







            "57600",







            "115200",







        ])















        self.baud_combo.setCurrentText(







            "115200"







        )















        # -----------------------------------------------------







        # CONNECT BUTTON







        # -----------------------------------------------------















        self.connect_button = QPushButton(







            "CONNECT"







        )















        # -----------------------------------------------------







        # CONNECTION STATUS







        # -----------------------------------------------------















        self.connection_status = QLabel(







            "● DISCONNECTED"







        )















        self.connection_status.setStyleSheet(







            "color: red; font-weight: bold;"







        )















        # -----------------------------------------------------







        # LAYOUT







        # -----------------------------------------------------















        connection_layout.addWidget(







            port_label







        )















        connection_layout.addWidget(







            self.port_combo







        )















        connection_layout.addWidget(







            self.refresh_button







        )















        connection_layout.addSpacing(







            20







        )















        connection_layout.addWidget(







            baud_label







        )















        connection_layout.addWidget(







            self.baud_combo







        )















        connection_layout.addSpacing(







            20







        )















        connection_layout.addWidget(







            self.connect_button







        )















        connection_layout.addStretch()







        # -----------------------------------------------------







        # TIME INFORMATION







        # -----------------------------------------------------







        self.last_data_label = QLabel(



            "LAST DATA: --:--:-- IST"



        )







        self.current_time_label = QLabel(



            "CURRENT: --:--:-- IST"



        )







        self.last_data_label.setStyleSheet(



            "font-weight: bold;"



        )







        self.current_time_label.setStyleSheet(



            "font-weight: bold;"



        )







        connection_layout.addWidget(



            self.last_data_label



        )







        connection_layout.addSpacing(20)







        connection_layout.addWidget(



            self.current_time_label



        )







        connection_layout.addSpacing(25)















        connection_layout.addWidget(







            self.connection_status







        )















        main_layout.addWidget(







            connection_box







        )















        # =====================================================
        # BALLOON COMMANDS
        # =====================================================

        command_box = QGroupBox("BALLOON COMMANDS")
        command_layout = QHBoxLayout(command_box)

        self.ping_button = QPushButton("PING")
        self.image_button = QPushButton("TRANSMIT IMAGE")
        self.reset_button = QPushButton("RESET")

        self.ping_button.setMinimumHeight(40)
        self.image_button.setMinimumHeight(40)
        self.reset_button.setMinimumHeight(40)

        command_layout.addWidget(self.ping_button)
        command_layout.addWidget(self.image_button)
        command_layout.addWidget(self.reset_button)

        main_layout.addWidget(command_box)


        # =====================================================







        # MAIN CONTENT







        # =====================================================















        content_layout = QHBoxLayout()















        # =====================================================







        # LIVE FLIGHT MAP







        # =====================================================















        map_box = QGroupBox(







            "LIVE FLIGHT MAP"







        )















        map_layout = QVBoxLayout(







            map_box







        )















        # Real interactive Leaflet map







        self.map_widget = MapWidget()







        map_layout.addWidget(







            self.map_widget







        )















        # TELEMETRY







        # =====================================================















        telemetry_box = QGroupBox(







            "TELEMETRY"







        )















        telemetry_layout = QVBoxLayout(







            telemetry_box







        )















        telemetry_values = [







            ("Altitude", "--- m"),
            ("Estimated Altitude from Launch Site", "--- m"),







            ("Latitude", "---"),







            ("Longitude", "---"),







            ("Horizontal Disp.", "--- m"),







            ("Speed", "--- m/s"),







            ("Temperature", "--- °C"),







            ("Pressure", "--- mbar"),







            ("RSSI", "--- dBm"),







            ("Battery", "--- V"),







            ("Heater", "---"),







            ("Pitch", "--- °"),







            ("Roll", "--- °"),







            ("Yaw Rate", "--- °/s"),







        ]















        self.telemetry_labels = {}















        for name, value in telemetry_values:















            row = QHBoxLayout()















            name_label = QLabel(







                name + ":"







            )















            value_label = QLabel(







                value







            )















            value_label.setAlignment(







                Qt.AlignmentFlag.AlignRight







            )















            value_label.setStyleSheet(







                "font-weight: bold;"







            )















            row.addWidget(







                name_label







            )















            row.addWidget(







                value_label







            )















            telemetry_layout.addLayout(







                row







            )















            self.telemetry_labels[







                name







            ] = value_label















        telemetry_layout.addStretch()















        # -----------------------------------------------------







        # ADD MAP AND TELEMETRY







        # -----------------------------------------------------















        content_layout.addWidget(







            map_box,







            3







        )















        content_layout.addWidget(







            telemetry_box,







            1







        )















        main_layout.addLayout(







            content_layout







        )















        # =====================================================







        # IMAGE RECEIVER







        # =====================================================















        image_box = QGroupBox(







            "IMAGE RECEIVER"







        )















        image_layout = QHBoxLayout(







            image_box







        )















        self.image_status = QLabel(







            "Session: --    Packets: 0 / 610    Missing: 610    CRC Errors: 0    Duplicates: 0"







        )















        image_layout.addWidget(







            self.image_status







        )















        image_layout.addStretch()















        main_layout.addWidget(







            image_box







        )















        # =====================================================







        # SERIAL MONITOR







        # =====================================================















        serial_box = QGroupBox(







            "SERIAL MONITOR"







        )















        serial_layout = QVBoxLayout(







            serial_box







        )















        self.serial_monitor = QPlainTextEdit()















        self.serial_monitor.setReadOnly(







            True







        )















        self.serial_monitor.setMaximumHeight(







            180







        )















        serial_layout.addWidget(







            self.serial_monitor







        )















        main_layout.addWidget(







            serial_box







        )















        # =====================================================







        # SIGNALS







        # =====================================================















        self.refresh_button.clicked.connect(







            self.refresh_ports







        )















        self.connect_button.clicked.connect(







            self.toggle_connection







        )

        self.ping_button.clicked.connect(
        lambda: self.send_balloon_command(0x37, "PING")
        )

        self.image_button.clicked.connect(
        lambda: self.send_balloon_command(0x49, "TRANSMIT IMAGE")
        )

        self.reset_button.clicked.connect(
        self.confirm_reset
        )















    # =========================================================
    # BALLOON COMMANDS
    # =========================================================

    def send_balloon_command(self, command, command_name):
        # Frame sent to the ground-station STM32 over UART:
        # 55 COMMAND
        #
        # The ground station itself adds the radio packet framing:
        # 04 55 COMMAND 00 00
        #
        # 0x37 = PING
        # 0x49 = TRANSMIT IMAGE
        # 0x27 = RESET

        if self.serial_worker is None:
            QMessageBox.warning(
                self,
                "Not Connected",
                "Connect to the ground station first."
            )
            return

        frame = bytes([
            0x55,
            command
        ])

        # Each TRANSMIT IMAGE press starts a fresh image reception session.
        if command == 0x49:
            self.start_image_session()

        success = self.serial_worker.write_data(frame)

        if success:
            self.serial_monitor.appendPlainText(
                f"COMMAND: {command_name}"
            )
            self.serial_monitor.appendPlainText(
                f"TX -> {frame.hex(' ').upper()}"
            )
        else:
            self.serial_monitor.appendPlainText(
                f"COMMAND FAILED: {command_name}"
            )

    def confirm_reset(self):
        reply = QMessageBox.question(
            self,
            "Reset Balloon",
            "Are you sure you want to reset the balloon controller?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.send_balloon_command(0x27, "RESET")


    # =========================================================







    # REFRESH COM PORTS







    # =========================================================















    def refresh_ports(self):















        # Don't refresh while connected







        if self.serial_thread is not None:







            return















        self.port_combo.clear()















        ports = serial.tools.list_ports.comports()















        if not ports:















            self.port_combo.addItem(







                "No ports found"







            )















            return















        for port in ports:















            self.port_combo.addItem(







                port.device







            )















        # Automatically select COM7 if available







        index = self.port_combo.findText(







            "COM7"







        )















        if index >= 0:















            self.port_combo.setCurrentIndex(







                index







            )















    # =========================================================







    # CONNECT / DISCONNECT







    # =========================================================















    def toggle_connection(self):















        if self.serial_thread is None:















            self.connect_serial()















        else:















            self.disconnect_serial()















    # =========================================================







    # CONNECT







    # =========================================================















    def connect_serial(self):















        port = self.port_combo.currentText()















        if port == "No ports found":















            QMessageBox.warning(







                self,







                "Serial Port",







                "No COM port was detected."







            )















            return















        baud = int(







            self.baud_combo.currentText()







        )















        # -----------------------------------------------------







        # Reset parser







        # -----------------------------------------------------















        self.packet_parser = PacketParser()















        # -----------------------------------------------------







        # Create thread







        # -----------------------------------------------------















        self.serial_thread = QThread()















        # -----------------------------------------------------







        # Create worker







        # -----------------------------------------------------















        self.serial_worker = SerialWorker(







            port,







            baud







        )















        # -----------------------------------------------------







        # Move worker to thread







        # -----------------------------------------------------















        self.serial_worker.moveToThread(







            self.serial_thread







        )















        # -----------------------------------------------------







        # Thread started







        # -----------------------------------------------------















        self.serial_thread.started.connect(







            self.serial_worker.start







        )















        # -----------------------------------------------------







        # Data received







        # -----------------------------------------------------















        self.serial_worker.data_received.connect(







            self.handle_serial_data







        )















        # -----------------------------------------------------







        # Error







        # -----------------------------------------------------















        self.serial_worker.error_occurred.connect(







            self.handle_serial_error







        )















        # -----------------------------------------------------







        # Worker finished







        # -----------------------------------------------------















        self.serial_worker.finished.connect(







            self.serial_thread.quit







        )















        self.serial_worker.finished.connect(







            self.serial_worker.deleteLater







        )















        self.serial_thread.finished.connect(







            self.serial_thread.deleteLater







        )















        # -----------------------------------------------------







        # Start thread







        # -----------------------------------------------------















        self.serial_thread.start()















        # -----------------------------------------------------







        # Update GUI







        # -----------------------------------------------------















        self.connection_status.setText(







            "● CONNECTED"







        )















        self.connection_status.setStyleSheet(







            "color: green; font-weight: bold;"







        )















        self.connect_button.setText(







            "DISCONNECT"







        )















        self.port_combo.setEnabled(







            False







        )















        self.baud_combo.setEnabled(







            False







        )















        self.refresh_button.setEnabled(







            False







        )















        self.serial_monitor.appendPlainText(







            f"Connected to {port} @ {baud}"







        )















    # =========================================================







    # SERIAL DATA







    # =========================================================















    def handle_serial_data(







        self,







        data







    ):















        # -----------------------------------------------------







        # Feed raw bytes into packet parser







        # -----------------------------------------------------















        packets = self.packet_parser.feed(







            data







        )















        # -----------------------------------------------------







        # Process every complete packet







        # -----------------------------------------------------















        for payload in packets:















            self.handle_packet(







                payload







            )















    # =========================================================







    # COMPLETE PACKET







    # =========================================================















    def handle_packet(







        self,







        payload







    ):















        length = len(







            payload







        )















        # -----------------------------------------------------







        # Show packet in serial monitor







        # -----------------------------------------------------















        hex_data = payload.hex(







            " "







        ).upper()















        self.serial_monitor.appendPlainText(







            f"PACKET  LEN={length}  {hex_data}"







        )















        # -----------------------------------------------------







        # JPEG packet: ID + type 0x05 + 58 data bytes + CRC16.
        if (len(payload) == self.IMAGE_PACKET_LENGTH
                and payload[2] == self.IMAGE_PACKET_TYPE):
            if self.handle_image_packet(payload):
                return

        # Try to decode as telemetry beacon







        # -----------------------------------------------------















        telemetry = self.telemetry_decoder.decode(







            payload







        )















        # -----------------------------------------------------







        # Not a telemetry packet







        # -----------------------------------------------------















        if telemetry is None:















            return















        # -----------------------------------------------------







        # Telemetry successfully decoded







        # -----------------------------------------------------















        self.update_telemetry(







            telemetry







        )















    # =========================================================







    # UPDATE TELEMETRY







    # =========================================================















    # =========================================================
    # IMAGE RECEIVER
    # =========================================================

    @staticmethod
    def image_crc16(data):
        """CRC16 used by the balloon firmware for JPEG packets."""
        crc = 0xFFFF
        polynomial = 0x8408
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ polynomial
                else:
                    crc >>= 1
        return crc ^ 0xFFFF

    def start_image_session(self):
        self.image_session_number += 1
        self.image_active = True
        self.image_packets = {}
        self.image_received_ids = set()
        self.image_crc_errors = 0
        self.image_duplicate_packets = 0
        self.image_session_started = datetime.now(self.ist_timezone)
        self.image_last_saved_path = None

        # Clear retransmission state for this new image.
        self.image_missing_ids = []
        self.image_current_request_ids = []
        self.image_waiting_for_beacon = False
        self.image_first_pass_complete = False
        self.image_last_packet_time = None

        if self.retransmission_timer.isActive():
            self.retransmission_timer.stop()

        self.image_session_altitude = self.last_telemetry.get("altitude")
        self.image_session_latitude = self.last_telemetry.get("latitude")
        self.image_session_longitude = self.last_telemetry.get("longitude")
        self.image_session_rssi = self.last_telemetry.get("rssi")
        self.update_image_status()
        self.serial_monitor.appendPlainText(
            f"IMAGE SESSION {self.image_session_number} STARTED - "
            f"ALT={self.image_session_altitude if self.image_session_altitude is not None else 'N/A'} m"
        )

    def update_image_status(self):
        received = len(self.image_received_ids)
        missing = self.IMAGE_TOTAL_PACKETS - received
        session_text = str(self.image_session_number) if self.image_session_number else "--"

        if self.image_active and self.image_waiting_for_beacon and missing > 0:
            phase = "WAITING FOR BEACON"
        elif self.image_active and self.image_current_request_ids and missing > 0:
            phase = "RETRANSMITTING"
        elif self.image_active:
            phase = "RECEIVING"
        else:
            phase = "IDLE"

        self.image_status.setText(
            f"Session: {session_text}    Packets: {received} / {self.IMAGE_TOTAL_PACKETS}    "
            f"Missing: {missing}    CRC Errors: {self.image_crc_errors}    "
            f"Duplicates: {self.image_duplicate_packets}    {phase}"
        )

    def handle_image_packet(self, payload):
        if not self.image_active:
            return True

        if len(payload) != self.IMAGE_PACKET_LENGTH or payload[2] != self.IMAGE_PACKET_TYPE:
            return False

        packet_id = (payload[0] << 8) | payload[1]
        if packet_id >= self.IMAGE_TOTAL_PACKETS:
            return False

        received_crc = payload[61] | (payload[62] << 8)
        calculated_crc = self.image_crc16(payload[:61])
        crc_ok = received_crc == calculated_crc

        # Any validly framed JPEG packet counts as activity. Beacons may arrive
        # between JPEG packets, so they must not trigger retransmission unless
        # the JPEG stream has been silent for the full timeout.
        self.image_last_packet_time = time.monotonic()

        # A new JPEG packet means the stream is active again. Cancel any
        # pending 1-second retransmission request that was waiting on a beacon.
        if self.retransmission_timer.isActive():
            self.retransmission_timer.stop()

        now_text = datetime.now(self.ist_timezone).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.image_csv_writer.writerow([
            self.image_session_number, now_text, packet_id,
            "OK" if crc_ok else "ERROR", self.IMAGE_DATA_BYTES, payload[3:61].hex().upper(),
            self.image_session_altitude if self.image_session_altitude is not None else "",
            f"{self.image_session_latitude:.6f}" if self.image_session_latitude is not None else "",
            f"{self.image_session_longitude:.6f}" if self.image_session_longitude is not None else "",
            self.image_session_rssi if self.image_session_rssi is not None else ""
        ])
        self.image_log_file.flush()

        if not crc_ok:
            self.image_crc_errors += 1
            self.update_image_status()
            self.serial_monitor.appendPlainText(
                f"JPEG CRC ERROR: ID={packet_id} RX={received_crc:04X} CALC={calculated_crc:04X}"
            )
            return True

        if packet_id in self.image_received_ids:
            self.image_duplicate_packets += 1
        else:
            self.image_received_ids.add(packet_id)
            self.image_packets[packet_id] = bytes(payload[3:61])

        self.update_image_status()

        # If all packets are present, the image is complete immediately.
        # Otherwise, do NOT assume packet 609 means the stream has ended.
        # Telemetry beacons can appear between JPEG packets. The retransmission
        # decision is made only when a beacon arrives after >5 seconds with no
        # JPEG packet received.
        if len(self.image_received_ids) == self.IMAGE_TOTAL_PACKETS:
            self.finish_image_session()

        return True

    def prepare_image_retransmission(self):
        """Find missing IDs after a >5 s JPEG silence and prepare a request."""
        if not self.image_active:
            return

        missing_ids = [
            pid for pid in range(self.IMAGE_TOTAL_PACKETS)
            if pid not in self.image_received_ids
        ]

        self.image_missing_ids = missing_ids
        self.image_current_request_ids = []
        self.image_first_pass_complete = True

        if not missing_ids:
            self.finish_image_session()
            return

        # The caller only reaches here after a telemetry beacon arrives and
        # the JPEG stream has been silent for more than 5 seconds.
        self.image_waiting_for_beacon = True
        self.update_image_status()

        self.serial_monitor.appendPlainText(
            f"IMAGE PASS COMPLETE: {len(missing_ids)} packets missing. "
            "Waiting for next beacon before requesting retransmission."
        )
        self.serial_monitor.appendPlainText(
            "MISSING JPEG IDS: " + self.format_id_ranges(missing_ids)
        )

    @staticmethod
    def format_id_ranges(ids):
        if not ids:
            return "NONE"

        ids = sorted(set(ids))
        ranges = []
        start = previous = ids[0]

        for pid in ids[1:]:
            if pid == previous + 1:
                previous = pid
            else:
                ranges.append(str(start) if start == previous else f"{start}-{previous}")
                start = previous = pid

        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        return ", ".join(ranges)

    def send_retransmission_request_after_beacon(self):
        """Send a missing-ID request only after a telemetry beacon arrives."""
        if not self.image_active or not self.image_waiting_for_beacon:
            return

        # Recalculate from the actual received set. Some requested packets
        # may have arrived since the previous request.
        self.image_missing_ids = [
            pid for pid in range(self.IMAGE_TOTAL_PACKETS)
            if pid not in self.image_received_ids
        ]

        if not self.image_missing_ids:
            self.image_waiting_for_beacon = False
            self.image_current_request_ids = []
            self.finish_image_session()
            return

        # Retry the current batch first. Only advance to the next batch once
        # every ID in the current batch has been recovered.
        if self.image_current_request_ids:
            request_ids = [
                pid for pid in self.image_current_request_ids
                if pid in self.image_missing_ids
            ]
        else:
            request_ids = []

        if not request_ids:
            request_ids = self.image_missing_ids[:30]

        frame = bytearray([0x55, 0x45, len(request_ids)])
        for packet_id in request_ids:
            frame.append((packet_id >> 8) & 0xFF)
            frame.append(packet_id & 0xFF)

        success = (
            self.serial_worker is not None
            and self.serial_worker.write_data(bytes(frame))
        )

        if success:
            self.image_current_request_ids = list(request_ids)
            self.image_waiting_for_beacon = True
            # Start a fresh 5-second silence window. We only send another
            # request after 5 seconds without receiving any JPEG packet and
            # then seeing another telemetry beacon.
            self.image_last_packet_time = time.monotonic()
            self.update_image_status()
            self.serial_monitor.appendPlainText(
                f"RETRANSMISSION REQUEST: {len(request_ids)} missing JPEG packet IDs"
            )
            self.serial_monitor.appendPlainText(
                f"TX -> {bytes(frame).hex(' ').upper()}"
            )
        else:
            self.serial_monitor.appendPlainText(
                "RETRANSMISSION REQUEST FAILED: ground station not connected"
            )

    def finish_image_session(self):
        """Reconstruct/save only after all 610 valid packets are present."""
        if not self.image_active:
            return

        received = len(self.image_received_ids)
        missing_ids = [
            pid for pid in range(self.IMAGE_TOTAL_PACKETS)
            if pid not in self.image_received_ids
        ]

        if missing_ids:
            # Never create a partial JPEG. Keep the session alive for
            # retransmission.
            self.serial_monitor.appendPlainText(
                f"JPEG NOT RECONSTRUCTED: {len(missing_ids)} packets still missing."
            )
            self.image_missing_ids = missing_ids
            self.image_waiting_for_beacon = True
            self.update_image_status()
            return

        reconstructed = bytearray()
        for pid in range(self.IMAGE_TOTAL_PACKETS):
            reconstructed.extend(self.image_packets[pid])

        eoi = reconstructed.find(b"\xFF\xD9")
        if eoi < 0:
            self.serial_monitor.appendPlainText(
                "JPEG NOT SAVED: all packets received, but JPEG EOI (FF D9) was not found."
            )
            return

        jpeg_data = bytes(reconstructed[:eoi + 2])
        timestamp = self.image_session_started.strftime("%Y%m%d_%H%M%S")
        altitude_text = (
            f"{self.image_session_altitude}m"
            if self.image_session_altitude is not None
            else "ALT_UNKNOWN"
        )
        jpeg_path = self.image_dir / (
            f"HAB_Image_{self.image_session_number:02d}_"
            f"{altitude_text}_{timestamp}.jpg"
        )

        with open(jpeg_path, "wb") as image_file:
            image_file.write(jpeg_data)

        self.image_last_saved_path = jpeg_path
        self.image_active = False
        self.image_waiting_for_beacon = False
        if self.retransmission_timer.isActive():
            self.retransmission_timer.stop()
        self.image_current_request_ids = []
        self.image_missing_ids = []
        self.image_first_pass_complete = True
        self.update_image_status()

        self.serial_monitor.appendPlainText(
            f"IMAGE SESSION {self.image_session_number} COMPLETE: "
            f"{received}/{self.IMAGE_TOTAL_PACKETS} packets, "
            f"{self.image_crc_errors} CRC errors"
        )
        self.serial_monitor.appendPlainText(f"JPEG saved: {jpeg_path}")

    def calculate_distance_m(self, lat1, lon1, lat2, lon2):

        """Calculate horizontal ground distance between two GPS coordinates."""

        R = 6371000.0

        lat1 = radians(lat1)

        lat2 = radians(lat2)

        dlat = lat2 - lat1

        dlon = radians(lon2 - lon1)

        a = (

            sin(dlat / 2) ** 2

            + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2

        )

        return 2 * R * atan2(sqrt(a), sqrt(1 - a))



    def gps_position_is_valid(self, latitude, longitude):

        """Reject GPS positions that imply an impossible jump."""

        if not (-90.0 <= latitude <= 90.0):

            return False

        if not (-180.0 <= longitude <= 180.0):

            return False



        now = datetime.now().timestamp()



        if self.last_valid_lat is None:

            self.last_valid_lat = latitude

            self.last_valid_lon = longitude

            self.last_valid_gps_time = now



            if self.launch_lat is None or self.launch_lon is None:

                self.launch_lat = latitude

                self.launch_lon = longitude

            return True



        distance = self.calculate_distance_m(

            self.last_valid_lat, self.last_valid_lon,

            latitude, longitude

        )

        dt = now - self.last_valid_gps_time



        if dt <= 0:

            return False



        calculated_speed = distance / dt



        if calculated_speed > self.max_gps_speed_mps:

            print(

                f"GPS MAP FILTER: rejected jump "

                f"{distance:.1f} m in {dt:.2f} s "

                f"({calculated_speed:.1f} m/s)"

            )

            return False



        self.last_valid_lat = latitude

        self.last_valid_lon = longitude

        self.last_valid_gps_time = now

        return True



    def update_telemetry(







        self,







        telemetry







    ):

        self.last_telemetry = dict(telemetry)

        # Beacons can arrive between JPEG packets. Only use a beacon as the
        # retransmission trigger if no JPEG packet has arrived for >5 seconds.
        #
        # IMPORTANT:
        # Do NOT send the retransmission request immediately when the beacon
        # arrives. Start a 1-second single-shot timer instead. This gives the
        # ground station/balloon a short delay after the beacon before the
        # retransmission request is transmitted.
        if self.image_active and self.image_last_packet_time is not None:
            image_silence = time.monotonic() - self.image_last_packet_time

            if image_silence > 5.0:
                if not self.image_first_pass_complete:
                    self.prepare_image_retransmission()

                if self.image_active and self.image_waiting_for_beacon:
                    # Avoid starting multiple 1-second timers if another
                    # beacon arrives during the waiting period.
                    if not self.retransmission_timer.isActive():
                        self.serial_monitor.appendPlainText(
                            "BEACON RECEIVED: retransmission request scheduled "
                            "for 1 second later."
                        )
                        self.retransmission_timer.start(300)















        # -----------------------------------------------------







        # LAST TELEMETRY UPDATE TIME







        # -----------------------------------------------------







        self.last_data_time = datetime.now(



            self.ist_timezone



        )







        self.update_time_display()















        # -----------------------------------------------------







        # ALTITUDE







        # -----------------------------------------------------















        altitude = telemetry.get(







            "altitude"







        )















        if altitude is not None:















            self.telemetry_labels[







                "Altitude"







            ].setText(







                f"{altitude} m"







            )















        # -----------------------------------------------------







        # LATITUDE







        # -----------------------------------------------------















        latitude = telemetry.get(







            "latitude"







        )















        if latitude is not None:















            self.telemetry_labels[







                "Latitude"







            ].setText(







                f"{latitude:.6f}"







            )















        # -----------------------------------------------------







        # LONGITUDE







        # -----------------------------------------------------















        longitude = telemetry.get(







            "longitude"







        )















        if longitude is not None:















            self.telemetry_labels[







                "Longitude"







            ].setText(







                f"{longitude:.6f}"







            )















        # -----------------------------------------------------







        # -----------------------------------------------------







        # UPDATE LIVE MAP







        # -----------------------------------------------------







        accepted_gps = False

        horizontal_disp = None



        if latitude is not None and longitude is not None:







            if self.gps_position_is_valid(latitude, longitude):







                accepted_gps = True



                self.map_widget.update_position(







                    latitude,







                    longitude







                )



                # Horizontal displacement from launch site

                if self.launch_lat is not None and self.launch_lon is not None:

                    horizontal_disp = self.calculate_distance_m(

                        self.launch_lat, self.launch_lon,

                        latitude, longitude

                    )



                    if horizontal_disp >= 1000.0:

                        self.telemetry_labels["Horizontal Disp."].setText(

                            f"{horizontal_disp / 1000.0:.2f} km"

                        )

                    else:

                        self.telemetry_labels["Horizontal Disp."].setText(

                            f"{horizontal_disp:.0f} m"

                        )















        # SPEED







        # -----------------------------------------------------















        speed = telemetry.get(







            "speed"







        )















        if speed is not None:















            self.telemetry_labels[







                "Speed"







            ].setText(







                f"{speed} m/s"







            )















        # -----------------------------------------------------







        # TEMPERATURE







        # -----------------------------------------------------















        temperature = telemetry.get(







            "temperature"







        )















        if temperature is not None:















            self.telemetry_labels[







                "Temperature"







            ].setText(







                f"{temperature} °C"







            )















        # -----------------------------------------------------







        # PRESSURE







        # -----------------------------------------------------















        pressure = telemetry.get(
            "pressure"
        )

        # -----------------------------------------------------
        # ESTIMATED ALTITUDE FROM PRESSURE
        # -----------------------------------------------------
        # Barometric equation, referenced to the first valid beacon:
        # h = 44330 * [1 - (P/P0)^0.19029495]
        #
        # The first valid beacon is defined as 0 m. The GPS altitude
        # received in the beacon is intentionally ignored here because
        # it is not reliable enough for the altitude reference.
        estimated_altitude = None
        if pressure is not None and pressure > 0:
            if self.est_alt_reference_pressure is None:
                self.est_alt_reference_pressure = float(pressure)

            p0 = self.est_alt_reference_pressure
            estimated_altitude = 44330.0 * (
                1.0 - (float(pressure) / p0) ** 0.19029495
            )

        if estimated_altitude is not None:
            self.telemetry_labels["Estimated Altitude from Launch Site"].setText(
                f"{estimated_altitude:.1f} m"
            )
        else:
            self.telemetry_labels["Estimated Altitude from Launch Site"].setText("--- m")

        if pressure is not None:
            self.telemetry_labels[
                "Pressure"
            ].setText(
                f"{pressure} mbar"
            )

        # -----------------------------------------------------







        # RSSI







        # -----------------------------------------------------















        rssi = telemetry.get(







            "rssi"







        )















        if rssi is not None:















            self.telemetry_labels[







                "RSSI"







            ].setText(







                f"{rssi} dBm"







            )















        # -----------------------------------------------------







        # BATTERY







        # -----------------------------------------------------















        battery = telemetry.get(







            "battery"







        )















        if battery is not None:















            self.telemetry_labels[







                "Battery"







            ].setText(







                f"{battery:.1f} V"







            )















        # -----------------------------------------------------







        # HEATER STATUS

        # -----------------------------------------------------



        heater = telemetry.get("heater")



        if heater == 0x00:

            self.telemetry_labels[

                "Heater"

            ].setText(

                "OFF"

            )

        elif heater == 0x01:

            self.telemetry_labels[

                "Heater"

            ].setText(

                "ON"

            )

        else:

            self.telemetry_labels[

                "Heater"

            ].setText(

                "UNKNOWN"

            )





        # -----------------------------------------------------







        # PITCH







        # -----------------------------------------------------















        pitch = telemetry.get(







            "pitch"







        )















        if pitch is not None:















            self.telemetry_labels[







                "Pitch"







            ].setText(







                f"{pitch} °"







            )















        # -----------------------------------------------------







        # ROLL







        # -----------------------------------------------------















        roll = telemetry.get(







            "roll"







        )















        if roll is not None:















            self.telemetry_labels[







                "Roll"







            ].setText(







                f"{roll} °"







            )















        # -----------------------------------------------------







        # YAW RATE







        # -----------------------------------------------------















        yaw_rate = telemetry.get(







            "yaw_rate"







        )















        if yaw_rate is not None:















            self.telemetry_labels[







                "Yaw Rate"







            ].setText(







                f"{yaw_rate} °/s"







            )















    # =========================================================







        # -----------------------------------------------------

        # CSV LOGGING

        # -----------------------------------------------------



        # -----------------------------------------------------

        # CSV LOGGING

        # -----------------------------------------------------

        # Log EVERY decoded telemetry packet exactly as received.

        # The GPS map filter does NOT affect the CSV logger.

        # -----------------------------------------------------



        log_time = self.last_data_time.strftime("%Y-%m-%d %H:%M:%S")



        raw_horizontal_disp = None

        if (

            latitude is not None

            and longitude is not None

            and self.launch_lat is not None

            and self.launch_lon is not None

        ):

            raw_horizontal_disp = self.calculate_distance_m(

                self.launch_lat,

                self.launch_lon,

                latitude,

                longitude

            )



        self.csv_writer.writerow([

            log_time,

            altitude if altitude is not None else "",
            f"{estimated_altitude:.1f}" if estimated_altitude is not None else "",

            f"{latitude:.6f}" if latitude is not None else "",

            f"{longitude:.6f}" if longitude is not None else "",

            f"{raw_horizontal_disp:.2f}" if raw_horizontal_disp is not None else "",

            speed if speed is not None else "",

            temperature if temperature is not None else "",

            f"{pressure:.2f}" if pressure is not None else "",

            rssi if rssi is not None else "",

            f"{battery:.1f}" if battery is not None else "",

            telemetry.get("heater", ""),

            pitch if pitch is not None else "",

            roll if roll is not None else "",

            yaw_rate if yaw_rate is not None else ""

        ])



        # Flush every row so the flight log is continuously saved.

        self.log_file.flush()



    # TIME DISPLAY







    # =========================================================







    def update_time_display(self):







        now = datetime.now(



            self.ist_timezone



        )







        current_time = now.strftime(



            "%H:%M:%S"



        )







        self.current_time_label.setText(



            f"CURRENT: {current_time} IST"



        )







        if self.last_data_time is not None:







            last_time = self.last_data_time.strftime(



                "%H:%M:%S"



            )







            self.last_data_label.setText(



                f"LAST DATA: {last_time} IST"



            )















    # =========================================================







    # SERIAL ERROR







    # =========================================================















    def handle_serial_error(







        self,







        error







    ):















        self.serial_monitor.appendPlainText(







            f"SERIAL ERROR: {error}"







        )















        self.connection_status.setText(







            "● ERROR"







        )















        self.connection_status.setStyleSheet(







            "color: red; font-weight: bold;"







        )















    # =========================================================







    # DISCONNECT







    # =========================================================















    def disconnect_serial(self):















        # -----------------------------------------------------







        # Stop worker







        # -----------------------------------------------------















        if self.serial_worker is not None:















            self.serial_worker.stop()















        # -----------------------------------------------------







        # Stop thread







        # -----------------------------------------------------















        if self.serial_thread is not None:















            self.serial_thread.quit()















            self.serial_thread.wait()















        # -----------------------------------------------------







        # Clear references







        # -----------------------------------------------------















        self.serial_worker = None







        self.serial_thread = None















        # -----------------------------------------------------







        # Update GUI







        # -----------------------------------------------------















        self.connection_status.setText(







            "● DISCONNECTED"







        )















        self.connection_status.setStyleSheet(







            "color: red; font-weight: bold;"







        )















        self.connect_button.setText(







            "CONNECT"







        )















        self.port_combo.setEnabled(







            True







        )















        self.baud_combo.setEnabled(







            True







        )















        self.refresh_button.setEnabled(







            True







        )















        self.serial_monitor.appendPlainText(







            "Disconnected"







        )















    # =========================================================







    # CLOSE APPLICATION







    # =========================================================















    def closeEvent(







        self,







        event







    ):















        if getattr(self, "image_log_file", None) is not None:
            self.image_log_file.flush()
            self.image_log_file.close()
            self.image_log_file = None

        if getattr(self, "log_file", None) is not None:
            self.log_file.flush()
            self.log_file.close()
            self.log_file = None

        if self.serial_worker is not None:















            self.serial_worker.stop()















        if self.serial_thread is not None:















            self.serial_thread.quit()















            self.serial_thread.wait()















        if hasattr(self, "log_file") and not self.log_file.closed:

            self.log_file.flush()

            self.log_file.close()



        event.accept()























# =============================================================







# APPLICATION ENTRY POINT







# =============================================================















if __name__ == "__main__":















    app = QApplication(







        sys.argv







    )















    window = MainWindow()















    window.show()















    sys.exit(







        app.exec()







    )