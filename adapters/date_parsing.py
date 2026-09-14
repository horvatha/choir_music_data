"""Shared day-precision date parsing for this repo's page-scraping
fetchers (fetch_swedish_heritage.py, fetch_polmic.py, ...) -- pulling a
composer's birth/death date out of free-text biography prose, English
only (site-specific languages, e.g. fetch_swedish_heritage.py's Swedish
patterns, stay local to that script -- not every source has one, and
forcing them in here wouldn't actually be reused yet).

DAY_PRECISION_DATE matches a "29 August 1881" / "1st May, 1872" /
"24th September 1914" shaped date (day, optional ordinal suffix, month
name, optional comma, year) -- deliberately just this one shape; each
site's own full sentence-pattern regexes (born in PLACE on DATE, etc.)
are still built per-script around it, since sentence structure varies
site to site even when the date token itself doesn't. The optional
ordinal suffix tolerates a space before it (found via polmic.pl, which
wraps it in <sup>th</sup> -- strip_tags() turns "24<sup>th</sup>" into
"24 th", a space this repo's own tag-stripping introduces, not a real
site-to-site formatting difference worth a separate pattern), and the
space between the (optional-suffix) day and the month is itself now
optional too -- found via polmic.pl's Jan Ekier: "b. 29August 1913",
a plain source typo, not a tag-stripping artifact this time.

parse_abbreviated_birth_death() handles one specific, but apparently
common, shape across multiple unrelated sources: "b. DATE in/,) PLACE
... d. DATE in/,) PLACE" (found first on swedishmusicalheritage.com's
Bror Beckman/Erik Gustaf Geijer entries, then again verbatim on
polmic.pl's Andrzej Panufnik entry: "b. 24th September 1914 in Warsaw,
d. 27th October 1991 in Twickenham") -- worth sharing since it's
recurred exactly, not a coincidence of one site.
"""
import re

DAY_PRECISION_DATE = r"\d{1,2}\s?(?:st|nd|rd|th)?\s*[A-Za-z]+\.?,?\s+\d{4}"

# "Aug. 28, 1951" / "October 6 1806" -- month (possibly abbreviated with
# a period) before the day, found on polmic.pl (Augustyn Rafał) and
# separately on swedishmusicalheritage.com (Andreas Randel) -- the same
# American-style convention recurring on unrelated sites, so shared here
# rather than handled per-script. Day takes an optional ordinal suffix
# too (found via polmic.pl's Wiktor Łabuński: "Born on April 14th 1895"),
# mirroring DAY_PRECISION_DATE's own tolerance for the same thing.
MONTH_DAY_YEAR_DATE = r"[A-Za-z]+\.?\s+\d{1,2}\s?(?:st|nd|rd|th)?,?\s+\d{4}"

_EITHER_DATE = rf"(?:{DAY_PRECISION_DATE}|{MONTH_DAY_YEAR_DATE})"

# Place capture stops at ";" too, not just ".,": found via polmic.pl's
# Karol Anbild, "b. 16th February 1925 Katowice; d. 1st March 2008
# Kielce." -- a semicolon between the two halves instead of a comma.
# The space after "b."/"d." is itself optional (found via Joanna
# Bruzdowicz-Tittel: "b.17th May 1943 in Warsaw"), and so now is the
# period itself (found via polmic.pl's Tomasz Radziwonowicz: "b 23rd
# March 1953 in Warsaw" -- no period at all). The trailing \b (not just
# a bare "b"/"d") matters once the period is optional: without it,
# case-insensitive \bd matched the capital D starting "December" itself
# (found via Józef Domżał: "b. December 11, 2003, Warsaw" produced a
# bogus death of "ecember 11, 2003" -- \bd\.?\s* swallowed the "D" as a
# zero-period abbreviation marker, then [A-Za-z]+ happily accepted
# "ecember" as a fake month name). \bd\b requires the letter be its own
# token -- a boundary immediately follows "b"/"d" whether that's a
# period, a space, or end of string, but not another word character
# like "e" -- which "b."/"b "/"b" all still satisfy but "December"'s
# leading "D" does not.
_B_ABBREV_RE = re.compile(r"\bb\b\.?\s*(%s)(?:\s+in\s+|[,;]\s*)([^.,;]+)" % _EITHER_DATE, re.IGNORECASE)
_D_ABBREV_RE = re.compile(r"\bd\b\.?\s*(%s)(?:\s+in\s+|[,;]\s*)([^.,;]+)" % _EITHER_DATE, re.IGNORECASE)


_STRAY_ORDINAL_SPACE_RE = re.compile(r"(\d)\s+(st|nd|rd|th)\b")


