import json
import requests
from typing import Self

from nexus import __version__


class Version:
    major: int
    minor: int
    patch: int

    def __init__(self, version: int | str):
        """
        Initialize a Version object
        :param version: Version string in the form of "X.X.X" or an integer representing the version
        :raises ValueError: If the version received is invalid
        """
        if isinstance(version, int):
            self.major = version >> 16
            self.minor = version >> 8 & 0xFF
            self.patch = version & 0xFF
        else:
            if not version.replace(".", "").isdigit():
                raise ValueError("Version string must be in the form of 'X.X.X'")
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
    def fetch_latest_nexus_version(cls) -> tuple[bool, Self | None]:
        """
        Fetch the latest release of Nexus from GitHub
        :returns: Tuple of an "outdated" boolean and the fetched version or None if the request failed
        """
        try:
            r = requests.get("https://api.github.com/repos/CharaChorder/nexus/releases/latest")
            response_dict = json.loads(r.text)

            # Ensure request succeeded and response contains a valid version
            if r.status_code != 200 or "tag_name" not in response_dict or not response_dict["tag_name"].startswith("v"):
                raise ValueError

            # Compare current version with fetched version
            current_version = cls(__version__)
            upstream_version = cls(response_dict["tag_name"][1:])
            return current_version < upstream_version, upstream_version
        except (ConnectionError, ValueError):  # Failsafe to outdated
            return True, None
