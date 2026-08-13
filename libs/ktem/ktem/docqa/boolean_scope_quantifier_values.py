from __future__ import annotations


def _number_value(value: str) -> int:
    words = {
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
    }
    return words.get(value, int(value) if value.isdigit() else 0)
