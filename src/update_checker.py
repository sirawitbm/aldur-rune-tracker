import json
import re
import urllib.request
from dataclasses import dataclass

LATEST_RELEASE_API = "https://api.github.com/repos/sirawitbm/aldur-rune-tracker/releases/latest"
RELEASE_TAG_URL = "https://github.com/sirawitbm/aldur-rune-tracker/releases/tag/v{version}"


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    page_url: str


def parse_version(value: str) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value.strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())


def newer_release(payload: dict, current_version: str) -> ReleaseInfo | None:
    if payload.get("draft") or payload.get("prerelease"):
        return None

    tag = str(payload.get("tag_name", ""))
    latest = parse_version(tag)
    current = parse_version(current_version)
    if latest is None or current is None or latest <= current:
        return None
    version = tag.removeprefix("v")
    return ReleaseInfo(version=version, page_url=RELEASE_TAG_URL.format(version=version))


def fetch_newer_release(current_version: str, timeout_sec: float = 8) -> ReleaseInfo | None:
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "AldurRuneTracker-update-check",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_sec) as response:
        payload = json.load(response)
    return newer_release(payload, current_version)