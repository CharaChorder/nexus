from dataclasses import dataclass
from typing import Literal

from serial.tools import list_ports
from serial.tools.list_ports_common import ListPortInfo

from .errors import UnknownDevice


@dataclass
class CCDevice:
    name: str
    company: Literal["CharaChorder"]
    device: Literal["One", "Lite", "X", "Engine"]
    chipset: Literal["M0", "S2"]

    product_id: Literal[
        32783,  # One
        32796,  # Lite M0
        33070,  # Lite S2
        33163,  # X
    ]
    vendor_id: Literal[
        9114,  # Adafruit (M0)
        12346,  # Espressif (S2)
    ]

    port: str

    def __init__(self, device: ListPortInfo):
        self.company = "CharaChorder"

        if device.pid == 32783:
            self.device = "One"
        elif device.pid in (32796, 33070):
            self.device = "Lite"
        elif device.pid == 33163:
            self.device = "X"
        else:
            # FIXME: This would also be raised if a user has their own device
            # with the CC Engine with an unknown pid.
            raise UnknownDevice(device)
        self.product_id = device.pid  # type: ignore

        if device.vid == 9114:
            self.chipset = "M0"
        elif device.vid == 12346:
            self.chipset = "S2"
        else:
            raise UnknownDevice(device)
        self.vendor_id = device.vid

        self.name = f"{self.company} {self.device} {self.chipset}"

        self.port = device.device

    def __repr__(self):
        return f"{self.name} ({self.port})"

    def __str__(self):
        return f"{self.name} ({self.port})"

    @staticmethod
    def list_devices() -> list["CCDevice"]:
        return [CCDevice(device) for device in list_ports.comports()]
