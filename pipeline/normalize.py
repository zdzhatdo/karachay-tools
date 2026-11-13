"""Stage 3 (normalize): clean extracted text with explicit, counted rules.

Each rule fixes a problem measured in the data. Earlier outputs are never edited: the original text stays in
the extract output, and this stage records what it changed.
"""

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

STAGE_VERSION = "normalize-1"

STRESS_MARK = "́"
# Soft hyphen, zero-width space, word joiner, byte-order mark. Zero-width (non-)joiners are kept:
# in this corpus they occur only inside Sinhala and Persian words, where they are meaningful.
INVISIBLE = re.compile("[­​⁠﻿]")
OTHER_SPACES = re.compile("[    ]")
REPEATED_SPACES = re.compile(" {2,}")
SPACE_BEFORE_PUNCTUATION = re.compile(r" +(?=[,.;:])")
WORD = re.compile(r"[A-Za-zЀ-ӿ]+")

LATIN_LOOKALIKES = "aceopxyABCEHKMOPTX"
CYRILLIC_TWINS = "асеорхуАВСЕНКМОРТХ"
TO_CYRILLIC = str.maketrans(LATIN_LOOKALIKES, CYRILLIC_TWINS)
ROMAN_NUMERAL = re.compile("[IVXLCDMХ]+")  # the last letter is Cyrillic Х, often typed in numerals


def is_cyrillic(char: str) -> bool:
    return "Ѐ" <= char <= "ӿ"


def fix_mixed_script(word: str) -> str:
    """Fix a word that mixes Latin and Cyrillic letters, but only in the two safe cases."""
    if not (any(is_cyrillic(c) for c in word) and any(c.isascii() for c in word)):
        return word
    if ROMAN_NUMERAL.fullmatch(word):
        return word.replace("Х", "X")
    if all(c in LATIN_LOOKALIKES for c in word if c.isascii()):
        return word.translate(TO_CYRILLIC)
    return word  # palochka-like I, glued words, typos: left for a human


def normalize_text(text: str, changes: Counter, fixes: list[list[str]]) -> str:
    """Apply every rule in order, counting how often each one changed something."""
    nfc = unicodedata.normalize("NFC", text)
    changes["nfc"] += nfc != text
    text = nfc

    changes["stress marks removed"] += text.count(STRESS_MARK)
    text = text.replace(STRESS_MARK, "")

    text, n = INVISIBLE.subn("", text)
    changes["invisible characters removed"] += n
    text, n = OTHER_SPACES.subn(" ", text)
    changes["special spaces replaced"] += n

    def fix(match: re.Match) -> str:
        fixed = fix_mixed_script(match.group())
        if fixed != match.group():
            fixes.append([match.group(), fixed])
            changes["mixed-script words fixed"] += 1
        return fixed

    text = WORD.sub(fix, text)

    text, n = REPEATED_SPACES.subn(" ", text)
    changes["repeated spaces collapsed"] += n
    text, n = SPACE_BEFORE_PUNCTUATION.subn("", text)
    changes["spaces before punctuation removed"] += n
    return text.strip()


def normalize_file(extracted: Path, out_dir: Path) -> tuple[Path, Counter, list[list[str]]]:
    """Normalize every article in an extract output; skip if this input was already normalized by this version."""
    out = out_dir / f"{extracted.name.removesuffix('.jsonl')}.{STAGE_VERSION}.jsonl"
    totals: Counter = Counter()
    all_fixes: list[list[str]] = []
    if out.exists():
        totals["skipped (already normalized)"] = 1
        return out, totals, all_fixes

    out_dir.mkdir(parents=True, exist_ok=True)
    partial = out.with_name(out.name + ".part")
    with extracted.open(encoding="utf-8") as source, partial.open("w", encoding="utf-8") as target:
        for line in source:
            record = json.loads(line)
            changes: Counter = Counter()
            fixes: list[list[str]] = []
            for section in record["sections"]:
                if section["heading"] is not None:
                    section["heading"] = normalize_text(section["heading"], changes, fixes)
                section["paragraphs"] = [normalize_text(p, changes, fixes) for p in section["paragraphs"]]
            record["stage_versions"] = {"extract": record.pop("stage_version"), "normalize": STAGE_VERSION}
            record["normalize_changes"] = {rule: n for rule, n in sorted(changes.items()) if n}
            record["mixed_script_fixes"] = fixes
            target.write(json.dumps(record, ensure_ascii=False) + "\n")
            totals.update(changes)
            totals["articles"] += 1
            all_fixes += fixes
    partial.replace(out)
    return out, totals, all_fixes
