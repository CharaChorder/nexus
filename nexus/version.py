import json
import urllib.request
from typing import Self

from nexus import __version__


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

    @classmethod
    def fetch_latest_nexus_version(cls) -> tuple[bool, Self]:
        """
        Fetch the latest release of Nexus from GitHub
        :returns: Tuple of an "outdated" boolean and the fetched version
        """
        with urllib.request.urlopen(
            "https://api.github.com/repos/CharaChorder/nexus/releases/latest"
        ) as response:
            response_dict = json.loads(response.read())

        current_version = cls(__version__)
        upstream_version = cls(response_dict["tag_name"][1:])
        return current_version < upstream_version, upstream_version
