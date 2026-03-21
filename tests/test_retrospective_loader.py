"""Tests for the CGM trace loader."""
from __future__ import annotations

import pytest

from ags.retrospective.loader import CgmParseError, CgmReading, parse_cgm_text, readings_to_csv


# ── Simple CSV format ─────────────────────────────────────────────────────────

_SIMPLE_CSV = """\
timestamp_min,glucose_mgdl
0,110
5,115
10,122
15,130
20,138
25,142
"""

def test_simple_csv_parses():
    readings = parse_cgm_text(_SIMPLE_CSV)
    assert len(readings) == 6


def test_simple_csv_values():
    readings = parse_cgm_text(_SIMPLE_CSV)
    assert readings[0] == CgmReading(timestamp_min=0, glucose_mgdl=110.0)
    assert readings[2] == CgmReading(timestamp_min=10, glucose_mgdl=122.0)


def test_simple_csv_no_header():
    """Rows-only input (no header) should still parse."""
    text = "\n".join(f"{t},{g}" for t, g in [(0,110),(5,115),(10,120),(15,125),(20,130),(25,135)])
    readings = parse_cgm_text(text)
    assert len(readings) == 6


def test_simple_csv_float_timestamps():
    text = "timestamp_min,glucose_mgdl\n0.0,110\n5.0,115\n10.0,120\n15.0,125\n20.0,130\n25.0,135"
    readings = parse_cgm_text(text)
    assert readings[0].timestamp_min == 0


def test_simple_csv_extra_whitespace():
    text = "timestamp_min , glucose_mgdl\n 0 , 110 \n 5 , 115 \n10,120\n15,125\n20,130\n25,135"
    readings = parse_cgm_text(text)
    assert len(readings) == 6


# ── Dexcom G6 format ──────────────────────────────────────────────────────────

_DEXCOM_CSV = """\
Index,Timestamp (YYYY-MM-DD HH:MM:SS),Event Type,Event Subtype,Patient Info,Device Info,Source Device ID,Glucose Value (mg/dL),Insulin Value (u),Carb Value (grams),Duration (hh:mm:ss),Glucose Rate of Change (mg/dL/min),Transmitter Time (Long Integer),Transmitter ID
1,2024-01-15 08:00:00,EGV,,,,DevA,110,,,,,,TX1
2,2024-01-15 08:05:00,EGV,,,,DevA,115,,,,,,TX1
3,2024-01-15 08:10:00,EGV,,,,DevA,122,,,,,,TX1
4,2024-01-15 08:15:00,EGV,,,,DevA,130,,,,,,TX1
5,2024-01-15 08:20:00,EGV,,,,DevA,138,,,,,,TX1
6,2024-01-15 08:25:00,EGV,,,,DevA,142,,,,,,TX1
"""

def test_dexcom_format_detected():
    readings = parse_cgm_text(_DEXCOM_CSV)
    assert len(readings) == 6


def test_dexcom_timestamps_relative():
    readings = parse_cgm_text(_DEXCOM_CSV)
    assert readings[0].timestamp_min == 0
    assert readings[1].timestamp_min == 5
    assert readings[-1].timestamp_min == 25


def test_dexcom_glucose_values():
    readings = parse_cgm_text(_DEXCOM_CSV)
    assert readings[0].glucose_mgdl == 110.0
    assert readings[2].glucose_mgdl == 122.0


def test_dexcom_non_egv_rows_skipped():
    """Calibration and insulin rows must be excluded."""
    text = """\
Index,Timestamp (YYYY-MM-DD HH:MM:SS),Event Type,Event Subtype,Patient Info,Device Info,Source Device ID,Glucose Value (mg/dL)
1,2024-01-15 08:00:00,EGV,,,,,110
2,2024-01-15 08:00:00,Calibration,,,,,115
3,2024-01-15 08:05:00,EGV,,,,,118
4,2024-01-15 08:10:00,EGV,,,,,122
5,2024-01-15 08:15:00,EGV,,,,,127
6,2024-01-15 08:20:00,EGV,,,,,132
7,2024-01-15 08:25:00,EGV,,,,,136
"""
    readings = parse_cgm_text(text)
    assert all(r.glucose_mgdl != 115.0 for r in readings)  # calibration row excluded


# ── Validation errors ─────────────────────────────────────────────────────────

def test_empty_input_raises():
    with pytest.raises(CgmParseError, match="empty"):
        parse_cgm_text("")


def test_too_few_readings_raises():
    text = "timestamp_min,glucose_mgdl\n0,110\n5,115"
    with pytest.raises(CgmParseError, match="too short"):
        parse_cgm_text(text)


def test_out_of_range_glucose_raises():
    text = "timestamp_min,glucose_mgdl\n0,110\n5,115\n10,122\n15,130\n20,138\n25,700"
    with pytest.raises(CgmParseError, match="physiological range"):
        parse_cgm_text(text)


def test_non_monotone_timestamps_are_sorted_and_accepted():
    """Out-of-order timestamps are sorted rather than rejected."""
    text = "timestamp_min,glucose_mgdl\n0,110\n10,115\n5,122\n15,130\n20,138\n25,142"
    readings = parse_cgm_text(text)
    # Should be sorted: 0, 5, 10, 15, 20, 25
    assert [r.timestamp_min for r in readings] == [0, 5, 10, 15, 20, 25]


def test_gap_too_large_raises():
    text = "timestamp_min,glucose_mgdl\n0,110\n5,115\n10,122\n15,130\n20,138\n55,142"
    with pytest.raises(CgmParseError, match="Gap"):
        parse_cgm_text(text)


def test_duplicate_timestamps_raises():
    text = "timestamp_min,glucose_mgdl\n0,110\n5,115\n5,122\n10,130\n15,138\n20,142"
    with pytest.raises(CgmParseError, match="Duplicate"):
        parse_cgm_text(text)


# ── Round-trip ────────────────────────────────────────────────────────────────

def test_readings_to_csv_round_trip():
    original = parse_cgm_text(_SIMPLE_CSV)
    csv_text = readings_to_csv(original)
    restored = parse_cgm_text(csv_text)
    assert len(restored) == len(original)
    for a, b in zip(original, restored):
        assert a.timestamp_min == b.timestamp_min
        assert abs(a.glucose_mgdl - b.glucose_mgdl) < 0.2
