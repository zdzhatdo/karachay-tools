"""Stage 4 (langid): tag every paragraph as krc, rus, or other.

Only tags; nothing is removed. Later stages decide what to do with non-krc text, e.g. keep Russian citations
out of coverage. Accuracy was measured on hand-labeled samples: see eval/langid_eval.py.
"""

import hashlib
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path

STAGE_VERSION = "langid-1"
# This stage version is tied to one exact model file: GlotLID v4 (Apache 2.0 plus notices).
MODEL_URL = (
    "https://huggingface.co/cis-lmu/glotlid/resolve/e9592e0a9bc3b6f2a946de94faaa188d1dd6f522/model_v4.bin"
)
MODEL_SHA256 = "3b26297652e105cb63acde0fbf5aa228161528b519331e58a7c94ea9fe58474c"
# Below this many characters the model often mistakes krc for a related Turkic language.
SHORT = 40

Predict = Callable[[str], tuple[str, float]]


def to_label(text: str, code: str) -> tuple[str, bool]:
    """Map a GlotLID code to krc/rus/other. Also return whether the short-line rule decided it."""
    if code == "krc_Cyrl":
        return "krc", False
    if code == "rus_Cyrl":
        return "rus", False
    if len(text) < SHORT and code.endswith("_Cyrl"):
        return "krc", True
    return "other", False


def load_glotlid(path: Path) -> Predict:
    """Load the pinned GlotLID model, refusing any other file."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    if digest.hexdigest() != MODEL_SHA256:
        raise ValueError(f"{path} is not the pinned GlotLID model (sha256 {digest.hexdigest()})")

    import fasttext  # optional dependency (the "langid" extra); tests never need it

    model = fasttext.load_model(str(path))

    def predict(text: str) -> tuple[str, float]:
        (code,), (probability,) = model.predict(text.replace("\n", " "))
        return code.removeprefix("__label__"), round(float(probability), 4)

    return predict


def langid_file(normalized: Path, out_dir: Path, load: Callable[[], Predict]) -> tuple[Path, Counter]:
    """Tag every paragraph of a normalize output. The model is loaded only if there is work to do."""
    out = out_dir / f"{normalized.name.removesuffix('.jsonl')}.{STAGE_VERSION}.jsonl"
    totals: Counter = Counter()
    if out.exists():
        totals["skipped (already tagged)"] = 1
        return out, totals

    predict = load()
    out_dir.mkdir(parents=True, exist_ok=True)
    partial = out.with_name(out.name + ".part")
    with normalized.open(encoding="utf-8") as source, partial.open("w", encoding="utf-8") as target:
        for line in source:
            record = json.loads(line)
            for section in record["sections"]:
                section["langs"] = []
                for paragraph in section["paragraphs"]:
                    code, probability = predict(paragraph)
                    label, short_rule = to_label(paragraph, code)
                    section["langs"].append(
                        {"lang": label, "glotlid": code, "p": probability, "short_rule": short_rule})
                    totals[f"paragraphs {label}"] += 1
                    totals["short-line rule applied"] += short_rule
            record["stage_versions"]["langid"] = STAGE_VERSION
            target.write(json.dumps(record, ensure_ascii=False) + "\n")
            totals["articles"] += 1
    partial.replace(out)
    return out, totals
