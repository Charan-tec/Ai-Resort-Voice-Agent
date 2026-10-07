from datetime import date
from app.utils.date_parser import parse_date_range

ref = date(2026, 10, 7)

tests = [
    "from November 21 to 25 2030",
    "from November 21 2030 to 25",
    "from November 21 2030 to 25 2030",
    "from November 21 to November 25 2035",
    "from November 21 2035 to November 25",
    "from 21st to 25th of November 2030",
]

for t in tests:
    print(f"'{t}' -> {parse_date_range(t, ref)}")
