from datetime import date
from app.utils.date_parser import parse_date_range

ref = date(2026, 10, 7)

tests = [
    "I need a room for two guests from November 21 to November 25",
    "I need a room for two guests from January 10 to January 15",
    "I need a room for two guests from November 21 2027 to November 25 2027",
    "I need a room for two guests from November 21 2030 to November 25 2030",
    "I need a room for two guests from December 28 2027 to January 3 2028",
    "I need a room for two guests from February 28 2028 to March 2 2028",
    "I need a room for two guests from February 29 2027 to March 2 2027",
    "I need a room for two guests from November 25 to November 21",
    "I need a room for two guests from November 21 2030 to November 25 2030",
]

for i, t in enumerate(tests, 1):
    res = parse_date_range(t, ref)
    print(f"Test {i}: {t}")
    print(f"  Result: {res}\n")
