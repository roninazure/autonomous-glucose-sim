"""CGM trace loader for retrospective replay.

Accepts two formats:
  1. Simple two-column CSV  — ``timestamp_min,glucose_mgdl`` (header required)
  2. Dexcom G6/G7 export   — detected by the presence of a
     ``Glucose Value (mg/dL)`` column; timestamps are parsed and converted to
     relative minutes from the first EGV reading.

Parsing is intentionally lenient (skips blank lines, tolerates whitespace) so
that pasted text-area input and file uploads both work without pre-processing.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CgmReading:
    timestamp_min: int
    glucose_mgdl: float


class CgmParseError(ValueError):
    """Raised when the input cannot be parsed as a valid CGM trace."""


# ── Public API ────────────────────────────────────────────────────────────────

def parse_cgm_text(text: str) -> list[CgmReading]:
    """Parse a CGM trace from a string (file contents or pasted text).

    Auto-detects Dexcom vs simple format. Returns readings sorted by
    timestamp, deduplicated, and validated.

    Raises:
        CgmParseError: if the text cannot be parsed or fails validation.
    """
    text = text.strip()
    if not text:
        raise CgmParseError("Input is empty.")

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        raise CgmParseError("No non-blank lines found.")

    header = lines[0].lower()
    if "glucose value" in header or "event type" in header:
        readings = _parse_dexcom(lines)
    else:
        readings = _parse_simple(lines)

    _validate(readings)
    return readings


def readings_to_csv(readings: list[CgmReading]) -> str:
    """Serialise readings back to simple CSV format (for download/export)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["timestamp_min", "glucose_mgdl"])
    for r in readings:
        writer.writerow([r.timestamp_min, round(r.glucose_mgdl, 1)])
    return buf.getvalue()


# ── Simple format parser ──────────────────────────────────────────────────────

def _parse_simple(lines: list[str]) -> list[CgmReading]:
    """Parse timestamp_min,glucose_mgdl rows.

    The first row is consumed as a header and skipped if it contains any
    non-numeric token in the first column.
    """
    readings: list[CgmReading] = []
    start = 0

    # Skip header row if first column is non-numeric
    first_col = lines[0].split(",")[0].strip()
    if not _is_numeric(first_col):
        start = 1

    for lineno, line in enumerate(lines[start:], start=start + 1):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            raise CgmParseError(
                f"Line {lineno}: expected 'timestamp_min,glucose_mgdl', got: {line!r}"
            )
        try:
            ts = int(float(parts[0]))
            glucose = float(parts[1])
        except ValueError:
            raise CgmParseError(
                f"Line {lineno}: cannot parse numbers from: {line!r}"
            )
        readings.append(CgmReading(timestamp_min=ts, glucose_mgdl=glucose))

    return readings


# ── Dexcom format parser ──────────────────────────────────────────────────────

_DEXCOM_TIMESTAMP_FMTS = [
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%y %H:%M:%S",
]

_DEXCOM_GLUCOSE_COLS = [
    "glucose value (mg/dl)",
    "glucose value (mmol/l)",
    "egv",
]

_DEXCOM_TIMESTAMP_COLS = [
    "timestamp (yyyy-mm-dd hh:mm:ss)",
    "timestamp",
    "time",
]


def _parse_dexcom(lines: list[str]) -> list[CgmReading]:
    """Parse a Dexcom Clarity / G6 / G7 export CSV."""
    reader = csv.DictReader(lines)
    headers_lower = {h.strip().lower(): h for h in (reader.fieldnames or [])}

    # Find glucose column
    glucose_col = next(
        (headers_lower[k] for k in _DEXCOM_GLUCOSE_COLS if k in headers_lower), None
    )
    if glucose_col is None:
        raise CgmParseError(
            "Dexcom format: no glucose value column found. "
            f"Expected one of {_DEXCOM_GLUCOSE_COLS}. "
            f"Got columns: {list(headers_lower.keys())}"
        )

    # Find timestamp column
    ts_col = next(
        (headers_lower[k] for k in _DEXCOM_TIMESTAMP_COLS if k in headers_lower), None
    )
    if ts_col is None:
        raise CgmParseError(
            "Dexcom format: no timestamp column found. "
            f"Expected one of {_DEXCOM_TIMESTAMP_COLS}."
        )

    # Is this mmol/L?
    is_mmol = "mmol" in glucose_col.lower()

    raw_rows: list[tuple[datetime, float]] = []
    for row in reader:
        # Skip non-EGV rows if Event Type column present
        event_col = headers_lower.get("event type", "")
        if event_col and row.get(event_col, "").strip().lower() not in ("egv", ""):
            continue

        glucose_str = row[glucose_col].strip()
        ts_str = row[ts_col].strip()
        if not glucose_str or not ts_str or glucose_str.lower() in ("low", "high", ""):
            continue

        try:
            glucose = float(glucose_str)
        except ValueError:
            continue

        if is_mmol:
            glucose = glucose * 18.0  # convert to mg/dL

        dt = _parse_dt(ts_str)
        if dt is None:
            continue
        raw_rows.append((dt, glucose))

    if not raw_rows:
        raise CgmParseError("Dexcom parse: no valid EGV rows found.")

    raw_rows.sort(key=lambda x: x[0])
    t0 = raw_rows[0][0]

    readings: list[CgmReading] = []
    for dt, glucose in raw_rows:
        delta = dt - t0
        minutes = int(delta.total_seconds() / 60)
        readings.append(CgmReading(timestamp_min=minutes, glucose_mgdl=round(glucose, 1)))

    return readings


def _parse_dt(s: str) -> datetime | None:
    for fmt in _DEXCOM_TIMESTAMP_FMTS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# ── Validation ────────────────────────────────────────────────────────────────

_MIN_READINGS = 6       # at least 5-step intervals for the history window
_MAX_STEP_MIN = 30      # flag if gaps are suspiciously large
_MIN_GLUCOSE = 20.0
_MAX_GLUCOSE = 600.0


def _validate(readings: list[CgmReading]) -> None:
    if len(readings) < _MIN_READINGS:
        raise CgmParseError(
            f"Trace too short: {len(readings)} readings, minimum {_MIN_READINGS} required."
        )

    # Sort and check for monotone timestamps
    readings.sort(key=lambda r: r.timestamp_min)
    timestamps = [r.timestamp_min for r in readings]
    if len(set(timestamps)) < len(timestamps):
        raise CgmParseError("Duplicate timestamps found in CGM trace.")

    for r in readings:
        if not (_MIN_GLUCOSE <= r.glucose_mgdl <= _MAX_GLUCOSE):
            raise CgmParseError(
                f"Glucose value {r.glucose_mgdl} mg/dL at t={r.timestamp_min} is out of "
                f"physiological range [{_MIN_GLUCOSE}, {_MAX_GLUCOSE}] mg/dL."
            )

    # Warn (via exception) if any single gap is huge
    for prev, curr in zip(readings[:-1], readings[1:]):
        gap = curr.timestamp_min - prev.timestamp_min
        if gap <= 0:
            raise CgmParseError(
                f"Non-monotone timestamps: t={prev.timestamp_min} followed by t={curr.timestamp_min}."
            )
        if gap > _MAX_STEP_MIN:
            raise CgmParseError(
                f"Gap of {gap} minutes between t={prev.timestamp_min} and "
                f"t={curr.timestamp_min} exceeds maximum allowed {_MAX_STEP_MIN} min. "
                f"Resample to ≤{_MAX_STEP_MIN}-minute intervals before upload."
            )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_numeric(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False
