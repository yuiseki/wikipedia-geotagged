# wikipedia-geotagged

Which English Wikipedia articles are about a place, their text, and how those
places are linked to one another.

Wikipedia's GeoData extension attaches coordinates to pages. 1,411,568 pages
carry one; 1,374,075 of those are articles rather than redirects. That is the
subset of Wikipedia that is about geography, and it is about a fifth of the
encyclopedia.

The corpus built from it is published as
[`yuiseki/wikipedia-geotagged`](https://huggingface.co/datasets/yuiseki/wikipedia-geotagged):
1,374,056 articles, 3.84 billion characters, with the coordinates alongside the
text. Its card is `data/README.md`.

## What is here

    src/geo_pages.py          joins geo_tags to page titles
    src/link_qids.py          attaches a Wikidata id to each article
    src/extract_text.py       pulls those articles' text out of the XML dump
    src/publish.py            writes the Parquet and pushes it to the Hub
    src/geo_graph.py          extracts the links between geographic articles
    src/closure.py            every ancestor of every place, not just the parent
    src/compare_hierarchy.py  links against hierarchy, three ways

Building the corpus is three steps:

    python3 src/geo_pages.py    --geo-tags enwiki-geo_tags.sql.gz --page enwiki-page.sql.gz --out geo_pages.jsonl
    python3 src/link_qids.py    --geo-pages geo_pages.jsonl --page-props enwiki-page_props.sql.gz --out geo_pages_qid.jsonl
    python3 src/extract_text.py --dump enwiki-pages-articles.xml.bz2 --geo-pages geo_pages_qid.jsonl --out corpus.jsonl.gz

The article dump is 25.7 GB of bzip2 and decompression is the whole cost, so
`extract_text.py` hands it to `lbzip2` and reads the stream.

## The dumps it reads

    enwiki-latest-geo_tags.sql.gz      53 MB   coordinates per page
    enwiki-latest-page.sql.gz         2.4 GB   page id to title
    enwiki-latest-page_props.sql.gz   471 MB   page id to Wikidata item
    enwiki-latest-pagelinks.sql.gz    7.1 GB   the links
    enwiki-latest-linktarget.sql.gz   1.4 GB   link target id to title

Links are no longer stored as pairs of page ids. `pagelinks` holds a target id
and `linktarget` maps that to a title, so resolving one means going through the
title and back into `page`.

## What the join gives

99.9% of the geographic articles carry a Wikidata id, which is a far better
join than matching titles as strings: that reached 52.8% and could not tell
`Alexander the Great` from a town.

93.8% of them are in `wikidata-gazetteer`. The 6.1% that are not are Wikipedia
tagging things that are not places, `Apollo 11` and `Alfred Nobel` among them.

What Wikipedia writes about is not what Wikidata holds. Its geographic articles
are villages 86,584, human settlements 77,771, villages of Poland 51,471,
railway stations 40,228, communes of France 37,488. Streets do not reach the top
twenty-two, although half a million of them have Wikidata items. Having an item
and being written about are different things.

## Links against hierarchy

121,024,111 links run between geographic articles. Wikidata states 4,284,033
containments between the same articles, counting every ancestor and the country,
not only the immediate parent.

| | | |
| --- | --- | --- |
| stated and linked | 2,673,075 | 62.4% of stated |
| stated but never linked | 1,610,958 | 37.6% |
| linked but not stated | 117,558,950 | 97.1% of links |

Taking ancestors rather than parents absorbed 1.75 million links, 1.5%, so the
surplus is not mostly an artefact of comparing one step against many. Deep
ancestors go unlinked more often than near ones: a village names its country
and skips the district.

What the surplus contains, read from a sample: real geography that containment
does not cover (`Muharraq Island` to `Persian Gulf`, `Rakautara` to `Kaikōura
Peninsula`), references between things of the same kind (one ballpark to
another), boilerplate (`Google Maps` 12,969 times), and noise. Separating them
is unfinished. Distance between the endpoints is the obvious next measure, since
both ends carry coordinates.

## A caution about what counts as geographic here

`geo_tags` lists anything with a coordinate, and the most linked-to entries are
`National Park Service` 80,126, `United States Geological Survey` 47,487 and
`2020 United States census` 44,544. None is a place. Every American settlement
article cites them by template. This is the same fault as the 36,000
organisations in `wikidata-gazetteer`, seen from the other side.

## Licence

Code is Apache-2.0. The dumps are CC BY-SA 4.0 from Wikipedia and are not
redistributed here; everything is reproducible from them.
