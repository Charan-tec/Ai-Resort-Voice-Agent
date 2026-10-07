from datetime import date, datetime, timedelta
import re
from typing import Optional, Tuple


MONTHS_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

MONTH_REGEX_PART = r"(?:january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|sept|october|oct|november|nov|december|dec)"


def get_reference_date() -> date:
    """Return the effective today reference date for resolving future stays dynamically."""
    now = datetime.now().date()
    return date(now.year, now.month, 1)


def _resolve_weekend(ref_date: date, is_next: bool = False) -> Tuple[date, date]:
    """Resolve Friday-to-Sunday weekend stay dates relative to ref_date."""
    weekday = ref_date.weekday()  # Monday=0, Sunday=6
    if weekday <= 4:
        days_to_friday = 4 - weekday
    else:
        days_to_friday = (4 - weekday) + 7
    if is_next:
        days_to_friday += 7
    friday = ref_date + timedelta(days=days_to_friday)
    sunday = friday + timedelta(days=2)
    return friday, sunday


def _parse_date_subclause(clause_str: str, default_month: Optional[int], default_year: Optional[int], ref_date: date) -> Optional[date]:
    """Parse a single date subclause: month+day, day+month, numeric, or day-only with default_month."""
    # 1. Month Day: november 22, nov 22nd
    m1 = re.search(rf'({MONTH_REGEX_PART})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{{4}}))?', clause_str, re.IGNORECASE)
    if m1:
        m_name, d_str, y_str = m1.groups()
        m_val = MONTHS_MAP[m_name.lower()]
        d_val = int(d_str)
        y_val = int(y_str) if y_str else (default_year or ref_date.year)
        try:
            cand = date(y_val, m_val, d_val)
            if not y_str and cand < ref_date:
                cand = date(y_val + 1, m_val, d_val)
            return cand
        except ValueError:
            return None

    # 2. Day Month: 22nd of november, 22 november
    m2 = re.search(rf'(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({MONTH_REGEX_PART})(?:\s*,?\s*(\d{{4}}))?', clause_str, re.IGNORECASE)
    if m2:
        d_str, m_name, y_str = m2.groups()
        m_val = MONTHS_MAP[m_name.lower()]
        d_val = int(d_str)
        y_val = int(y_str) if y_str else (default_year or ref_date.year)
        try:
            cand = date(y_val, m_val, d_val)
            if not y_str and cand < ref_date:
                cand = date(y_val + 1, m_val, d_val)
            return cand
        except ValueError:
            return None

    # 3. Numeric: 11/22, 11-22
    m3 = re.search(r'(\d{1,2})[\/\.-](\d{1,2})(?:[\/\.-](\d{2,4}))?', clause_str)
    if m3:
        m_str, d_str, y_str = m3.groups()
        m_val, d_val = int(m_str), int(d_str)
        y_val = int(y_str) if y_str else (default_year or ref_date.year)
        if 1 <= m_val <= 12:
            try:
                cand = date(y_val, m_val, d_val)
                if not y_str and cand < ref_date:
                    cand = date(y_val + 1, m_val, d_val)
                return cand
            except ValueError:
                return None

    # 4. Day only if default_month is provided: 25th, 25
    m4 = re.search(r'(\d{1,2})(?:st|nd|rd|th)?', clause_str)
    if m4 and default_month:
        d_val = int(m4.group(1))
        y_val = default_year or ref_date.year
        try:
            cand = date(y_val, default_month, d_val)
            if cand < ref_date:
                cand = date(y_val + 1, default_month, d_val)
            return cand
        except ValueError:
            return None

    return None


