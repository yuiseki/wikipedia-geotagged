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


def test_the_card_declares_every_subset_that_exists():
    """The configs in the card have to be the directories publish.py writes.

    They are set in different files, so nothing but a test connects them. Get
    it wrong and the dataset viewer finds no data while every upload succeeds.
    Following wikimedia/wikipedia, a subset is named {dump}.{lang} and its
    files are {dump}.{lang}/train-*.
    """
    import re
    import publish

    base = os.path.join(os.path.dirname(__file__), "..")
    card = open(os.path.join(base, "data/README.md"), encoding="utf-8").read()
    names = re.findall(r"^- config_name: (\S+)$", card, re.M)
    paths = re.findall(r"^    path: (\S+)$", card, re.M)
    assert names, "the card declares no configs"
    assert len(names) == len(paths)
    for name, path in zip(names, paths):
        assert re.fullmatch(r"\d{8}\.[a-z-]+", name), name
        assert path == publish.subset_glob(name), (name, path)


def test_shards_are_named_the_way_the_hub_expects():
    import publish

    assert publish.shard_name(0, 1) == "train-00000-of-00001.parquet"
    assert publish.shard_name(3, 41) == "train-00003-of-00041.parquet"
    assert publish.subset_glob("20260901.en") == "20260901.en/train-*"


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


def test_a_dump_escape_is_undone_in_titles_and_names():
    """The dumps escape quotes and backslashes; the value is not the raw bytes.

    Found on Wikivoyage, whose first geotagged page is 's-Hertogenbosch and
    came out as \\'s-Hertogenbosch. 216 of its 29,505 titles carry an escape.
    Wikipedia hides this: its geo_pages title is only used for reporting, and
    the published title comes from the XML dump instead.
    """
    line = rb"(10,0,'\'s-Hertogenbosch',0,0,0.922237949364,'20260828224346',"
    m = geo_pages.PAGE.search(line)
    assert m
    assert geo_pages.unescape(m.group(3)) == b"'s-Hertogenbosch"


def test_unquote_undoes_escapes_too():
    assert geo_pages.unquote(rb"'Coeur d\'Alene'") == "Coeur d'Alene"
    assert geo_pages.unquote(rb"'a\\b'") == "a\\b"
    assert geo_pages.unquote(b"NULL") is None


def test_only_the_outer_quotes_come_off():
    """strip() takes every quote at the ends, not the one that delimits.

    A value ending in an escaped quote ends in backslash, quote, quote: the
    delimiter and the escaped character look the same to strip, which ate the
    escaped one and left its backslash. It survived the first fix of this bug
    and showed up as USS ''S-37'\\ in 225 of 1,374,056 records.
    """
    assert geo_pages.unquote(rb"'USS \'\'S-37\'\''") == "USS ''S-37''"
    assert geo_pages.unquote(rb"''") is None
    assert geo_pages.unquote(rb"'Paris'") == "Paris"


def test_a_file_link_leaves_its_caption_and_nothing_else():
    """A file link has more than one pipe, which the old pattern never matched.

    [[File:X.jpg|thumb|220px|A caption]] survived whole into the text, so 55.6%
    of English articles and 71.0% of Japanese ones carried image markup as
    prose. The caption is worth keeping: it is written by an editor and names
    places the body sometimes does not.
    """
    import wikitext

    out = wikitext.clean(
        "[[File:Dogo.JPG|thumb|220px|3000年の歴史を有する道後温泉の本館]] です。")
    assert "道後温泉の本館" in out
    assert "thumb" not in out and "220px" not in out
    assert "[[" not in out and "]]" not in out and ".JPG" not in out


def test_a_file_link_with_no_caption_leaves_nothing():
    import wikitext

    out = wikitext.clean("[[ファイル:Flag of Matsuyama.svg|100px]] 松山市の旗")
    assert "松山市の旗" in out
    assert "Flag of Matsuyama" not in out and "100px" not in out


def test_a_plain_link_keeps_its_label():
    import wikitext

    assert wikitext.clean("[[Ehime Prefecture|Ehime]] is warm.").startswith("Ehime is warm")
    assert wikitext.clean("[[Matsuyama]] is a city.").startswith("Matsuyama is a city")


