import bz2
import json

from pipeline.extract import extract_dump, plain_text, sections

LINKS = ("file:", "category:")


def test_plain_text_keeps_prose_and_link_text_only():
    wikitext = (
        "{{Infobox|name=X}}Alpha [[Beta|beta link]] gamma.<ref>Source title, 1999.</ref>"
        "<ref>{{cite web|url=http://x}}</ref>\n"
        "[[File:x.jpg|thumb|caption]]\n{| class=wikitable\n| cell\n|}\n[[Category:Things]]"
    )
    assert plain_text(wikitext, LINKS).split() == ["Alpha", "beta", "link", "gamma."]


def test_sections_keep_headings_and_drop_empty_sections():
    wikitext = "Lead text.\n\n== First ==\nOne.\nTwo.\n\n== Empty ==\n{{only a template}}\n"
    assert sections(wikitext, LINKS) == [
        {"heading": None, "paragraphs": ["Lead text."]},
        {"heading": "First", "paragraphs": ["One.", "Two."]},
    ]


def make_dump(path):
    xml = """<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">
  <siteinfo><namespaces><namespace key="6">File</namespace><namespace key="14">Category</namespace></namespaces></siteinfo>
  <page><title>Article</title><ns>0</ns><id>1</id><revision><id>10</id><text>Some text. {{Stub}}</text></revision></page>
  <page><title>Old name</title><ns>0</ns><id>2</id><redirect title="Article" /><revision><id>20</id><text>#REDIRECT [[Article]]</text></revision></page>
  <page><title>Template:Stub</title><ns>10</ns><id>3</id><revision><id>30</id><text>stub box</text></revision></page>
  <page><title>Empty</title><ns>0</ns><id>4</id><revision><id>40</id><text>{{Infobox}}</text></revision></page>
</mediawiki>"""
    path.write_bytes(bz2.compress(xml.encode("utf-8")))


def test_extract_dump_writes_articles_with_provenance_and_counts_skips(tmp_path):
    dump = tmp_path / "abc123.xml.bz2"
    make_dump(dump)
    out, stats = extract_dump(dump, tmp_path / "out")

    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert records == [{
        "page_id": 1, "rev_id": 10, "title": "Article",
        "sections": [{"heading": None, "paragraphs": ["Some text."]}],
        "templates": ["stub"], "source_sha256": "abc123", "stage_version": "extract-1",
    }]
    assert stats == {"articles": 1, "skipped: redirect": 1, "skipped: not an article": 1,
                     "skipped: no text after extraction": 1}


def test_extract_dump_is_idempotent(tmp_path):
    dump = tmp_path / "abc123.xml.bz2"
    make_dump(dump)
    first, _ = extract_dump(dump, tmp_path / "out")
    content = first.read_bytes()
    second, stats = extract_dump(dump, tmp_path / "out")

    assert second == first and second.read_bytes() == content
    assert stats == {"skipped (already extracted)": 1}