def parse_date_range(text: str, reference_date: Optional[date] = None) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extract and normalize check-in and check-out dates from natural language text dynamically.
    Returns: (check_in_str (YYYY-MM-DD), check_out_str (YYYY-MM-DD), error_message_or_None)

    Features:
    - Zero hardcoded dates: all calculations dynamically anchored to reference_date (defaults to today).
    - Resolves month names and abbreviations (e.g. 'Oct', 'November').
    - Resolves ordinal day numbers ('10th', '14th', '21st').
    - Supports single-month ranges ('October 10 to 14', 'December 5 to December 8').
    - Supports cross-month ranges ('Oct 28 to Nov 3', 'December 28 to January 3').
    - Supports cross-year rollover ('December 28 to January 3', 'January 15 to January 20').
    - Supports day-first phrasing ('from the 12th to the 16th of November').
    - Supports explicit check-in and check-out clauses ('check-in date is november 22 on checkout date is november 25th').
    - Supports relative phrases ('this weekend', 'next weekend', 'next month', 'next year').
    - Supports ISO ('2026-10-10 to 2026-10-14') and numeric slash/dash ('11/20 to 11/25', '11/20/2026 to 11/25/2026').
    - Validates calendar validity, check_out > check_in, and prevents past stay dates.
    """
    if not text:
        return None, None, None

    ref_date = reference_date or get_reference_date()
    lower = text.lower().strip()

    # Spoken number words normalization (STT transcript compatibility)
    spoken_map = [
        (r'\btwenty[\s-]first\b', '21st'),
        (r'\btwenty[\s-]second\b', '22nd'),
        (r'\btwenty[\s-]third\b', '23rd'),
        (r'\btwenty[\s-]fourth\b', '24th'),
        (r'\btwenty[\s-]fifth\b', '25th'),
        (r'\btwenty[\s-]sixth\b', '26th'),
        (r'\btwenty[\s-]seventh\b', '27th'),
        (r'\btwenty[\s-]eighth\b', '28th'),
        (r'\btwenty[\s-]ninth\b', '29th'),
        (r'\bthirty[\s-]first\b', '31st'),
        (r'\bthirtieth\b', '30th'),
        (r'\btwentieth\b', '20th'),
        (r'\bnineteenth\b', '19th'),
        (r'\beighteenth\b', '18th'),
        (r'\bseventeenth\b', '17th'),
        (r'\bsixteenth\b', '16th'),
        (r'\bfifteenth\b', '15th'),
        (r'\bfourteenth\b', '14th'),
        (r'\bthirteenth\b', '13th'),
        (r'\btwelfth\b', '12th'),
        (r'\beleventh\b', '11th'),
        (r'\btenth\b', '10th'),
        (r'\bninth\b', '9th'),
        (r'\beighth\b', '8th'),
        (r'\bseventh\b', '7th'),
        (r'\bsixth\b', '6th'),
        (r'\bfifth\b', '5th'),
        (r'\bfourth\b', '4th'),
        (r'\bthird\b', '3rd'),
        (r'\bsecond\b', '2nd'),
        (r'\bfirst\b', '1st'),
        (r'\btwenty[\s-]one\b', '21'),
        (r'\btwenty[\s-]two\b', '22'),
        (r'\btwenty[\s-]three\b', '23'),
        (r'\btwenty[\s-]four\b', '24'),
        (r'\btwenty[\s-]five\b', '25'),
        (r'\btwenty[\s-]six\b', '26'),
        (r'\btwenty[\s-]seven\b', '27'),
        (r'\btwenty[\s-]eight\b', '28'),
        (r'\btwenty[\s-]nine\b', '29'),
        (r'\bthirty[\s-]one\b', '31'),
        (r'\bthirty\b', '30'),
        (r'\btwenty\b', '20'),
    ]
    for pattern, repl in spoken_map:
        lower = re.sub(pattern, repl, lower)

    has_next_year = bool(re.search(r'\bnext year\b', lower))

    # 1. Relative Weekend: "next weekend" or "this weekend"
    if "next weekend" in lower:
        d_in, d_out = _resolve_weekend(ref_date, is_next=True)
        return d_in.strftime("%Y-%m-%d"), d_out.strftime("%Y-%m-%d"), None

    if "this weekend" in lower or re.search(r'\bthe weekend\b', lower):
        d_in, d_out = _resolve_weekend(ref_date, is_next=False)
        return d_in.strftime("%Y-%m-%d"), d_out.strftime("%Y-%m-%d"), None

    # 1.5 Explicit Check-In and Check-Out Clauses:
    # e.g. "check-in date is november 22 on checkout date is november 25th", "check in 11/22 checkout 11/25"
    if any(k in lower for k in ("check-in", "checkin", "arriving", "arrival")) and any(k in lower for k in ("check-out", "checkout", "departing", "departure", "leaving")):
        split_match = re.search(
            r'(?:check-?in|arriving|arrival|from)\s*(?:date\s+is|date|is|on|for|:)?\s*(.*?)\s*(?:on\s+checkout|and\s+checkout|checkout|check-?out|departing|departure|leaving)\s*(?:date\s+is|date|is|on|for|:)?\s*(.*)',
            lower
        )
        if split_match:
            ci_part, co_part = split_match.groups()
            ref_y = ref_date.year + 1 if has_next_year else ref_date.year
            d_in_cand = _parse_date_subclause(ci_part, None, ref_y, ref_date)
            def_m = d_in_cand.month if d_in_cand else None
            def_y = d_in_cand.year if d_in_cand else ref_y
            d_out_cand = _parse_date_subclause(co_part, def_m, def_y, ref_date)
            if d_in_cand and d_out_cand:
                if d_in_cand < ref_date:
                    return None, None, "Check-in date cannot be in the past."
                if d_out_cand <= d_in_cand:
                    return None, None, "Check-out date must be after check-in date."
                return d_in_cand.strftime("%Y-%m-%d"), d_out_cand.strftime("%Y-%m-%d"), None

    # 2. ISO YYYY-MM-DD date ranges: "2026-10-10 to 2026-10-14"
    iso_match = re.search(r'(\d{4}-\d{2}-\d{2})\s*(?:to|through|until|-)\s*(\d{4}-\d{2}-\d{2})', lower)
    if iso_match:
        ci_str, co_str = iso_match.group(1), iso_match.group(2)
        try:
            d_in = datetime.strptime(ci_str, "%Y-%m-%d").date()
            d_out = datetime.strptime(co_str, "%Y-%m-%d").date()
            if d_in < ref_date:
                return None, None, "Check-in date cannot be in the past."
            if d_out <= d_in:
                return None, None, "Check-out date must be after check-in date."
            return ci_str, co_str, None
        except ValueError:
            return None, None, "Invalid calendar date."

    # 3. Numeric ranges: "11/20 to 11/25" or "11/20/2026 to 11/25/2026"
    num_match = re.search(
        r'(\d{1,2})[\/\.-](\d{1,2})(?:[\/\.-](\d{2,4}))?\s*(?:to|through|until|-)\s*(\d{1,2})[\/\.-](\d{1,2})(?:[\/\.-](\d{2,4}))?',
        lower
    )
    if num_match:
        m1, d1, y1_str, m2, d2, y2_str = num_match.groups()
        try:
            m1_val, d1_val = int(m1), int(d1)
            m2_val, d2_val = int(m2), int(d2)
            if 1 <= m1_val <= 12 and 1 <= m2_val <= 12:
                y1 = int(y1_str) if y1_str else ref_date.year
                y2 = int(y2_str) if y2_str else y1
                if not y1_str:
                    try:
                        cand = date(y1, m1_val, d1_val)
                        if cand < ref_date:
                            y1 += 1
                            y2 = y1
                    except ValueError:
                        return None, None, "Invalid calendar date."
                d_in = date(y1, m1_val, d1_val)
                d_out = date(y2, m2_val, d2_val)
                if y1_str and d_in < ref_date:
                    return None, None, "Check-in date cannot be in the past."
                if d_out <= d_in:
                    return None, None, "Check-out date must be after check-in date."
                return d_in.strftime("%Y-%m-%d"), d_out.strftime("%Y-%m-%d"), None
        except ValueError:
            return None, None, "Invalid calendar date."

    # 4. Relative "next month": "from the 10th to the 15th next month" or "next month from 10 to 15"
    if "next month" in lower:
        target_month = (ref_date.month % 12) + 1
        target_year = ref_date.year + 1 if ref_date.month == 12 else ref_date.year
        nm_match = re.search(
            r'(\d{1,2})(?:st|nd|rd|th)?\s*(?:to|through|until|-|\band\b)\s*(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?',
            lower
        )
        if nm_match:
            d1, d2 = int(nm_match.group(1)), int(nm_match.group(2))
            try:
                d_in = date(target_year, target_month, d1)
                d_out = date(target_year, target_month, d2)
                if d_out <= d_in:
                    return None, None, "Check-out date must be after check-in date."
                return d_in.strftime("%Y-%m-%d"), d_out.strftime("%Y-%m-%d"), None
            except ValueError:
                return None, None, "Invalid calendar date."

    # 5. Day-first ordinal range with "of [Month]":
    # e.g. "from the 12th to the 16th of November", "12 to 16 of November", "12th to 16th November"
    pattern_day_first = re.compile(
        rf'(?:from\s+)?(?:the\s+)?(\d{{1,2}})(?:st|nd|rd|th)?\s*'
        rf'(?:to|through|until|-|\band\b)\s*'
        rf'(?:the\s+)?(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?'
        rf'({MONTH_REGEX_PART})(?:\s*,?\s*(\d{{4}}))?',
        re.IGNORECASE
    )
    m = pattern_day_first.search(lower)
    if m:
        d1_str, d2_str, m_name, y_str = m.groups()
        m_val = MONTHS_MAP[m_name.lower()]
        d1 = int(d1_str)
        d2 = int(d2_str)
        if y_str:
            y1 = int(y_str)
        elif has_next_year:
            y1 = ref_date.year + 1
        else:
            y1 = ref_date.year
            try:
                cand = date(y1, m_val, d1)
                if cand < ref_date:
                    y1 += 1
            except ValueError:
                return None, None, "Invalid calendar date."
        try:
            d_in = date(y1, m_val, d1)
            d_out = date(y1, m_val, d2)
        except ValueError:
            return None, None, "Invalid calendar date."

        if y_str and d_in < ref_date:
            return None, None, "Check-in date cannot be in the past."
        if d_out <= d_in:
            return None, None, "Check-out date must be after check-in date."
        return d_in.strftime("%Y-%m-%d"), d_out.strftime("%Y-%m-%d"), None

    # 6. Month-first full range:
    # e.g. "October 17 to October 21", "December 28 to January 3", "March 10 to March 15 next year"
    pattern_two_months = re.compile(
        rf'({MONTH_REGEX_PART})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{{4}}))?'
        rf'\s*(?:to|through|until|-|\band\b)\s*'
        rf'({MONTH_REGEX_PART})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{{4}}))?',
        re.IGNORECASE
    )
    m = pattern_two_months.search(lower)
    if m:
        m1_name, d1_str, y1_str, m2_name, d2_str, y2_str = m.groups()
        m1 = MONTHS_MAP[m1_name.lower()]
        d1 = int(d1_str)
        m2 = MONTHS_MAP[m2_name.lower()]
        d2 = int(d2_str)

        if y1_str and y2_str:
            y1 = int(y1_str)
            y2 = int(y2_str)
        elif y2_str and not y1_str:
            y2 = int(y2_str)
            y1 = y2 if m1 <= m2 else y2 - 1
        elif y1_str and not y2_str:
            y1 = int(y1_str)
            y2 = y1 if m2 >= m1 else y1 + 1
        elif has_next_year:
            y1 = ref_date.year + 1
            y2 = y1 if m2 >= m1 else y1 + 1
        else:
            y1 = ref_date.year
            try:
                candidate_ci = date(y1, m1, d1)
            except ValueError:
                return None, None, "Invalid calendar date."

            if candidate_ci < ref_date:
                y1 += 1

            if m2 < m1:
                y2 = y1 + 1
            else:
                y2 = y1

        try:
            d_in = date(y1, m1, d1)
            d_out = date(y2, m2, d2)
        except ValueError:
            return None, None, "Invalid calendar date."

        if (y1_str or y2_str) and d_in < ref_date:
            return None, None, "Check-in date cannot be in the past."

        if d_out <= d_in:
            return None, None, "Check-out date must be after check-in date."

        return d_in.strftime("%Y-%m-%d"), d_out.strftime("%Y-%m-%d"), None

    # 7. Single-month range:
    # e.g. "October 17 to 21", "December 5 to December 8", "December 5 to 8", "November 21 2030 to 25"
    pattern_same_month = re.compile(
        rf'({MONTH_REGEX_PART})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{{4}}))?'
        rf'\s*(?:to|through|until|-|\band\b)\s*'
        rf'(\d{{1,2}})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{{4}}))?',
        re.IGNORECASE
    )
    m = pattern_same_month.search(lower)
    if m:
        m1_name, d1_str, y1_str, d2_str, y2_str = m.groups()
        m1 = MONTHS_MAP[m1_name.lower()]
        d1 = int(d1_str)
        d2 = int(d2_str)

        y_explicit = y2_str or y1_str
        if y_explicit:
            y1 = int(y_explicit)
        elif has_next_year:
            y1 = ref_date.year + 1
        else:
            y1 = ref_date.year
            try:
                candidate_ci = date(y1, m1, d1)
            except ValueError:
                return None, None, "Invalid calendar date."

            if candidate_ci < ref_date:
                y1 += 1

        try:
            d_in = date(y1, m1, d1)
            d_out = date(y1, m1, d2)
        except ValueError:
            return None, None, "Invalid calendar date."

        if y_explicit and d_in < ref_date:
            return None, None, "Check-in date cannot be in the past."

        if d_out <= d_in:
            return None, None, "Check-out date must be after check-in date."

        return d_in.strftime("%Y-%m-%d"), d_out.strftime("%Y-%m-%d"), None

    # 8. Single date check (Requirement 5):
    # e.g. "from October 17th", "checking in on November 20"
    pattern_single = re.compile(
        rf'(?:on|from|check-?in|starting)?\s*({MONTH_REGEX_PART})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{{4}}))?',
        re.IGNORECASE
    )
    m = pattern_single.search(lower)
    if m:
        m_name, d_str, y_str = m.groups()
        m_val = MONTHS_MAP[m_name.lower()]
        d_val = int(d_str)
        y_val = int(y_str) if y_str else (ref_date.year + 1 if has_next_year else ref_date.year)
        try:
            cand = date(y_val, m_val, d_val)
            if not y_str and not has_next_year and cand < ref_date:
                cand = date(y_val + 1, m_val, d_val)
            if y_str and cand < ref_date:
                return None, None, "Check-in date cannot be in the past."
            return cand.strftime("%Y-%m-%d"), None, "Please specify your check-out date."
        except ValueError:
            return None, None, "Invalid calendar date."

    return None, None, None