def test_a_link_inside_a_caption_is_unwrapped_too():
    """Captions contain links, so one pass is not enough."""
    import wikitext

    out = wikitext.clean("[[File:X.jpg|thumb|The [[Dogo Onsen|onsen]] at night]]")
    assert out.strip() == "The onsen at night"


def test_table_attributes_do_not_become_prose():
    import wikitext

    out = wikitext.clean('{{Infobox|style="width:280px; margin:2px auto"|name=Matsuyama}}')
    assert "width:280px" not in out and "style" not in out


def test_a_template_containing_a_table_does_not_leak_its_attributes():
    """The innermost-template pattern cannot cross a brace, and a table opens
    with one. An infobox holding a table was therefore never unwrapped, and its
    raw markup reached the text: every Japanese city article began with
    style="width:280px; margin:2px auto".
    """
    import wikitext

    out = wikitext.clean(
        '{{Infobox\n|image=\n{|style="width:280px"\n|-\n|A caption\n|}\n'
        '|name=Matsuyama\n}}\n松山市（まつやまし）は、愛媛県の中部に位置する市である。')
    assert "松山市（まつやまし）は、愛媛県の中部に位置する市である。" in out
    assert "width:280px" not in out
    assert "style=" not in out


def test_a_reference_leaves_nothing_whatever_its_shape():
    import wikitext

    for ref in ('<ref name="a">Some source</ref>',
                '<ref name="19940617-notification-04" />',
                '<ref>Plain</ref>'):
        out = wikitext.clean(f"御蔵島村は、東京都の島嶼部に位置する村。{ref}")
        assert out.startswith("御蔵島村は、東京都の島嶼部に位置する村。"), (ref, out)
        assert "19940617" not in out and "Some source" not in out


def test_a_self_closing_reference_does_not_swallow_the_article():
    """<ref name="x" /> matches <ref[^>]*>, and the search for </ref> then runs
    past everything between. 御蔵島村's opening sentence disappeared this way:
    a self-closing ref in the infobox ate the text up to the next real
    reference, several hundred characters later.
    """
    import wikitext

    out = wikitext.clean(
        '告示第4号<ref name="notice-04" />\n\n'
        "'''御蔵島村'''（みくらじまむら）は、[[東京都]]の[[東京都島嶼部|島嶼部]]に位置する[[村]]。"
        "<ref>出典</ref>")
    assert "御蔵島村（みくらじまむら）は、東京都の島嶼部に位置する村。" in out
    assert "notice-04" not in out and "出典" not in out


def test_a_link_inside_a_template_argument_survives_the_split():
    """Templates are split on the pipe, and so is a link inside one.

    [[Yellowhammer|Yellowhammer]] State in an infobox argument came out as
    "Yellowhammer]] State", which is where nearly every stray bracket in the
    corpus came from. Links have to be unwrapped before the split.
    """
    import wikitext

    out = wikitext.clean(
        "{{Infobox\n|nickname=The [[Yellowhammer (bird)|Yellowhammer]] State, "
        "the Heart of Dixie\n}}\nAlabama is a state.")
    assert "]]" not in out and "[[" not in out
    assert "Yellowhammer State" in out


def test_a_reference_inside_a_template_leaves_nothing():
    import wikitext

    out = wikitext.clean(
        '{{Infobox|紋章=1994年4月1日制定<ref name="19940617-notification-04">'
        "御蔵島村の紋章及び木に関する告示 平成6年6月17日 告示第4号</ref>}}\n本文。")
    assert "19940617" not in out
    assert "告示第4号" not in out


def test_a_table_written_with_magic_word_templates_is_read_as_a_table():
    """{{(!}} is {|, {{!}} is |, {{!!}} is ||. Japanese city infoboxes build
    their image montage this way. Unwrapping them as ordinary templates threw
    away the pipes and left style="width:280px" standing as prose, which is
    how every 市 article came to start with a CSS declaration.
    """
    import wikitext

    out = wikitext.clean(
        '{{(!}} style="width:280px; margin:2px auto"\n'
        '{{!}} style="width:50%"{{!}}[[道後温泉]]{{!!}}[[正岡子規]]歌碑\n'
        "{{!-}}\n{{!}}[[松山城]]天守\n{{!)}}")
    assert "width:280px" not in out and "style" not in out
    assert "道後温泉" in out and "松山城天守" in out


