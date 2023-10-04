from serial import Serial
from serial.tools import list_ports
from serial.tools.list_ports_common import ListPortInfo


class CCSerial:

    @staticmethod
    def get_devices() -> list[ListPortInfo]:
        """
        List CharaChorder serial devices
        :returns: List of CharaChorder serial devices
        """
        return list(filter(lambda p: p.manufacturer == "CharaChorder", list_ports.comports()))

    @staticmethod
    def get_device_id(device: str) -> str:
        """
        Get CharaChorder device ID
        :param device: Device path
        :raises IOError: If serial response is invalid
        :returns: Device ID
        """
        ser: Serial = Serial(device, 115200, timeout=1)
        ser.write(b"ID\r\n")
        res = ser.readline().decode("utf-8").strip().split(" ")
        ser.close()
        if len(res) != 2 or res[0] != "ID":
            raise IOError(f"Invalid response: {res}")
        return res[1]

    @staticmethod
    def get_device_version(device: str) -> str:
        """
        Get CharaChorder device version
        :param device: Device path
        :raises IOError: If serial response is invalid
        :returns: Device version
        """
        ser: Serial = Serial(device, 115200, timeout=1)
        ser.write(b"VERSION\r\n")
        res = ser.readline().decode("utf-8").strip().split(" ")
        ser.close()
        if len(res) != 2 or res[0] != "VERSION":
            raise IOError(f"Invalid response: {res}")
        return res[1]

    @staticmethod
    def get_chordmap_count(device: str) -> int:
        """
        Get CharaChorder device chordmap count
        :param device: Device path
        :raises IOError: If serial response is invalid
        :returns: Chordmap count
        """
        ser: Serial = Serial(device, 115200, timeout=1)
        ser.write(b"CML C0\r\n")
        res = ser.readline().decode("utf-8").strip().split(" ")
        ser.close()
        if len(res) != 3 or res[0] != "CML" or res[1] != "C0":
            raise IOError(f"Invalid response: {res}")
        return int(res[2])

    @staticmethod
    def get_chordmap_by_index(device: str, index: int) -> (str, str):
        """
        Get chordmap from CharaChorder device by index
        :param device: Device path
        :param index: Chordmap index
        :raises ValueError: If index is out of range
        :raises IOError: If serial response is invalid
        :returns: Chord (hex), Chordmap (Hexadecimal CCActionCodes List)
        """
        if index < 0 or index >= CCSerial.get_chordmap_count(device):
            raise ValueError("Index out of range")
        ser: Serial = Serial(device, 115200, timeout=1)
        ser.write(f"CML C1 {index}\r\n".encode("utf-8"))
        res = ser.readline().decode("utf-8").strip().split(" ")
        ser.close()
        if len(res) != 6 or res[0] != "CML" or res[1] != "C1" or res[2] != str(index) or res[3] == "0" or res[4] == "0":
            raise IOError(f"Invalid response: {res}")
        return res[3], res[4]

    @staticmethod
    def get_chordmap_by_chord(device: str, chord: str) -> str | None:
        """
        Get chordmap from CharaChorder device by chord
        :param device: Device path
        :param chord: Chord (hex)
        :raises ValueError: If chord is not a hex string
        :raises IOError: If serial response is invalid
        :returns: Chordmap (Hexadecimal CCActionCodes List), or None if chord was not found on device
        """
        try:
            int(chord, 16)
        except ValueError:
            raise ValueError("Chord must be a hex string")
        ser: Serial = Serial(device, 115200, timeout=1)
        ser.write(f"CML C2 {chord}\r\n".encode("utf-8"))
        res = ser.readline().decode("utf-8").strip().split(" ")
        ser.close()
        if len(res) != 4 or res[0] != "CML" or res[1] != "C2" or res[2] != chord:
            raise IOError(f"Invalid response: {res}")
        return res[3] if res[3] != "0" else None

    @staticmethod
    def set_chordmap_by_chord(device: str, chord: str, chordmap: str) -> bool:
        """
        Set chordmap on CharaChorder device by chord
        :param device: Device path
        :param chord: Chord (hex)
        :param chordmap: Chordmap (Hexadecimal CCActionCodes List)
        :raises ValueError: If chord or chordmap is not a hex string
        :raises IOError: If serial response is invalid
        :returns: Whether the chord was set successfully
        """
        try:
            int(chord, 16)
        except ValueError:
            raise ValueError("Chord must be a hex string")
        try:
            int(chordmap, 16)
        except ValueError:
            raise ValueError("Chordmap must be a hex string")
        ser: Serial = Serial(device, 115200, timeout=1)
        ser.write(f"CML C3 {chord}\r\n".encode("utf-8"))
        res = ser.readline().decode("utf-8").strip().split(" ")
        ser.close()
        if len(res) != 5 or res[0] != "CML" or res[1] != "C3" or res[2] != chord:
            raise IOError(f"Invalid response: {res}")
        return res[4] == "0"

    @staticmethod
    def del_chordmap_by_chord(device: str, chord: str) -> bool:
        """
        Delete chordmap from CharaChorder device by chord
        :param device: Device path
        :param chord: Chord (hex)
        :raises ValueError: If chord is not a hex string
        :raises IOError: If serial response is invalid
        :returns: False if the chord was not found on the device or was not deleted, True otherwise
        """
        try:
            int(chord, 16)
        except ValueError:
            raise ValueError("Chord must be a hex string")
        ser: Serial = Serial(device, 115200, timeout=1)
        ser.write(f"CML C4 {chord}\r\n".encode("utf-8"))
        res = ser.readline().decode("utf-8").strip().split(" ")
        ser.close()
        if len(res) != 4 or res[0] != "CML" or res[1] != "C4":
            raise IOError(f"Invalid response: {res}")
        return res[3] == "0"

    @staticmethod
    def decode_ascii_cc_action_code(code: int) -> str:
        """
        Decode CharaChorder action code
        :param code: integer action code
        :return: character corresponding to decoded action code
        :note: only decodes ASCII characters for now (32-126)
        """
        if 32 <= code <= 126:
            return chr(code)
        else:
            raise NotImplementedError(f"Action code {code} ({hex(code)}) not supported yet")

    @staticmethod
    def list_device_chords(device: str) -> list[str]:
        """
        List all chord(map)s on CharaChorder device
        :return: list of chordmaps
        """
        num_chords = CCSerial.get_chordmap_count(device)
        chordmaps = []
        for i in range(num_chords):
            chord_hex = CCSerial.get_chordmap_by_index(device, i)[1]
            chord_int = [int(chord_hex[i:i + 2], 16) for i in range(0, len(chord_hex), 2)]
            chord_utf8 = []
            for i, c in enumerate(chord_int):
                if c < 32:  # 10-bit scan code
                    chord_int[i + 1] = (chord_int[i] << 8) | chord_int[i + 1]
                elif c == 298 and len(chord_utf8) > 0:  # backspace
                    chord_utf8.pop()
                elif c == 544:  # spaceright
                    chord_utf8.append(" ")
                elif c > 126:  # TODO: support non-ASCII characters
                    continue
                else:
                    chord_utf8.append(chr(c))
            chordmaps.append("".join(chord_utf8).strip())
        return chordmaps


if __name__ == '__main__':
    cc = CCSerial()
    dev = cc.get_devices()[0][0]
    chords = cc.list_device_chords(dev)
    print(chords)
