"""Measure the langid stage against the hand-labeled samples.

Usage: python eval/langid_eval.py <path to GlotLID model_v4.bin>

Samples (paragraphs from the Karachay-Balkar Wikipedia, CC BY-SA 4.0; page IDs are in the files):
- langid-sample.txt: 150 random paragraphs (seed 20261114).
- langid-sample-literature.txt: 60 random paragraphs under the heading «Литература» (same seed), added
  because the random sample had too few Russian paragraphs to measure.
Labels were assigned by a native speaker. Lines labeled `name` (only names or terms) are left out.
Note: the short-line rule was chosen by looking at these same samples, so its numbers are optimistic.
"""

import sys
from collections import Counter
from pathlib import Path

from pipeline.langid import SHORT, load_glotlid, to_label

SAMPLES = [Path(__file__).parent / "langid-sample.txt", Path(__file__).parent / "langid-sample-literature.txt"]


def read_sample(path: Path) -> list[tuple[str, str]]:
    """Return (gold label, text) pairs from a sample file."""
    pairs = []
    for block in path.read_text(encoding="utf-8").split("\n\n")[1:]:
        if block.strip():
            _, label, text = block.split("\n", 2)
            pairs.append((label.removeprefix("label="), text.strip()))
    return pairs


def main() -> None:
    predict = load_glotlid(Path(sys.argv[1]))
    results: Counter = Counter()
    for path in SAMPLES:
        for gold, text in read_sample(path):
            if gold != "name":
                label, _ = to_label(text, predict(text)[0])
                length = "short" if len(text) < SHORT else "long"
                results[gold, length, label == gold] += 1

    print(f"{'gold':6}{'length':8}{'correct':>10}")
    for gold in ["krc", "rus", "other"]:
        for length in ["short", "long"]:
            right, wrong = results[gold, length, True], results[gold, length, False]
            if right + wrong:
                print(f"{gold:6}{length:8}{right:>5}/{right + wrong:<4} {right / (right + wrong):.0%}")


if __name__ == "__main__":
    main()
