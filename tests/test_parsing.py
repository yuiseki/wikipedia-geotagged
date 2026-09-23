"""Tests for reading MediaWiki SQL dumps.

The dumps put their values on the lines after `INSERT INTO ... VALUES`, not on
the same line, and they write an absent value as a bare NULL. Both cost time
here: a parser that split on INSERT found nothing, and one that decoded NULL as
text stored the string "NULL" for 57.5% of rows and hid that they had no type.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import geo_pages  # noqa: E402
import geo_graph  # noqa: E402
import closure  # noqa: E402


def test_geo_tuple_is_read_from_a_values_line():
    line = (b"(32506976,39009140,'earth',1,22.22466660,-159.54949951,"
            b"NULL,NULL,NULL,NULL,NULL,NULL,NULL),")
    m = geo_pages.GEO.search(line)
    assert m is not None
    assert int(m.group(2)) == 39009140      # page id
    assert m.group(4) == b"1"               # primary tag
    assert m.group(8) == b"NULL"            # no type


def test_a_typed_tag_keeps_its_type():
    line = b"(1,2,'earth',1,51.5,-0.12,NULL,'city',NULL,NULL,NULL,NULL,NULL),"
    m = geo_pages.GEO.search(line)
    assert m.group(8) == b"'city'"


def test_page_tuple_carries_namespace_and_redirect_flag():
    line = b"(12,0,'Anarchism',0,0,0.123,'20260101000000',NULL,1,50000,'wikitext',NULL),"
    m = geo_pages.PAGE.search(line)
    assert int(m.group(1)) == 12
    assert int(m.group(2)) == geo_pages.ARTICLE_NAMESPACE
    assert m.group(3) == b"Anarchism"
    assert m.group(4) == b"0"


def test_pagelinks_is_a_triple_now():
    """Links stopped being page-id pairs; the target moved to linktarget."""
    assert geo_graph.PAGELINK.search(b"(12345,0,67890)") is not None


def test_linktarget_gives_a_namespace_and_a_title():
    m = geo_graph.LINKTARGET.search(b"(99,0,'United_States')")
    assert int(m.group(1)) == 99
    assert int(m.group(2)) == 0
    assert m.group(3) == b"United_States"


def test_ancestors_stop_at_a_cycle():
    """Wikidata is edited by people, so a containment chain can loop."""
    parents = {"A": {"B"}, "B": {"C"}, "C": {"A"}}
    seen, frontier = set(), {"A"}
    for _ in range(12):
        nxt = set()
        for node in frontier:
            for p in parents.get(node, ()):
                if p in seen or p == "A":
                    continue
                seen.add(p); nxt.add(p)
        if not nxt:
            break
        frontier = nxt
    assert seen == {"B", "C"}


def test_two_page_ids_pack_into_one_integer():
    import compare_hierarchy
    assert compare_hierarchy.pack(1, 2) != compare_hierarchy.pack(2, 1)
    assert compare_hierarchy.pack(39009140, 12) == (39009140 << 32) | 12


def test_the_card_names_the_file_that_is_uploaded():
    """data_files in the card has to be the path publish.py writes to.

    They are set in different files, so nothing but a test connects them. Get
    it wrong and the dataset viewer finds no data while every upload succeeds.
    """
    import re
    import publish

    base = os.path.join(os.path.dirname(__file__), "..")
    card = open(os.path.join(base, "data/README.md"), encoding="utf-8").read()
    declared = re.search(r"^\s*data_files:\s*(\S+)\s*$", card, re.M)
    assert declared, "the card declares no data_files"
    assert declared.group(1) == publish.PATH_IN_REPO


def test_templates_and_tables_are_unwrapped_not_removed():
    """The cleaner keeps what is inside braces and pipes.

    A cleaner that deletes templates deletes the facts: an infobox is often
    the only place an article states a population or an elevation.
    """
    import wikitext

    out = wikitext.clean("{{Tag|railway|station}} is a [[railway station]].")
    assert "railway=station" in out
    assert "railway station" in out
    assert "{{" not in out and "[[" not in out
