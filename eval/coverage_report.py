"""Report morphological coverage from Apertium stream output (krc-morph)."""

import re
import sys
from collections import Counter

# ^surface/analysis1/analysis2$ ; a backslash escapes special characters.
TOKEN = re.compile(r"(?<!\\)\^(.*?)(?<!\\)\$")
SLASH = re.compile(r"(?<!\\)/")
ESCAPE = re.compile(r"\\(.)")


def parse_tokens(stream: str) -> list[tuple[str, bool]]:
    """Return (surface, is_known) for every ^...$ token."""
    tokens = []
    for body in TOKEN.findall(stream):
        surface, *analyses = SLASH.split(body)
        is_known = bool(analyses) and not analyses[0].startswith("*")
        tokens.append((ESCAPE.sub(r"\1", surface), is_known))
    return tokens


def is_word(surface: str) -> bool:
    """True if the surface form contains at least one letter."""
    return any(char.isalpha() for char in surface)


def main() -> None:
    """Read the file named on the command line, then print the report."""
    with open(sys.argv[1], encoding="utf-8") as file:
        words = [(s.lower(), known) for s, known in parse_tokens(file.read()) if is_word(s)]

    unknown = Counter(surface for surface, known in words if not known)
    unknown_count = sum(unknown.values())
    types = {surface for surface, _ in words}

    print(f"words: {len(words)}")
    print(f"unknown: {unknown_count}")
    print(f"token coverage: {100 * (len(words) - unknown_count) / len(words):.1f}%")
    print(f"type coverage: {100 * (len(types) - len(unknown)) / len(types):.1f}%")
    print("top 20 unknown:")
    for surface, count in unknown.most_common(20):
        print(f"{count:>5}  {surface}")


if __name__ == "__main__":
    main()
