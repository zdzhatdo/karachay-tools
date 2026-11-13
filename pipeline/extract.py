"""Stage 2 (extract): stored Wikipedia dump -> plain-text articles with titles, sections, and paragraphs."""

import bz2
import json
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import mwparserfromhell

STAGE_VERSION = "extract-1"
DROPPED_TAGS = {"ref", "references", "gallery", "math", "table", "syntaxhighlight", "timeline", "score"}
FILE_NAMESPACE, CATEGORY_NAMESPACE = 6, 14


def link_prefixes(namespaces: dict[int, str]) -> tuple[str, ...]:
    """Lowercase prefixes of links that are files or categories, not text ("Файл:", "Category:", ...)."""
    names = {namespaces.get(FILE_NAMESPACE, ""), namespaces.get(CATEGORY_NAMESPACE, ""), "file", "image", "category"}
    return tuple(f"{name.lower()}:" for name in names if name)


def plain_text(wikitext: str, drop_links: tuple[str, ...]) -> str:
    """Remove templates, citations, tables, files, and categories; keep the readable text."""
    code = mwparserfromhell.parse(wikitext)
    unwanted = [tag for tag in code.filter_tags() if str(tag.tag).strip().lower() in DROPPED_TAGS]
    unwanted += [link for link in code.filter_wikilinks() if str(link.title).strip().lower().startswith(drop_links)]
    for node in unwanted:
        try:
            code.remove(node)
        except ValueError:
            pass  # already removed together with an enclosing node
    return code.strip_code(normalize=True, collapse=True)


def sections(wikitext: str, drop_links: tuple[str, ...]) -> list[dict]:
    """Split an article into sections, each with its heading (None for the lead) and paragraphs."""
    result = []
    for section in mwparserfromhell.parse(wikitext).get_sections(flat=True, include_lead=True):
        headings = section.filter_headings(recursive=False)
        heading = plain_text(str(headings[0].title), drop_links).strip() if headings else None
        if headings:
            section.remove(headings[0])
        paragraphs = [line.strip() for line in plain_text(str(section), drop_links).splitlines() if line.strip()]
        if paragraphs:
            result.append({"heading": heading, "paragraphs": paragraphs})
    return result


def read_pages(dump: Path) -> Iterator[tuple[dict[int, str], ET.Element]]:
    """Stream <page> elements from a .xml.bz2 dump, with the dump's namespace names."""
    namespaces: dict[int, str] = {}
    with bz2.open(dump, "rb") as file:
        for _, elem in ET.iterparse(file, events=("end",)):
            if elem.tag.endswith("}namespace"):
                namespaces[int(elem.get("key"))] = elem.text or ""
            elif elem.tag.endswith("}page"):
                yield namespaces, elem
                elem.clear()


def extract_dump(dump: Path, out_dir: Path) -> tuple[Path, Counter]:
    """Write one JSON line per article to out_dir; skip if this input was already extracted by this version."""
    source_sha256 = dump.name.split(".")[0]
    out = out_dir / f"{source_sha256}.{STAGE_VERSION}.jsonl"
    stats: Counter = Counter()
    if out.exists():
        stats["skipped (already extracted)"] = 1
        return out, stats

    out_dir.mkdir(parents=True, exist_ok=True)
    partial = out.with_name(out.name + ".part")
    with partial.open("w", encoding="utf-8") as file:
        for namespaces, page in read_pages(dump):
            if page.findtext("{*}ns") != "0":
                stats["skipped: not an article"] += 1
                continue
            if page.find("{*}redirect") is not None:
                stats["skipped: redirect"] += 1
                continue
            wikitext = page.findtext("{*}revision/{*}text") or ""
            article_sections = sections(wikitext, link_prefixes(namespaces))
            if not article_sections:
                stats["skipped: no text after extraction"] += 1
                continue
            templates = sorted({str(t.name).strip().lower() for t in mwparserfromhell.parse(wikitext).filter_templates()})
            record = {
                "page_id": int(page.findtext("{*}id")),
                "rev_id": int(page.findtext("{*}revision/{*}id")),
                "title": page.findtext("{*}title"),
                "sections": article_sections,
                "templates": templates,
                "source_sha256": source_sha256,
                "stage_version": STAGE_VERSION,
            }
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
            stats["articles"] += 1
    partial.replace(out)
    return out, stats
