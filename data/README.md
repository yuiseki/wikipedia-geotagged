---
license: cc-by-sa-4.0
language:
- en
size_categories:
- 1M<n<10M
task_categories:
- text-generation
- fill-mask
tags:
- wikipedia
- geography
- geotagged
- coordinates
- gazetteer
pretty_name: Geotagged Wikipedia
configs:
- config_name: 20260901.en
  data_files:
  - split: train
    path: 20260901.en/train-*
---

# Geotagged Wikipedia

Every English Wikipedia article that carries coordinates, with its text.

1,374,056 articles, 3,843,346,999 characters. Built from the
`20260901` dumps. The `page` table lists 1,374,075 geotagged articles; 19 of
them are not in the article dump, which is taken a little later.

    from datasets import load_dataset
    ds = load_dataset("yuiseki/wikipedia-geotagged", "20260901.en")

The subset is named `{dump}.{lang}`, as in `wikimedia/wikipedia`. A later dump
or another language is added beside this one rather than replacing it.

The first four columns are `id`, `url`, `title` and `text`, in that order and
under those names, so that anything written for
[`wikimedia/wikipedia`](https://huggingface.co/datasets/wikimedia/wikipedia)
works here unchanged. Everything after them is geography.

[`yuiseki/wikivoyage-geotagged`](https://huggingface.co/datasets/yuiseki/wikivoyage-geotagged)
is the same thing built from Wikivoyage by the same code, with the same
columns. The two concatenate.

Code: https://github.com/yuiseki/wikipedia-geotagged

## What `geo_tags` is, and why it deserves to be better known

MediaWiki's GeoData extension keeps a table called `geo_tags`. Every time an
article carries a `{{coord}}` template, a row lands there with the coordinates,
a type, a rough size, and often an ISO country code. It ships in the public
dumps as a 53 MB file, and almost nobody seems to use it.

It is the cleanest answer to "which articles are about a place". 1,411,568
English pages carry a coordinate; 1,374,075 of them are articles rather than
redirects, which is about a fifth of the encyclopedia. No text classification,
no heuristics, no model: the editors already said so, one `{{coord}}` at a
time.

| | |
|---|---|
| `geo_tags` file | 53 MB |
| pages with a coordinate | 1,411,568 |
| of those, articles and not redirects | 1,374,075 |
| with a Wikidata id | 99.9% |
| also in `wikidata-gazetteer` | 93.8% |

## Columns

| Column | |
|---|---|
| `id` | page id, as a string, like upstream |
| `url` | the article's URL |
| `title` | |
| `text` | the article, wikitext flattened to prose |
| `qid` | Wikidata item, from `page_props` |
| `lat`, `lon` | from the primary tag |
| `gt_type` | `city`, `landmark`, `mountain`, `adm1st`, and so on. Null on 57.5% |
| `gt_globe` | `earth`, and also `moon`, `mars`, `venus`, `mercury`, `titan` |
| `gt_dim` | roughly how large the thing is, in metres |
| `gt_country` | ISO 3166-1, set on 41.3% of tags |
| `gt_region` | ISO 3166-2 subdivision, set on 14.2% |
| `gt_name` | a name the tag carries, often the formal one. `Alabama` is tagged `State of Alabama` |
| `gt_primary` | whether this tag is the article's own location |
| `tags` | every tag on the page, not only the primary one |

Nothing here restates what can be computed. There is no character count, no
language column, no licence column, and no `instance_of`: the first two are
`len(text)` and the name of the dataset, and the last is a join away on `qid`.
`url` is the exception, kept because upstream has it.

### Why `tags` is an array

A page can carry several coordinates. The primary one is where the article's
subject is; the others are places it mentions. 44,477 pages have two tags and
7,173 have three. The top-level `lat`, `lon` and `gt_*` columns are the primary
tag, and `tags` keeps all of them.

## What is here that is not a place

This takes everything `geo_tags` lists, mechanically, and leaves the filtering
to you. Wikipedia attaches coordinates to more than places.

**6.1% are not places at all.** `Apollo 11`, `Alexander the Great`,
`Alfred Nobel`, `American National Standards Institute`. Their coordinates are
a landing site, a birthplace, a headquarters. These are the articles whose
`qid` is not in `wikidata-gazetteer`.

**Organisations rank high.** Sorted by how many other geotagged articles link
to them, the leaders are `National Park Service` 80,126, `United States
Geological Survey` 47,487, `2020 United States census` 44,544 and
`United States Department of the Interior` 38,299. None is a place. Every
American settlement article cites them by template.

**10,681 tags are not on Earth**: 4,911 on the moon, 3,145 on Mars, 1,222 on
Venus, 944 on Mercury, 459 on Titan and a handful elsewhere. Filter on
`gt_globe` if you want this planet only.

### Filtering

By globe, which is exact:

    SELECT * FROM articles WHERE gt_globe = 'earth'

By type, which is not: `gt_type` is null on 57.5% of articles, so this keeps far
less than it should.

    SELECT * FROM articles WHERE gt_type IN ('city','adm1st','adm2nd','adm3rd','isle')

By what Wikidata says the thing is, which is the reliable way. Join `qid`
against [`wikidata-gazetteer`](https://huggingface.co/datasets/yuiseki/wikidata-gazetteer)
and use its `instance_of`. That card lists the classes to exclude, including
the 729 languages Wikidata gives coordinates to and about 36,000 organisations.

## How dense in place names is it

Measured against the English names in `wikidata-gazetteer` with the languages
excluded, requiring a one-word name to have 100 sitelinks before it counts, on
a sample of 20,000 articles:

| | wikipedia-geotagged | wikivoyage-geotagged |
|---|---|---|
| mentions per 1,000 characters | 5.46 | 3.85 |
| articles naming at least one place | 99.7% | 99.2% |
| distinct names, per 20,000 articles | 34,642 | 48,103 |
| one-word matches at a sentence start | 1.8% | 2.8% |

Densest of six corpora measured the same way, ahead of UN documents at 3.50,
Wikinews at 3.40, the OpenStreetMap Wiki at 1.32 and World Bank reports at
0.23. Not the most varied: a
[Wikivoyage](https://huggingface.co/datasets/yuiseki/wikivoyage-geotagged)
article is three times longer and names more distinct places, though fewer per
character.

The last row is the measurement's own error bar. A single capitalised word at
the start of a sentence is where false positives gather, and 1.8% is the lowest
of the six; UN documents put 15.2% of their matches there. The measurement is
most trustworthy exactly where the corpus is densest.

The sitelinks floor is not a detail. Without it the same sample reads 10.62 per
1,000 characters and 11.8% at a sentence start, because `This`, `They` and
`Most` are all place names somewhere.

## What is not here

Only English. `geo_tags` exists for every language edition and the same code
would build them.

Redirects are dropped, and so are pages outside the article namespace.

The text is the current revision as of the dump, with wikitext flattened:
templates and tables are unwrapped rather than removed, because in some wikis
the content lives inside them.
