from typing import Self


class Version:
    major: int
    minor: int
    patch: int

    def __init__(self, version: int | str):
        if isinstance(version, int):
            self.major = version >> 16
            self.minor = version >> 8 & 0xFF
            self.patch = version & 0xFF
        else:
            self.major, self.minor, self.patch = map(int, version.split("."))

    def __int__(self):
        return self.major << 16 | self.minor << 8 | self.patch

    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}"

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other: Self | str | int):
        if isinstance(other, str):
            other = Version(other)
        return int(self) == int(other)

    def __gt__(self, other: Self | str | int):
        if isinstance(other, str):
            other = Version(other)
        return int(self) > int(other)

    def __lt__(self, other: Self | str | int):
        if isinstance(other, str):
            other = Version(other)
        return int(self) < int(other)
