import serial
import threading

from PySide6.QtCore import QObject, Signal, Slot


class SerialWorker(QObject):

    data_received = Signal(bytes)
    error_occurred = Signal(str)
    finished = Signal()

    def __init__(self, port, baudrate):

        super().__init__()

        self.port = port
        self.baudrate = baudrate

        self.serial = None
        self.running = False

        # Protect serial TX/RX access
        self.serial_lock = threading.Lock()

    @Slot()
    def start(self):

        try:

            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.1
            )

            self.running = True

            while self.running:

                if self.serial.in_waiting > 0:

                    with self.serial_lock:

                        data = self.serial.read(
                            self.serial.in_waiting
                        )

                    if data:

                        self.data_received.emit(
                            data
                        )

        except serial.SerialException as error:

            self.error_occurred.emit(
                str(error)
            )

        finally:

            if self.serial is not None:

                with self.serial_lock:

                    self.serial.close()

                self.serial = None

            self.running = False

            self.finished.emit()

    def write_data(self, data):

        if self.serial is None:
            return False

        try:

            with self.serial_lock:

                self.serial.write(data)

                self.serial.flush()

            return True

        except serial.SerialException as error:

            self.error_occurred.emit(
                str(error)
            )

            return False

    @Slot()
    def stop(self):

        self.running = False