def _clean_date(date_str: str) -> str:
    """Collapses the "24 th" DAY_PRECISION_DATE's optional-space-before-
    ordinal tolerates back into "24th" for the value callers actually
    store/display -- matching only, not cleanup, happens in the regex
    itself."""
    return _STRAY_ORDINAL_SPACE_RE.sub(r"\1\2", date_str)


# Full "born"/"died" sentence patterns (English only -- a site with its
# own non-English language, e.g. fetch_swedish_heritage.py's Swedish
# text, needs its own mirror set; not attempted here since nothing else
# has needed it yet). Originally built for swedishmusicalheritage.com
# across many rounds of real-page bug-fixing (see git history/the
# comments each pattern still carries below), then found to apply
# verbatim to polmic.pl too (Wojciech Kilar: "Born in Lviv on 17 July
# 1932, died in Katowice on 29 December 2013" -- the exact
# BORN_PLACE_DATE/DIED_PLACE_DATE shape), which is what justified
# sharing this rather than leaving it as one script's private regexes.
#
# Place-capturing groups are restricted to [^.]+? (never crossing a full
# stop) rather than a bare .+? -- the regex runs against the *whole*
# multi-sentence biography, not just the birth/death sentence in
# isolation, so an unrestricted .+? happily skips right over the comma/
# period after the real place and keeps consuming text until it finds a
# much later "and" or "on DATE" match elsewhere in the bio (found via
# Stenhammar: birth "place" came back as half his biography).
#
# "on" before the date is itself optional and inconsistently used
# (found via Wilhelm Uddén: "born in Stockholm 4 August 1799 and died
# there 3 May 1868", no "on" anywhere) -- applied throughout.
#
# The birth place capture must not cross a "died" clause -- found via
# Conrad Friedrich Hurlebusch: "born in Brunswick, Northern Germany in
# 1691 (baptised 30 December) and died in Amsterdam 17 December 1765."
# His birth is genuinely year-only (no day/month attached to "1691"),
# so unguarded this pattern ran straight past "and died in Amsterdam"
# and matched the DEATH date/place as if they were birth's.
# All of these use _EITHER_DATE (not just DAY_PRECISION_DATE) so the
# American month-first order matches full "born"/"died" sentences too,
# not just the abbreviated "b./d." form -- found via polmic.pl's
# Kazimierz Serocki: "born March 3, 1922, in Toruń; died January 9,
# 1981, in Warsaw."
_BORN_PLACE_DATE_RE = re.compile(rf"born (?:in|at) ((?:(?!died|\.).)+?)\s+(?:on\s+)?({_EITHER_DATE})", re.IGNORECASE)
# Two-tier fallback, tried in this order: PLACE can itself contain a
# comma (e.g. "Löth parish, Östergötland"), so prefer stopping at " and"
# (the Agrell shape: "...in PLACE and died...") and only fall back to
# stopping at the first comma/period/semicolon (the Stenhammar shape:
# "...in PLACE, was one of...", no "and died" continuation) when no
# " and" is found -- a comma-stop alone would wrongly truncate a comma-
# containing place name in the first shape. The date and "in" may have a
# comma between them too (Serocki again: "born March 3, 1922, in
# Toruń") -- optional, not required, since the day-precision shape
# doesn't use one ("born 4 August 1799 in Stockholm").
_BORN_DATE_PLACE_AND_RE = re.compile(rf"born (?:on )?({_EITHER_DATE}),?\s+in\s+([^.]+?)\s+and\s+died\b", re.IGNORECASE)
_BORN_DATE_PLACE_PUNCT_RE = re.compile(rf"born (?:on )?({_EITHER_DATE}),?\s+in\s+([^.,;]+)[.,;]", re.IGNORECASE)
_DIED_SAME_PLACE_RE = re.compile(rf"died there (?:on )?({_EITHER_DATE})|where (?:he|she|they) (?:also )?died (?:on )?({_EITHER_DATE})", re.IGNORECASE)
_DIED_PLACE_DATE_RE = re.compile(rf"(?:deceased|died) (?:at|in) ([^.]+?)\s+(?:on\s+)?({_EITHER_DATE})", re.IGNORECASE)
_DIED_DATE_PLACE_RE = re.compile(rf"died (?:on )?({_EITHER_DATE}),?\s+in\s+([^.;]+?)[.;]", re.IGNORECASE)
# Last-resort, no-place fallbacks -- some entries never name a place at
# all for one or both events (found via Bengt Wilhelm Hallberg: "was
# born on 13 May 1824 and died 4 May 1883", no place anywhere in the
# sentence). Kept as a *separate* function (parse_born_died_noplace,
# below) rather than folded into parse_born_died_sentence's own tier
# list: fetch_swedish_heritage.py tries this no-place fallback at a
# different relative position for birth (after its Swedish patterns)
# than for death (before them) -- genuinely per-site/per-field tuning,
# not something safe to bake into one fixed shared order.
_BORN_DATE_NOPLACE_RE = re.compile(rf"born (?:on )?({_EITHER_DATE})\b", re.IGNORECASE)
_DIED_DATE_NOPLACE_RE = re.compile(rf"died (?:on )?({_EITHER_DATE})\b", re.IGNORECASE)


