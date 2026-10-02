import struct


class TelemetryDecoder:

    BEACON_LENGTH = 52
    BEACON_FLAG = 0x7E

    def decode(self, packet):

        # -----------------------------------------------------
        # Basic validation
        # -----------------------------------------------------

        if len(packet) != self.BEACON_LENGTH:
            return None

        # -----------------------------------------------------
        # Check beacon flags
        # -----------------------------------------------------

        if packet[0] != self.BEACON_FLAG:
            return None

        if packet[51] != self.BEACON_FLAG:
            return None

        # -----------------------------------------------------
        # Decode telemetry
        #
        # All multi-byte telemetry values are BIG ENDIAN
        # because the STM32 explicitly sends MSB first.
        # -----------------------------------------------------

        time = struct.unpack(
            ">I",
            packet[17:21]
        )[0]

        altitude = struct.unpack(
            ">i",
            packet[21:25]
        )[0]

        latitude = struct.unpack(
            ">i",
            packet[25:29]
        )[0]

        longitude = struct.unpack(
            ">i",
            packet[29:33]
        )[0]

        rssi = struct.unpack(
            ">h",
            packet[33:35]
        )[0]

        temperature = struct.unpack(
            ">b",
            packet[35:36]
        )[0]

        battery_raw = packet[36]

        heater_status = packet[37]

        pitch = struct.unpack(
            ">h",
            packet[38:40]
        )[0]

        roll = struct.unpack(
            ">h",
            packet[40:42]
        )[0]

        yaw_rate = struct.unpack(
            ">h",
            packet[42:44]
        )[0]

        speed = struct.unpack(
            ">b",
            packet[44:45]
        )[0]

        pressure = struct.unpack(
            ">i",
            packet[45:49]
        )[0]

        # -----------------------------------------------------
        # Apply scaling
        # -----------------------------------------------------

        latitude_deg = latitude / 1_000_000.0

        longitude_deg = longitude / 1_000_000.0

        # Your current firmware stores the RSSI directly.
        # Keep the raw value for now.
        rssi_dbm = rssi

        # Battery is V * 10 according to your telemetry
        # definition.
        battery_voltage = battery_raw / 10.0

        # -----------------------------------------------------
        # Error / invalid sensor values
        # -----------------------------------------------------

        if temperature == -1:
            temperature_value = None
        else:
            temperature_value = temperature

        if pressure == -1:
            pressure_value = None
        else:
            pressure_value = pressure

        if pitch == -1:
            pitch_value = None
        else:
            pitch_value = pitch

        if roll == -1:
            roll_value = None
        else:
            roll_value = roll

        if yaw_rate == -1:
            yaw_rate_value = None
        else:
            yaw_rate_value = yaw_rate

        # -----------------------------------------------------
        # Return telemetry dictionary
        # -----------------------------------------------------

        return {
            "time": time,
            "altitude": altitude,
            "latitude": latitude_deg,
            "longitude": longitude_deg,
            "rssi": rssi_dbm,
            "temperature": temperature_value,
            "battery": battery_voltage,
            "heater": heater_status,
            "pitch": pitch_value,
            "roll": roll_value,
            "yaw_rate": yaw_rate_value,
            "speed": speed,
            "pressure": pressure / 100.0,
        }