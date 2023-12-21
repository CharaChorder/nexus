__all__ = [
    "NexusException",
    "UnknownDevice",
]


class NexusException(Exception):
    """Base exception class for Nexus"""


class UnknownDevice(NexusException):
    """An exception raised when an unknown device was loaded as a CharaChorder device"""

    def __init__(self, device):
        super().__init__(f'Device "{device}" cannot be parsed as a CharaChorder device')
