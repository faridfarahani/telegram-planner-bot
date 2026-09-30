from __future__ import annotations

DAYS = [
    ("sat", "شنبه"),
    ("sun", "یکشنبه"),
    ("mon", "دوشنبه"),
    ("tue", "سه‌شنبه"),
    ("wed", "چهارشنبه"),
    ("thu", "پنج‌شنبه"),
    ("fri", "جمعه"),
]

DAY_LABELS = dict(DAYS)

# Python weekday(): Monday=0 ... Sunday=6
PY_WEEKDAY_TO_CODE = {
    0: "mon",
    1: "tue",
    2: "wed",
    3: "thu",
    4: "fri",
    5: "sat",
    6: "sun",
}

REMINDER_PRESETS = {
    "a": ("15:00", "21:00"),
    "b": ("12:00", "18:00"),
    "c": ("17:00", "22:00"),
}

REMINDER_LABELS = {
    "a": "15:00 و 21:00",
    "b": "12:00 و 18:00",
    "c": "17:00 و 22:00",
}