def _empty():
    return {"place": None, "date": None, "raw": None}


def parse_born_died_sentence(text: str, birth_place: str | None = None) -> tuple[dict, dict]:
    """Returns (birth, death), each {"place", "date", "raw"} -- English
    "born .../died ..." full-word, *place-aware* sentence patterns only
    (see the block comment above) -- not the "b./d." abbreviated form
    (parse_abbreviated_birth_death() instead) and not the no-place
    fallback (parse_born_died_noplace() instead, see its own docstring
    for why it's kept separate). Callers typically try several of these
    in whatever order matches their site's more common style.

    birth_place: only used for death's "died there"/"where ... also
    died" same-place resolution -- pass the birth place you already
    resolved (from this function's own birth result, or a same-text
    call to a different tier that found one) if you want that handled;
    left None, "died there" still matches but death["place"] stays None."""
    birth = _empty()
    m = _BORN_PLACE_DATE_RE.search(text)
    if m:
        birth = {"place": m.group(1).strip(), "date": _clean_date(m.group(2).strip()), "raw": m.group(0)}
    else:
        m = _BORN_DATE_PLACE_AND_RE.search(text)
        if m:
            birth = {"place": m.group(2).strip(), "date": _clean_date(m.group(1).strip()), "raw": m.group(0)}
        else:
            m = _BORN_DATE_PLACE_PUNCT_RE.search(text)
            if m:
                birth = {"place": m.group(2).strip(), "date": _clean_date(m.group(1).strip()), "raw": m.group(0)}

    death = _empty()
    m = _DIED_SAME_PLACE_RE.search(text)
    if m:
        death = {"place": birth["place"] or birth_place, "date": _clean_date((m.group(1) or m.group(2)).strip()), "raw": m.group(0)}
    else:
        m = _DIED_PLACE_DATE_RE.search(text)
        if m:
            death = {"place": m.group(1).strip(), "date": _clean_date(m.group(2).strip()), "raw": m.group(0)}
        else:
            m = _DIED_DATE_PLACE_RE.search(text)
            if m:
                death = {"place": m.group(2).strip(), "date": _clean_date(m.group(1).strip()), "raw": m.group(0)}

    return birth, death


def parse_born_died_noplace(text: str) -> tuple[dict, dict]:
    """Returns (birth, death), each {"place": None, "date", "raw"} --
    the last-resort "born DATE"/"died DATE" fallback with no place
    mentioned at all (see _BORN_DATE_NOPLACE_RE's comment above). Kept
    separate from parse_born_died_sentence() rather than a combined
    tier list: where this belongs relative to a site's own non-English
    patterns is genuine per-site tuning (fetch_swedish_heritage.py uses
    it at a different point for birth than for death), not something a
    shared fixed order should decide."""
    birth = _empty()
    m = _BORN_DATE_NOPLACE_RE.search(text)
    if m:
        birth = {"place": None, "date": _clean_date(m.group(1).strip()), "raw": m.group(0)}

    death = _empty()
    m = _DIED_DATE_NOPLACE_RE.search(text)
    if m:
        death = {"place": None, "date": _clean_date(m.group(1).strip()), "raw": m.group(0)}

    return birth, death


def parse_abbreviated_birth_death(text: str) -> tuple[dict, dict]:
    """Returns (birth, death), each {"place", "date", "raw"} -- "raw" is
    the exact matched substring, for callers that want to show their
    work. Either half is the all-None _empty() dict if that pattern
    isn't found (e.g. only a death date given, or neither in this
    shape at all -- not every source uses "b."/"d.")."""
    birth = _empty()
    death = _empty()

    m = _B_ABBREV_RE.search(text)
    if m:
        birth = {"place": m.group(2).strip(), "date": _clean_date(m.group(1).strip()), "raw": m.group(0)}

    m = _D_ABBREV_RE.search(text)
    if m:
        death = {"place": m.group(2).strip(), "date": _clean_date(m.group(1).strip()), "raw": m.group(0)}

    return birth, death
