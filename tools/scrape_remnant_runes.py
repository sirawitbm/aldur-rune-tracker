"""One-off scraper: pulls Grand Expedition Remnant rune name+icon pairs
from poe2db.tw individual item pages (e.g. poe2db.tw/us/Soul_Rune) and
writes data/rune_icon_seed.json + downloads their icons to
data/seed_icons/*.webp.

This is a *seed* for src/icon_db.py's IconLibrary, not a live dependency -
the app's runtime image-matching doesn't call poe2db at all. Re-run this
if GGG adds more Remnant rune types (extend CANDIDATE_SUFFIXES below;
found by inspecting the "RemnantRune*"/"RemnantRareRune*" icon filenames
referenced in poe2db's related-items sidebar on any one rune's page).
"""
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "data" / "rune_icon_seed.json"
ICONS_DIR = ROOT / "data" / "seed_icons"

CANDIDATE_SUFFIXES = [
    "Electrocuting", "Cyclonic", "Arcane", "Vision", "Rebirth", "Lightning",
    "Prismatic", "Wisdom", "Celestial", "Momentum", "Tempest",
    "Opulent", "Tidal", "Adaptive", "Fire", "Cold", "Protective",
    "Moon", "Stone", "Bloodletting", "Rage", "Gasp", "Toxic",
    # "Rare" tier (icon-name prefix only, display name has no "Rare" in it)
    "Power", "Soul", "Sky", "Death", "Oath", "Bond", "Ward", "Time", "Life", "Earth",
    # NOT "Bait" - poe2db lists a "Bait Rune" page but it shares Power
    # Rune's icon verbatim and has never actually been seen in-game;
    # treating this as a poe2db data error and excluding it rather than
    # adding a bogus 34th entry that would just collide with Power Rune.
    # Note: the icon *alt text* for a couple of these ("RemnantRuneEnrage",
    # "RemnantRuneGasp") doesn't match their actual page slug ("Rage_Rune",
    # "Volcanic_Rune") - found by inspecting each icon's actual <a href>
    # in poe2db's sidebar rather than guessing from the alt text alone.
    # Cross-checked against 4 different rune pages' sidebars and this list
    # of 33 was exhaustive across all of them (34 unique icons per page
    # including the league banner) - but if GGG adds more, the same
    # cross-checking approach applies.
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# A few pages' display name doesn't match their icon's internal codename at
# all (not just a suffix mismatch the automatic fallback can handle) -
# found by grepping the icon's actual alt text in another page's sidebar.
ICON_URL_OVERRIDES = {
    "Volcanic Rune": "https://cdn.poe2db.tw/image/Art/2DArt/UIImages/InGame/Expedition/Remnant/RemnantRuneGasp.webp",
}


def fetch(url: str, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception:
            time.sleep(1.0 * (attempt + 1))
    return None


def download(url: str, dest: Path, retries: int = 3):
    if dest.exists():
        return
    headers = {**HEADERS, "Referer": "https://poe2db.tw/"}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                dest.write_bytes(resp.read())
            return
        except Exception:
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"failed to download {url}")


def parse_rune_page(html: str):
    title_m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    desc_m = re.search(r'<meta property="og:description" content="(.*?)"\s*/>', html, re.DOTALL)
    if not desc_m:
        return None

    # og:title is the wiki page's own title, which can be an internal/legacy
    # codename (e.g. the page "Gasp_Rune" actually displays as "Volcanic
    # Rune" in-game) - the FIRST {...} segment of og:description mirrors
    # the actual in-game tooltip text, so it's the authoritative name.
    segments = re.findall(r"\{([^{}]+)\}", desc_m.group(1))
    if not segments:
        return None
    name = segments[0].strip()
    if not name.endswith("Rune"):
        return None  # landed on an unrelated/disambiguation page

    wiki_title = title_m.group(1).strip() if title_m else None
    mods = [s.strip() for s in segments[1:] if s.strip() and "gain:" not in s.lower()]

    icon_m = re.search(r'<h5 class="card-header"><img loading="lazy" src="([^"]+)"', html)
    icon_url = icon_m.group(1) if icon_m else None
    if icon_url is None:
        # Some pages don't put the icon in the expected card-header -
        # fall back to the icon whose filename matches this page's own
        # wiki-title suffix (case-insensitive), then a manual override for
        # the cases where even the codename doesn't match (see above).
        if wiki_title:
            suffix = wiki_title.replace(" Rune", "").replace(" ", "")
            alt_m = re.search(
                rf'src="([^"]*RemnantR(?:are)?Rune{re.escape(suffix)}\.webp)"', html, re.IGNORECASE
            )
            icon_url = alt_m.group(1) if alt_m else None
        if icon_url is None:
            icon_url = ICON_URL_OVERRIDES.get(name)

    return {"name": name, "wiki_title": wiki_title, "mods": mods, "icon_url": icon_url}


def main():
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for suffix in CANDIDATE_SUFFIXES:
        url = f"https://poe2db.tw/us/{suffix}_Rune"
        html = fetch(url)
        if html is None:
            print(f"{suffix:15s} -> FETCH FAILED")
            continue
        parsed = parse_rune_page(html)
        if parsed is None or parsed["icon_url"] is None:
            print(f"{suffix:15s} -> NOT FOUND / no icon")
            continue

        icon_filename = f"{suffix.lower()}.webp"
        icon_path = ICONS_DIR / icon_filename
        try:
            download(parsed["icon_url"], icon_path)
            status = "ok"
        except Exception as exc:  # noqa: BLE001
            status = f"icon download failed: {exc}"

        results.append({
            "name": parsed["name"],
            "mods": parsed["mods"],
            "icon_file": f"seed_icons/{icon_filename}",
        })
        mismatch = " (wiki title differs!)" if parsed["wiki_title"] and parsed["wiki_title"] != parsed["name"] else ""
        print(f"{suffix:15s} -> {parsed['name']:25s} [{status}]{mismatch}")
        time.sleep(0.3)

    OUT_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote {len(results)} runes to {OUT_JSON}")


if __name__ == "__main__":
    main()
