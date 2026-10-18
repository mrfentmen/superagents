"""The sentry's lockwork: plain words -> a watch entry -> a merged conditions file.

Everything here is pure and offline-testable. Parsing is rules, not vibes:

    "watch air quality in Denver over 150"     -> air check, threshold 150,Denver
    "watch quakes over 4.5 within 120 km"      -> quakes check, needs a place
    "watch the river gauge at EADM7"           -> flood check, gauge EADM7 (over its stage)

The conditions file is the WHOLE contract with the watchd runtime in the sibling repo:
one JSON object the watcher loads unmodified. The sentry writes it, the watcher obeys it,
no private channel between them lives anywhere.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

KINDS = ("air", "quakes", "flood")
ROOMS = {"air": "air", "quakes": "quakes", "flood": "flood"}

_AIR = re.compile(r"\bair\b|\baqi\b|\bsmog\b|\bpm2[.,]?5\b|\bozone\b", re.I)
_QUAKES = re.compile(r"\bquake(?:s)?\b|\bearthquake(?:s)?\b|\bmagnitude\b|\bseismic\b", re.I)
_FLOOD = re.compile(r"\bflood(?:ing)?\b|\briver\b|\bgauge\b|\bstream\b|\bwater level\b", re.I)
_PLACE = re.compile(r"\b(?:in|at|near|around|of)\s+([A-Za-z][A-Za-z .'\-]{1,40}?)(?=\s*(?:over|above|below|under|within|,|\.|$|every))", re.I)
_OVER = re.compile(r"\b(?:over|above|past|beyond|more than)\s*(-?\d+(?:\.\d+)?)", re.I)
_UNDER = re.compile(r"\b(?:under|below|less than)\s*(-?\d+(?:\.\d+)?)", re.I)
_RADIUS = re.compile(r"\bwithin\s+(-?\d+(?:\.\d+)?)\s*(km|mi)\b", re.I)
_EVERY = re.compile(r"\bevery\s+(\d{1,4})\s*(min(?:ute)?s?|hour(?:s)?|sec(?:ond)?s?)\b", re.I)
_GAUGE_ID = re.compile(r"\bgauge\s+(?:at\s+)?([A-Za-z0-9]{4,15})\b", re.I)


def kind_of(text: str) -> str | None:
    if _AIR.search(text):
        return "air"
    if _QUAKES.search(text):
        return "quakes"
    if _FLOOD.search(text):
        return "flood"
    return None


def place_of(text: str) -> str | None:
    match = _PLACE.search(str(text or ""))
    if not match:
        return None
    clean = match.group(1).strip(" .,'\"").rstrip()
    if clean.lower() in {"me", "here", "us"}:
        return None
    return clean[:50]


def threshold_of(text: str) -> tuple[float, str] | None:
    """(number, direction) from over/under wording."""
    over, under = _OVER.search(text), _UNDER.search(text)
    if over:
        return float(over.group(1)), "above"
    if under:
        return float(under.group(1)), "below"
    return None


def radius_of(text: str) -> float | None:
    match = _RADIUS.search(str(text or ""))
    if not match:
        return None
    return float(match.group(1)) * (1.60934 if match.group(2) == "mi" else 1.0)


def gauge_of(text: str) -> str | None:
    """The flood watch obeys only an explicitly named gauge id (EADM7, MEMT1...).
    Guessing ids from stray capitalised words is how a wrong river gets watched."""
    match = _GAUGE_ID.search(str(text or ""))
    return match.group(1).upper() if match else None


def every_of(text: str, default: int = 300) -> int:
    match = _EVERY.search(str(text or ""))
    if not match:
        return default
    count, unit = int(match.group(1)), match.group(2).lower()
    if unit.startswith("sec"):
        return max(15, count)
    if unit.startswith("hour"):
        return count * 3600
    return count * 60


def slug(words: str) -> str:
    text = str(words or "watch").lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:48] or "watch"


def build_entry(text: str) -> dict:
    """Parse the order. ValueError tells the caller exactly what words were missing."""
    text = str(text or "").strip()
    kind = kind_of(text)
    if not kind:
        raise ValueError("tell me what to watch: air, quakes (earthquakes), or flood (a river gauge)")
    entry: dict = {"kind": kind}
    if kind == "air":
        place = place_of(text)
        if not place:
            raise ValueError("where do I watch the air? for example: watch air quality in Denver")
        entry["place"] = place
        thr = threshold_of(text)
        if not thr:
            raise ValueError("what number should trigger the yell? for example: ... over 150")
        entry["threshold"], entry["when"] = thr
    elif kind == "quakes":
        place = place_of(text)
        if not place:
            raise ValueError("where do I watch for quakes? a 'lat,lon' pair or a city name")
        entry["place"] = place
        radius = radius_of(text)
        if radius:
            entry["radius_km"] = round(radius, 1)
        thr = threshold_of(text)
        entry["magnitude"] = thr[0] if thr else 4.0
        entry["when"] = thr[1] if thr else "above"
    else:
        gauge = gauge_of(text)
        if not gauge:
            raise ValueError("which gauge? the flood watch needs a 5-character id like EADM7, "
                             "for example: watch the river gauge at EADM7")
        entry["gauge"] = gauge
        entry["when"] = "above"
    entry["every_s"] = every_of(text)
    entry["order"] = text[:200]
    if kind == "flood":
        label = entry["gauge"]  # gauge ids keep their own casing (EADM7, MEMT1)
    else:
        label = (place_of(text) or kind).title()
    entry["name"] = f"{kind}-{label}"
    return entry


def merge_into(existing: str, entry: dict, now: str) -> tuple[str, str]:
    """(json, changed) - same-named entries update in place; new ones append."""
    try:
        doc = json.loads(existing or "{}")
    except ValueError as exc:
        raise ValueError(f"the existing conditions file is not JSON: {exc}") from exc
    checks = [row for row in doc.setdefault("checks", []) if isinstance(row, dict)]
    doc["checks"] = checks
    doc.setdefault("notifiers", {"console": True})
    doc.setdefault("every_s", 120)
    doc["installed"] = now
    changed = "added"
    for i, row in enumerate(checks):
        if row.get("name") == entry["name"]:
            checks[i] = entry
            changed = "updated"
            break
    else:
        checks.append(entry)
    return json.dumps(doc, indent=2, default=str) + "\n", changed


def activation_lines(file_path: str, every_s: int) -> list[str]:
    """The whole operational contract, honest: the watcher obeys the file, cron or no cron."""
    minutes = max(1, every_s // 60)
    return [
        f"# one pass now:",
        f"python3 watchd.py --config {file_path} --once",
        "# continuous (this picket line):",
        f"python3 watchd.py --config {file_path} --loop",
        f"# cron-style, every {minutes} minute(s):",
        f"*/{minutes} * * * * cd <watchd-directory> && python3 watchd.py --config {file_path} --once",
    ]


def read_json(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "{}"
