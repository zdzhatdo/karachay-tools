import json

import pytest

from pipeline.langid import langid_file, load_glotlid, to_label


def test_to_label_maps_codes_and_applies_the_short_line_rule():
    assert to_label("a long Karachay-Balkar paragraph, well over forty characters", "krc_Cyrl") == ("krc", False)
    assert to_label("Short Russian line", "rus_Cyrl") == ("rus", False)
    assert to_label("карталары", "tat_Cyrl") == ("krc", True)  # short Cyrillic, related language
    assert to_label("x" * 40, "tat_Cyrl") == ("other", False)  # 40 characters is no longer short
    assert to_label("New York Daily News", "eng_Latn") == ("other", False)  # short, but not Cyrillic


def test_langid_file_tags_every_paragraph_and_records_lineage(tmp_path):
    source = tmp_path / "abc.extract-1.normalize-1.jsonl"
    source.write_text(json.dumps({
        "title": "T",
        "sections": [{"heading": None, "paragraphs": ["one", "two"]}],
        "stage_versions": {"extract": "extract-1", "normalize": "normalize-1"},
    }) + "\n", encoding="utf-8")
    fake = {"one": ("krc_Cyrl", 0.9), "two": ("kir_Cyrl", 0.5)}

    out, totals = langid_file(source, tmp_path / "out", lambda: fake.__getitem__)
    record = json.loads(out.read_text(encoding="utf-8"))

    assert out.name == "abc.extract-1.normalize-1.langid-1.jsonl"
    assert record["sections"][0]["paragraphs"] == ["one", "two"]  # text is never changed
    assert record["sections"][0]["langs"] == [
        {"lang": "krc", "glotlid": "krc_Cyrl", "p": 0.9, "short_rule": False},
        {"lang": "krc", "glotlid": "kir_Cyrl", "p": 0.5, "short_rule": True},
    ]
    assert record["stage_versions"]["langid"] == "langid-1"
    assert totals == {"paragraphs krc": 2, "short-line rule applied": 1, "articles": 1}


def test_existing_output_is_skipped_without_loading_the_model(tmp_path):
    source = tmp_path / "abc.jsonl"
    source.write_text(json.dumps({"sections": [], "stage_versions": {}}) + "\n", encoding="utf-8")
    first, _ = langid_file(source, tmp_path / "out", lambda: None)
    content = first.read_bytes()

    def must_not_load():
        raise AssertionError("model loaded although output exists")

    second, totals = langid_file(source, tmp_path / "out", must_not_load)
    assert second == first and second.read_bytes() == content
    assert totals == {"skipped (already tagged)": 1}


def test_load_glotlid_refuses_a_file_that_is_not_the_pinned_model(tmp_path):
    fake_model = tmp_path / "model.bin"
    fake_model.write_bytes(b"not the model")
    with pytest.raises(ValueError, match="not the pinned GlotLID model"):
        load_glotlid(fake_model)
