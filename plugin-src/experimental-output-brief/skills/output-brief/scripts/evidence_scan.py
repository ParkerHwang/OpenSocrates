#!/usr/bin/env python3
"""factcheck - deterministic pre-send FLAGS for an AI-written output, compared with the material the user
supplied. No model, no network, nothing stored. It is a PRESENCE check, not a fact check: it can tell that
a number, date or confirmation word is (or is not) somewhere in your material. It cannot tell that the
output attaches it to the right thing. It never edits the output and never says "verified" or "safe".

Flags (all surface-level, see KNOWN_BLIND_SPOTS):
  novel_date / novel_number   a date or number in the output that is not in the sources; a date whose
                              YEAR differs from the year your material gives for that day is also novel_date
  commitment                  confirmation wording (confirmed, booked, approved, 확정 ...) that the
                              material does not contain, or contains only negated ("not confirmed")
  missing_required            a fact the requester listed with --must is absent from the output
  year_unverified (info)      the output adds a year to a date that your material gives without a year
  unit_binding (info)         "24 USD" in the output, but your material attaches USD to a different number
  status_binding (info)       "Room B is booked", but your material attaches "booked" to other items only
  uncertainty_dropped (info)  the material marks something unsettled; the output has no such wording
  causal (info)               causal wording (because, due to, 때문에 ...) not present in the material

Every run also lists the values that were matched BY PRESENCE ONLY (coverage). Those are not verified.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

KNOWN_BLIND_SPOTS = [
    "SOURCE AUTHORITY: a value appearing only in an old, rejected, or proposed source is still treated as present",
    "CONDITIONAL PROMISES: conditional or future wording may still be an unauthorized promise",
    "STATUS BINDING: 'booked' / 'confirmed' attached to the wrong item is only caught in simple English "
    "sentences with capitalised or numeric item names (status_binding, INFO); not in Korean or paraphrases",
    "VALUE/UNIT BINDING: a number moved to another unit or item is only caught when a unit or label sits "
    "directly next to it and the label also appears in your material (unit_binding, INFO)",
    "ENTITY LINKING: wrong person, room, vendor or customer using names that DO appear in the material",
    "a fact stated wrongly using numbers/words that DO appear in the material (e.g. ratio vs percentage points)",
    "paraphrased commitments not in the marker list (e.g. 'locked in', 'all set')",
    "numbers written as words ('twenty-four'), relative dates ('next Friday'), 2-digit years, scales (만원, k, M)",
    "derived values (sums, percentages) are flagged as unverified even when correct",
    "an output that omits an unsettled item entirely is fine, yet may still raise the info flag",
    "languages other than English/Korean",
]

_MON = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_MON_RE = "|".join(sorted(_MON, key=len, reverse=True))
_YEAR = r"(?:19|20)\d{2}"

COMMIT = [  # (regex, label)
    (r"\bconfirmed\b", "confirmed"),
    (r"\bbooked\b", "booked"),
    (r"\bapproved\b", "approved"),
    (r"\bguaranteed?\b", "guaranteed"),
    (r"\breserved\b", "reserved"),
    (r"\bsecured\b", "secured"),
    (r"\bfinali[sz]ed\b", "finalized"),
    (r"\bconsented\b", "consented"),
    (r"\bsigned\b", "signed"),
    (r"\b(has|have) agreed\b", "has agreed"),
    (r"확정", "확정"),
    (r"예약\s*(완료|되었|됐)", "예약 완료"),
    (r"승인\s*(되었|됐|완료)", "승인 완료"),
    (r"보장", "보장"),
    (r"동의(했|하였|받았)", "동의"),
    (r"체결", "체결"),
]
SENTENCE_END = re.compile(r"[.!?。;\n]")
EN_NEG_PRE = re.compile(
    r"\b(?:not|never|no|nothing|none|neither|nor|without|cannot)\b|n't\b|\byet to\b",
    re.I,
)
EN_COND_PRE = re.compile(
    r"\b(?:to be|will be|would be|once|if|when|until|unless|pending|awaiting|subject to)\s+(?:\w+\s+){0,2}$",
    re.I,
)
KO_NEG_PRE = re.compile(r"(?:^|[^가-힣])(?:미|불)$|(?:^|[^가-힣])(?:아직은|아직도|아직|안|못)\s*$")
KO_TAIL_NEG = re.compile(
    r"""^\s*(?:
        (?:은|이|가|는|도)?\s*(?:되|하|돼|됐|했)?(?:지|진)(?:는|도|를)?\s*(?:않|못|아니)
      | (?:은|이|가|는|도)?\s*(?:안|못)\s*(?:됐|됨|되|돼|했|함)
      | (?:은|이|가|는)?\s*(?:아[니닙]|아님)
      | (?:된|한)\s*(?:것|건|게|바|내용|사항|사실)\S{0,3}\s*(?:아[니닙]|없)
      | (?:이전|전)(?:(?![가-힣])|입니다|이다|이라|이며|인|이고|이지만|에는|까지)
      | (?:가능\s*)?(?:여부|보류|대기|미정)
      | (?:이라고|라고)?\s*(?:보기|하기|말하기)\s*어렵
      | (?:되었|됐|했)(?:는지|을지|나요?)
      | (?:을|를|은|는)?\s*(?:요청|부탁|문의)
    )""",
    re.X,
)
KO_TAIL_COND = re.compile(
    r"""^\s*(?:
        (?:되|하|돼)?(?:면|려면)
      | (?:되|하)는\s*(?:대로|즉시)
      | (?:되|하)기\s*(?:전|까지)
      | (?:되어야|돼야|하여야|해야)
      | (?:될|할)(?![가-힣]*\s*수\s*있)
      | 시(?![가-힣])
      | 예정
    )""",
    re.X,
)
UNCERTAIN = re.compile(
    r"\b(tentative(ly)?|tbd|pending|not yet|not confirmed|still being considered|under consideration|"
    r"under review|to be decided|to be determined|provisional|subject to)\b|"
    r"미정|검토\s*중|검토중|확정되지|아직|협의\s*중|잠정",
    re.I,
)
CAUSAL = re.compile(
    r"\b(because|due to|caused by|as a result of|thanks to|led to)\b|때문에|덕분에|으로 인해|원인",
    re.I,
)

# a date is (year or None, month, day)
Date = tuple


def fmt_date(d: Date) -> str:
    y, mo, dd = d
    return f"{y}-{mo:02d}-{dd:02d}" if y else f"{mo}/{dd} (no year)"


def _scan(text: str) -> tuple[set, set, str]:
    """(dates, numbers, text with the dates blanked out)."""
    t = re.sub(r"(?m)^\s*(?:\d+[.)]|[-*•])\s+", "", text)  # list markers are not data
    dates: set = set()

    def add(y, mo, d):
        if 1 <= mo <= 12 and 1 <= d <= 31:
            dates.add((int(y) if y else None, mo, d))

    # year-bearing forms first so the year is not lost, then the same forms without a year
    pats = [
        (
            rf"(?<!\d)({_YEAR})-(\d{{1,2}})-(\d{{1,2}})(?!\d)",
            lambda m: add(m[1], int(m[2]), int(m[3])),
        ),
        (
            rf"(?<!\d)({_YEAR})/(\d{{1,2}})/(\d{{1,2}})(?!\d)",
            lambda m: add(m[1], int(m[2]), int(m[3])),
        ),
        (
            rf"({_YEAR})\s*년\s*(\d{{1,2}})\s*월\s*(\d{{1,2}})\s*일",
            lambda m: add(m[1], int(m[2]), int(m[3])),
        ),
        (r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", lambda m: add(None, int(m[1]), int(m[2]))),
        (
            rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MON_RE})\b\.?(?:,?\s+({_YEAR})\b)?",
            lambda m: add(m[3], _MON[m[2].lower()], int(m[1])),
        ),
        (
            rf"\b({_MON_RE})\b\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+({_YEAR})\b)?",
            lambda m: add(m[3], _MON[m[1].lower()], int(m[2])),
        ),
        (
            rf"(?<![\d/])(\d{{1,2}})/(\d{{1,2}})/({_YEAR})(?![\d/])",  # m/d/yyyy or d/m/yyyy: keep both readings
            lambda m: (add(m[3], int(m[1]), int(m[2])), add(m[3], int(m[2]), int(m[1]))),
        ),
        (
            r"(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])",
            lambda m: (add(None, int(m[1]), int(m[2])), add(None, int(m[2]), int(m[1]))),
        ),
    ]
    for rx, fn in pats:
        for m in list(re.finditer(rx, t, re.I)):
            fn(m)
        t = re.sub(rx, " ", t, flags=re.I)
    nums = {n.replace(",", "") for n in re.findall(r"\d+(?:[.,]\d+)*", t)}
    return dates, nums, t


def tokens(text: str) -> tuple[set, set]:
    """(dates as (year|None, month, day), numbers as strings)."""
    d, n, _ = _scan(text)
    return d, n


def date_status(d: Date, material: set) -> tuple[str, str]:
    """-> (status, detail). status: ok | year_unverified | year_mismatch | absent"""
    y, mo, dd = d
    same_day = {x for x in material if x[1:] == (mo, dd)}
    if not same_day:
        return "absent", ""
    if y is None or (y, mo, dd) in material:
        return "ok", ""
    if (None, mo, dd) in same_day:
        return "year_unverified", ""
    years = sorted({x[0] for x in same_day if x[0]})
    return "year_mismatch", ", ".join(map(str, years))


# ---- unit / label binding (INFO) -----------------------------------------------------------------
_LABEL_STOP = {
    "the",
    "and",
    "for",
    "are",
    "was",
    "were",
    "has",
    "have",
    "had",
    "will",
    "with",
    "from",
    "that",
    "this",
    "not",
    "but",
    "per",
    "than",
    "about",
    "over",
    "under",
    "into",
    "only",
    "also",
    "all",
    "any",
    "our",
    "your",
    "their",
    "its",
    "can",
    "may",
    "must",
    "should",
    "would",
    "could",
    "st",
    "nd",
    "rd",
    "th",
    "is",
    "in",
    "at",
    "on",
    "of",
    "to",
    "by",
    "or",
    "as",
    "an",
    "it",
    "no",
    "if",
}
_UNIT_MAP = {
    "$": "usd",
    "usd": "usd",
    "dollar": "usd",
    "dollars": "usd",
    "달러": "usd",
    "₩": "krw",
    "krw": "krw",
    "won": "krw",
    "원": "krw",
    "만원": "krw",
    "€": "eur",
    "eur": "eur",
    "euro": "eur",
    "euros": "eur",
    "%": "pct",
    "percent": "pct",
    "퍼센트": "pct",
    "pct": "pct",
}
_FWD = re.compile(r"\s{0,2}(%|[A-Za-z]{2,}|만원|원|명|석|개|건|시간|분|퍼센트|달러)")
_BWD = re.compile(r"([A-Za-z]{2,}|[$€£₩])\s{0,2}[:：]?\s{0,2}$")


def _norm_label(w: str) -> str | None:
    w = w.lower()
    if w in _UNIT_MAP:
        return _UNIT_MAP[w]
    if w in _LABEL_STOP or len(w) < 2:
        return None
    return w[:-1] if len(w) > 3 and w.endswith("s") else w


def number_labels(t: str) -> dict[str, set[str]]:
    """number -> labels directly after it ('24 people', '24%') or directly before it ('Seats: 24', '$50')."""
    out: dict[str, set[str]] = {}
    for m in re.finditer(r"(?<![\w.])\d+(?:[.,]\d+)*", t):
        num = m.group().replace(",", "")
        labs = out.setdefault(num, set())
        f = _FWD.match(t[m.end() : m.end() + 24])
        b = _BWD.search(t[max(0, m.start() - 24) : m.start()])
        for w in (f.group(1) if f else None, b.group(1) if b else None):
            lab = _norm_label(w) if w else None
            if lab:
                labs.add(lab)
    return out


def unit_binding_findings(mat_text: str, out_text: str, shared_nums: set[str]) -> list[dict]:
    ml, ol = number_labels(mat_text), number_labels(out_text)
    carrier: dict[str, set[str]] = {}  # label -> numbers it sits next to in the material
    for n, labs in ml.items():
        for lab in labs:
            carrier.setdefault(lab, set()).add(n)
    found = []
    for n in sorted(shared_nums):
        for lab in sorted(ol.get(n, ())):
            if lab in carrier and n not in carrier[lab]:
                found.append(
                    {
                        "severity": "INFO",
                        "kind": "unit_binding",
                        "message": f"output pairs {n} with '{lab}', but your material pairs '{lab}' with "
                        f"{', '.join(sorted(carrier[lab]))} - check the number is attached to the right thing",
                    }
                )
    return found


# ---- status binding (INFO) -----------------------------------------------------------------------
_CAP_STOP = {
    "the",
    "we",
    "it",
    "all",
    "our",
    "this",
    "that",
    "these",
    "those",
    "he",
    "she",
    "they",
    "a",
    "an",
    "i",
    "you",
    "if",
    "as",
    "in",
    "on",
    "at",
    "to",
    "and",
    "or",
    "but",
    "so",
    "yes",
    "no",
    "please",
    "dear",
    "hi",
    "hello",
    "thanks",
    "thank",
    "subject",
}


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[.!?\n。]+", text) if s.strip()]


def _idents(sentence: str) -> set[str]:
    """capitalised words and numbers in a sentence, minus common sentence openers: crude item names."""
    toks = re.findall(r"\b(?:[A-Z][A-Za-z0-9]*|\d+[A-Za-z]*)\b", sentence)
    return {t for t in toks if t.lower() not in _CAP_STOP}


def status_binding_findings(material: str, output: str) -> list[dict]:
    found = []
    msents, osents = _sentences(material), _sentences(output)
    for rx, label in COMMIT:
        if not (re.search(rx, output, re.I) and _present(rx, material)):
            continue
        carriers = [s for s in msents if _present(rx, s)]
        carrier_tokens = set().union(*[_idents(s) for s in carriers]) if carriers else set()
        for os_ in osents:
            if not re.search(rx, os_, re.I) or not _present(rx, os_):
                continue
            idents = _idents(os_)
            if not idents or any(idents <= _idents(s) for s in carriers):
                continue
            elsewhere = {
                t
                for t in idents - carrier_tokens
                if any(t in _idents(s) for s in msents if s not in carriers)
            }
            if elsewhere:
                found.append(
                    {
                        "severity": "INFO",
                        "kind": "status_binding",
                        "message": f"'{label}' appears in your material, but not together with "
                        f"{', '.join(sorted(elsewhere))} (output: {os_!r}) - check it is stated for this item",
                    }
                )
    return found


# ---- main check ----------------------------------------------------------------------------------
def _present(rx: str, text: str) -> bool:
    """Look for an affirmed marker; ambiguous or unsupported forms remain cues."""
    for m in re.finditer(rx, text, re.I):
        before = SENTENCE_END.split(text[max(0, m.start() - 24) : m.start()])[-1]
        after = SENTENCE_END.split(text[m.end() : m.end() + 32])[0]
        if EN_NEG_PRE.search(before) or KO_NEG_PRE.search(before) or KO_TAIL_NEG.match(after):
            continue
        if EN_COND_PRE.search(before) or KO_TAIL_COND.match(after):
            continue
        return True
    return False


def analyze(  # noqa: C901 - keep each distinct advisory check visible
    sources: list[str], prompt: str, output: str, must: list[str] | None = None
) -> dict:
    if not any(source.strip() for source in sources):
        raise ValueError("provide at least one nonempty source")
    # A request can quote the draft. It is not independent evidence for it.
    material = "\n".join(sources)
    md, mn, mt = _scan(material)
    od, on, ot = _scan(output)
    findings: list[dict] = []
    cov = {"dates": [], "numbers": [], "wording": []}

    if output.strip() and any(output.strip() in source for source in sources):
        findings.append(
            {
                "severity": "INFO",
                "kind": "draft_in_source",
                "message": "The full draft also appears in a source. The comparison may be circular; review the source selection.",
            }
        )

    for d in sorted(od, key=lambda x: (x[0] or 0, x[1], x[2])):
        st, detail = date_status(d, md)
        if st == "ok":
            cov["dates"].append(fmt_date(d))
        elif st == "year_unverified":
            findings.append(
                {
                    "severity": "INFO",
                    "kind": "year_unverified",
                    "message": f"output says {fmt_date(d)}; your material gives {d[1]}/{d[2]} without a year - confirm the year",
                }
            )
        elif st == "year_mismatch":
            findings.append(
                {
                    "severity": "HIGH",
                    "kind": "novel_date",
                    "message": f"output says {fmt_date(d)}; your material gives {d[1]}/{d[2]} only for year {detail}",
                }
            )
        else:
            findings.append(
                {
                    "severity": "HIGH",
                    "kind": "novel_date",
                    "message": f"date {fmt_date(d)} is not in your material; if derived, recompute it",
                }
            )
    for n in sorted(on - mn, key=lambda x: (len(x), x)):
        findings.append(
            {
                "severity": "HIGH",
                "kind": "novel_number",
                "message": f"number {n} is not in your material; if derived, recompute it before sending",
            }
        )
    cov["numbers"] = sorted(on & mn, key=lambda x: (len(x), x))
    findings += unit_binding_findings(mt, ot, on & mn)
    for rx, label in COMMIT:
        if _present(rx, output):
            if _present(rx, material):
                cov["wording"].append(label)
            else:
                findings.append(
                    {
                        "severity": "HIGH",
                        "kind": "commitment",
                        "message": f"'{label}' wording appears in the output but your material does not state it (or only negates it)",
                    }
                )
    findings += status_binding_findings(material, output)
    for item in must or []:
        if item.lower() not in output.lower():
            findings.append(
                {
                    "severity": "HIGH",
                    "kind": "missing_required",
                    "message": f"required item not found: {item!r}",
                }
            )
    if UNCERTAIN.search(material) and not UNCERTAIN.search(output):
        findings.append(
            {
                "severity": "INFO",
                "kind": "uncertainty_dropped",
                "message": "your material marks something as unsettled; the output has no uncertainty wording (fine if that item is omitted)",
            }
        )
    if CAUSAL.search(output) and not CAUSAL.search(material):
        findings.append(
            {
                "severity": "INFO",
                "kind": "causal",
                "message": "causal wording in the output that your material does not contain; check the cause is supported",
            }
        )
    return {
        "ran": True,
        "verified": False,
        "input_summary": {
            "source_characters": [len(source) for source in sources],
            "prompt_characters": len(prompt),
            "output_characters": len(output),
            "prompt_used_as_source": False,
        },
        "findings": findings,
        "matched_by_presence_only": cov,
        "meaning": "matched_by_presence_only values occur somewhere in your material. Nobody checked that they "
        "refer to the same item, status, unit or period as in the output.",
        "blind_spots": KNOWN_BLIND_SPOTS,
    }


def check(
    sources: list[str], prompt: str, output: str, must: list[str] | None = None
) -> list[dict]:
    return analyze(sources, prompt, output, must)["findings"]


def source_contexts(sources: list[str], output: str) -> dict:
    """Find source lines containing a draft number/date; not a support judgment."""
    dates, numbers = tokens(output)
    matches = []
    omitted = 0
    expected = {("date", fmt_date(d)) for d in dates} | {("number", n) for n in numbers}
    seen = set()
    dates_by_day: dict[tuple[int, int], set] = {}
    for date in dates:
        dates_by_day.setdefault(date[1:], set()).add(date)
    for source_index, source in enumerate(sources, 1):
        for line_number, line in enumerate(source.splitlines(), 1):
            line_dates, line_numbers = tokens(line)
            values = _matching_dates(dates, dates_by_day, line_dates)
            values.update(("number", n, "normalized") for n in numbers & line_numbers)
            for kind, value, match_type in sorted(values):
                seen.add((kind, value))
                if len(matches) >= 30:
                    omitted += 1
                    continue
                visible, escaped = _escape_controls(line) if len(line) <= 1000 else (None, False)
                matches.append(
                    {
                        "kind": kind,
                        "value": value,
                        "source": source_index,
                        "line": line_number,
                        "match_type": match_type,
                        "text": visible,
                        "controls_escaped": escaped,
                    }
                )
    return {
        "meaning": "Value presence in a line is not evidence that the line supports the claim.",
        "matches": matches,
        "additional_matches_not_shown": omitted,
        "values_without_line_match": [
            {"kind": kind, "value": value} for kind, value in sorted(expected - seen)
        ],
    }


def _matching_dates(dates: set, dates_by_day: dict, line_dates: set) -> set:
    """Use exact lookups for dated sources and a day index for yearless ones."""
    matches = set()
    for source_date in line_dates:
        if source_date[0] is None:
            candidates = dates_by_day.get(source_date[1:], ())
        else:
            candidates = (
                candidate
                for candidate in (source_date, (None, *source_date[1:]))
                if candidate in dates
            )
        for date in candidates:
            kind = (
                "same_year" if date[0] is not None and date[0] == source_date[0] else "year_missing"
            )
            matches.add(("date", fmt_date(date), kind))
    return matches


def _escape_controls(text: str) -> tuple[str, bool]:
    """Render terminal and bidirectional controls visibly, including in JSON."""
    result = []
    escaped = False
    for character in text:
        if unicodedata.category(character) in {"Cc", "Cf", "Cs"}:
            code = ord(character)
            result.append(f"\\u{code:04x}" if code <= 0xFFFF else f"\\U{code:08x}")
            escaped = True
        else:
            result.append(character)
    return "".join(result), escaped


def render(res: dict) -> str:
    f = res["findings"]
    high = sum(1 for x in f if x["severity"] == "HIGH")
    lines = [
        "Review cues only: a flag can be correct, including a calculated value. "
        "No flags do not mean the draft is safe or accurate.",
        "The scan may miss a real value attached to the wrong person, item, or event.",
        "Input lengths show what the scan received, not whether it was complete or unchanged: "
        f"sources={res['input_summary']['source_characters']}, "
        f"request={res['input_summary']['prompt_characters']}, "
        f"draft={res['input_summary']['output_characters']} characters.",
        "",
    ]
    lines.extend(
        f"[{'REVIEW' if x['severity'] == 'HIGH' else 'INFO'}] {x['kind']}: {x['message']}"
        for x in f
    )
    cov = res["matched_by_presence_only"]
    lines.append("")
    lines.append(
        f"RESULT: NOT VERIFIED. {len(f)} flag(s), {high} to review. "
        "Zero flags is not a pass; this tool only compares surface strings with your material."
    )
    if any(cov.values()):
        lines.append(
            "Matched by PRESENCE ONLY (found somewhere in your material; NOT checked that they mean the same thing there):"
        )
        for k, label in (
            ("numbers", "numbers"),
            ("dates", "dates"),
            ("wording", "confirmation wording"),
        ):
            if cov[k]:
                lines.append(f"  {label}: {', '.join(cov[k])}")
        lines.append(
            "  -> a person must check each of these is attached to the right item, status, unit and period."
        )
    lines.append(f"Blind spots ({len(res['blind_spots'])}), e.g.: " + res["blind_spots"][0])
    lines.append("  (all of them: --json)")
    if "source_contexts" in res:
        contexts = res["source_contexts"]
        lines.append("")
        lines.append("Source lines containing draft values (presence does not prove support):")
        for match in contexts["matches"]:
            source_line = match["text"] if match["text"] is not None else "[line too long to show]"
            lines.append(
                f"  {match['kind']} {match['value']}, source {match['source']} "
                f"line {match['line']} ({match['match_type']}): {source_line}"
            )
            if match["controls_escaped"]:
                lines.append("  Control characters were escaped for display.")
        if contexts["additional_matches_not_shown"]:
            lines.append(
                f"  Additional matches not shown: {contexts['additional_matches_not_shown']}"
            )
        if not contexts["matches"]:
            lines.append("  No matching values found by this limited scan.")
        for value in contexts["values_without_line_match"]:
            lines.append(
                f"  No matching line for {value['kind']} {value['value']} (not a truth verdict)."
            )
    return "\n".join(lines)


def _missing_sources(json_mode: bool) -> int:
    message = "Scan not run: provide separated source material, not the whole request as a source."
    if json_mode:
        print(json.dumps({"ran": False, "verified": False, "reason": message}))
    else:
        print(message, file=sys.stderr)
    return 2


def main(argv=None) -> int:  # noqa: C901 - keep input modes and failure boundaries explicit
    ap = argparse.ArgumentParser(
        prog="factcheck",
        description=__doc__.split("\n")[0],
        epilog="Exit code 1 (with --strict) means a HIGH flag. Exit code 0 NEVER means the output is correct.",
    )
    ap.add_argument(
        "--source", action="append", default=[], help="user-provided source file (repeatable)"
    )
    ap.add_argument("--prompt", help="request text file; not used as evidence")
    ap.add_argument("--output", help="draft file to inspect")
    ap.add_argument(
        "--stdin-json",
        action="store_true",
        help="read sources, prompt, and output as a JSON object from standard input",
    )
    ap.add_argument(
        "--must", action="append", default=[], help="fact that must appear (repeatable)"
    )
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--show-context",
        action="store_true",
        help="include matching source lines in output; host may retain tool output",
    )
    ap.add_argument("--strict", action="store_true", help="exit 1 if any HIGH flag")
    a = ap.parse_args(argv)

    def rd(path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

    if a.stdin_json:
        if a.source or a.prompt or a.output:
            ap.error("--stdin-json cannot be combined with file inputs")
        try:
            payload = json.load(sys.stdin)
        except (ValueError, UnicodeError):
            ap.error("standard input must contain a JSON object")
        if not isinstance(payload, dict):
            ap.error("standard input must contain a JSON object")
        sources = payload.get("sources", [])
        prompt = payload.get("prompt", "")
        output = payload.get("output")
        if not isinstance(sources, list) or not all(isinstance(s, str) for s in sources):
            ap.error("sources must be a list of strings")
        if not isinstance(prompt, str) or not isinstance(output, str):
            ap.error("prompt and output must be strings")
        if not any(s.strip() for s in sources):
            return _missing_sources(a.json)
    else:
        if not a.output:
            ap.error("provide --output")
        if not a.source:
            return _missing_sources(a.json)
        sources = [rd(s) for s in a.source]
        prompt = rd(a.prompt) if a.prompt else ""
        output = rd(a.output)
        if not any(s.strip() for s in sources):
            return _missing_sources(a.json)
    res = analyze(sources, prompt, output, a.must)
    if a.show_context:
        res["source_contexts"] = source_contexts(sources, output)
    print(json.dumps(res, ensure_ascii=False, indent=2) if a.json else render(res))
    return 1 if a.strict and any(f["severity"] == "HIGH" for f in res["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