def test_a_bare_attribute_run_is_not_prose():
    import wikitext

    assert wikitext.clean('style="vertical-align:middle"\n本文です。').strip() == "本文です。"


def test_unquoted_cell_attributes_come_off_too():
    """The old pattern required every attribute in the run to be quoted, so
    colspan="2" data-sort-type=number |Alone kept the whole run as prose.
    """
    import wikitext

    out = wikitext.clean('{|\n|-\n|colspan="2" data-sort-type=number |Alone\n|}')
    assert out.strip() == "Alone"


def test_a_table_caption_keeps_only_the_caption():
    import wikitext

    out = wikitext.clean('{|\n|+ style="font-size:90%" |Racial composition\n|}')
    assert out.strip() == "Racial composition"


def test_templates_are_unwrapped_however_deep_they_nest():
    import wikitext

    out = wikitext.clean("{{a|{{b|{{c|{{d|{{e|{{as of|2023|February|}}}}}}}}}}}}, there are voters.")
    assert "{{" not in out and "}}" not in out


def test_a_template_ending_in_an_empty_argument_is_not_a_table():
    """{{as of|2023|February|}} ends in |}, which is also how a table closes.

    Hiding the table markers while templates unwrap broke this: the template
    lost its closing brace to the disguise and survived whole. MediaWiki only
    reads {| and |} at the start of a line, so that is where they are hidden.
    """
    import wikitext

    out = wikitext.clean("{{as of|2023|February|}}, there are voters.")
    assert out.strip() == ", there are voters."


def test_a_template_in_a_caption_is_not_split_by_the_caption_split():
    """A link body is split on the pipe, and a template inside it has pipes.

    [[File:X.jpg|thumb|200px|[[ヒメツリガネゴケ]] {{Snamei||Physcomitrium patens}}
    の原糸体。]] lost its {{Snamei and kept the closing braces, which is where
    13.3% of Japanese articles got a stray }} from.
    """
    import wikitext

    out = wikitext.clean(
        "[[File:P.jpg|thumb|200px|[[ヒメツリガネゴケ]] {{Snamei||Physcomitrium patens}}"
        " の[[原糸体]]。]]\nコケ植物の配偶体は。")
    assert "}}" not in out and "{{" not in out
    assert "原糸体" in out


def test_a_lone_brace_inside_a_template_does_not_stop_it_matching():
    """{{chem2|C_{n}H_{2n+2} }} has single braces, and a pattern that forbids
    every brace could not cross them, so the template survived as prose.
    """
    import wikitext

    out = wikitext.clean("Alkanes have the formula {{chem2|C_{n}H_{2n+2} }}. Single bonds.")
    assert "{{" not in out and "}}" not in out
    assert out.strip().startswith("Alkanes have the formula")


def test_non_prose_blocks_are_dropped_whole():
    """Music, formulae and code are not sentences, and their braces confuse
    everything downstream. An American in Paris put a page of LilyPond into
    the corpus this way.
    """
    import wikitext

    for tag in ("score", "math", "syntaxhighlight", "timeline", "nowiki"):
        out = wikitext.clean(f"Before. <{tag}>{{ \\tempo 4 = 96 }}</{tag}> After.")
        assert out.strip() == "Before. After.", (tag, out)


def test_a_gallery_keeps_its_captions_and_drops_its_filenames():
    import wikitext

    out = wikitext.clean(
        "<gallery>\nFile:Matsuyama.jpg|松山城の天守\nFile:Dogo.jpg|道後温泉\n</gallery>")
    assert "松山城の天守" in out and "道後温泉" in out
    assert ".jpg" not in out and "File:" not in out


def test_a_gallery_caption_that_is_a_link_keeps_its_bracket_pair():
    """split_pipes counted braces and not brackets, so File:X.jpg|[[Hoggar]]
    was split inside the link and left Hoggar]] in the text.
    """
    import wikitext

    out = wikitext.clean(
        "<gallery>\nFile:Hoggar.jpg|[[Hoggar]]\n"
        "File:A.jpg|[[Aristotle]] by [[Jusepe de Ribera|Ribera]]\n</gallery>")
    assert "]]" not in out and "[[" not in out
    assert "Hoggar" in out and "Aristotle by Ribera" in out
