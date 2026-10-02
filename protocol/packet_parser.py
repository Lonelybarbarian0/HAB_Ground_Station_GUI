class PacketParser:

    HEADER_1 = 0x55
    HEADER_2 = 0xAA

    def __init__(self):

        # Persistent buffer.
        # Data can arrive in any number of chunks.
        self.buffer = bytearray()

    def feed(self, data):

        """
        Feed raw UART bytes into the parser.

        Returns:
            list of complete payloads
        """

        packets = []

        # Add newly received bytes
        self.buffer.extend(data)

        while True:

            # -------------------------------------------------
            # Find packet header: 55 AA
            # -------------------------------------------------

            header_index = self.find_header()

            if header_index is None:

                # No complete header yet.
                # Keep the final byte because it could be 0x55
                # belonging to the next header.
                if self.buffer and self.buffer[-1] == self.HEADER_1:

                    self.buffer = bytearray(
                        [self.buffer[-1]]
                    )

                else:

                    self.buffer.clear()

                break

            # -------------------------------------------------
            # Remove garbage before header
            # -------------------------------------------------

            if header_index > 0:

                del self.buffer[
                    :header_index
                ]

            # -------------------------------------------------
            # Need at least:
            #
            # 55 AA LEN
            # -------------------------------------------------

            if len(self.buffer) < 3:

                break

            # -------------------------------------------------
            # Payload length
            # -------------------------------------------------

            payload_length = self.buffer[2]

            # -------------------------------------------------
            # Complete packet size
            #
            # 2 bytes header
            # + 1 byte length
            # + payload
            # -------------------------------------------------

            total_length = 3 + payload_length

            # Wait for remaining bytes
            if len(self.buffer) < total_length:

                break

            # -------------------------------------------------
            # Extract complete packet
            # -------------------------------------------------

            payload = bytes(
                self.buffer[
                    3:total_length
                ]
            )

            packets.append(payload)

            # -------------------------------------------------
            # Remove processed packet
            # -------------------------------------------------

            del self.buffer[
                :total_length
            ]

        return packets

    def find_header(self):

        """
        Find the first occurrence of 55 AA.
        """

        for i in range(
            len(self.buffer) - 1
        ):

            if (
                self.buffer[i] == self.HEADER_1
                and
                self.buffer[i + 1] == self.HEADER_2
            ):

                return i

        return None