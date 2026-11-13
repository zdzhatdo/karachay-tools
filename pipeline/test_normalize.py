import json
from collections import Counter

from pipeline.normalize import fix_mixed_script, normalize_file, normalize_text


def test_normalize_text_applies_each_rule_and_counts_it():
    changes, fixes = Counter(), []
    text = " ab́c­​d  e , f "
    assert normalize_text(text, changes, fixes) == "abcd e, f"
    assert changes["stress marks removed"] == 1
    assert changes["invisible characters removed"] == 2
    assert changes["special spaces replaced"] == 1
    assert changes["spaces before punctuation removed"] == 1
    assert fixes == []


def test_zero_width_joiners_are_kept():
    assert normalize_text("a‌b‍c", Counter(), []) == "a‌b‍c"


def test_mixed_script_fixes_only_the_safe_cases():
    assert fix_mixed_script("Aзия") == "Азия"  # Latin A among Cyrillic letters
    assert fix_mixed_script("ХIХ") == "XIX"  # Roman numeral typed with Cyrillic Х
    assert fix_mixed_script("пIа") == "пIа"  # I has no Cyrillic twin here: left alone
    assert fix_mixed_script("Unitedсы") == "Unitedсы"  # glued words: left alone
    assert fix_mixed_script("Hello") == "Hello"  # Latin only
    assert fix_mixed_script("Азия") == "Азия"  # Cyrillic only


def test_normalize_file_records_lineage_changes_and_fixes(tmp_path):
    source = tmp_path / "abc.extract-1.jsonl"
    source.write_text(json.dumps({
        "page_id": 1, "rev_id": 2, "title": "T",
        "sections": [{"heading": "Aзия", "paragraphs": ["x́ ,y"]}],
        "templates": [], "source_sha256": "abc", "stage_version": "extract-1",
    }, ensure_ascii=False) + "\n", encoding="utf-8")

    out, totals, fixes = normalize_file(source, tmp_path / "out")
    record = json.loads(out.read_text(encoding="utf-8"))

    assert out.name == "abc.extract-1.normalize-1.jsonl"
    assert record["sections"] == [{"heading": "Азия", "paragraphs": ["x,y"]}]
    assert record["stage_versions"] == {"extract": "extract-1", "normalize": "normalize-1"}
    assert record["normalize_changes"] == {
        "mixed-script words fixed": 1, "spaces before punctuation removed": 1, "stress marks removed": 1}
    assert record["mixed_script_fixes"] == fixes == [["Aзия", "Азия"]]
    assert "stage_version" not in record


def test_normalize_file_is_idempotent(tmp_path):
    source = tmp_path / "abc.extract-1.jsonl"
    source.write_text(json.dumps({"sections": [], "stage_version": "extract-1"}) + "\n", encoding="utf-8")
    first, _, _ = normalize_file(source, tmp_path / "out")
    content = first.read_bytes()
    second, totals, _ = normalize_file(source, tmp_path / "out")

    assert second == first and second.read_bytes() == content
    assert totals == {"skipped (already normalized)": 1}
