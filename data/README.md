---
license: cc-by-sa-4.0
language:
- en
- ja
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
- config_name: 20260901.ja
  data_files:
  - split: train
    path: 20260901.ja/train-*
---

# Geotagged Wikipedia

Every Wikipedia article that carries coordinates, with its text.

    from datasets import load_dataset
    ds = load_dataset("yuiseki/wikipedia-geotagged", "20260901.en")
    ds = load_dataset("yuiseki/wikipedia-geotagged", "20260901.ja")

| subset | articles | characters | share of the wiki |
|---|---|---|---|
| `20260901.en` | 1,374,056 | 4,331,110,851 | 19.0% of 7,235,024 |
| `20260901.ja` | 218,496 | 435,046,691 | 14.4% of 1,516,331 |

Subsets are named `{dump}.{lang}`, as in
[`wikimedia/wikipedia`](https://huggingface.co/datasets/wikimedia/wikipedia).
A later dump or another language is added beside the existing ones rather than
replacing them, so a result stays reproducible after the next dump lands.

The first four columns are `id`, `url`, `title` and `text`, in that order and
under those names, so that anything written for `wikimedia/wikipedia` works
here unchanged. Everything after them is geography.

[`yuiseki/wikivoyage-geotagged`](https://huggingface.co/datasets/yuiseki/wikivoyage-geotagged)
is the same thing built from Wikivoyage by the same code, with the same
columns. They concatenate.

Code: https://github.com/yuiseki/wikipedia-geotagged

## What `geo_tags` is, and why it deserves to be better known

MediaWiki's GeoData extension keeps a table called `geo_tags`. Every time an
article carries a `{{coord}}` template, a row lands there with the coordinates,
a type, a rough size, and often an ISO country code. It ships in the public
dumps as a small file, 53 MB for English and 6 MB for Japanese, and almost
nobody seems to use it.

It is the cleanest answer to "which articles are about a place". No text
classification, no heuristics, no model: the editors already said so, one
`{{coord}}` at a time.

## Columns

| Column | |
|---|---|
| `id` | page id, as a string, like upstream |
| `url` | the article's URL |
| `title` | |
| `text` | the article, wikitext flattened to prose |
| `qid` | Wikidata item, from `page_props` |
| `lat`, `lon` | from the primary tag |
| `gt_type` | `city`, `landmark`, `mountain`, `adm1st`, and so on |
| `gt_globe` | `earth`, and also `moon`, `mars`, `venus`, `mercury`, `titan` |
| `gt_dim` | roughly how large the thing is, in metres |
| `gt_country` | ISO 3166-1 |
| `gt_region` | ISO 3166-2 subdivision |
| `gt_name` | a name the tag carries, often the formal one. `Alabama` is tagged `State of Alabama` |
| `gt_primary` | whether this tag is the article's own location |
| `tags` | every tag on the page, not only the primary one |

Nothing here restates what can be computed. There is no character count, no
language column, no licence column, and no `instance_of`: the first two are
`len(text)` and the name of the subset, and the last is a join away on `qid`.
`url` is the exception, kept because upstream has it.

### The two wikis fill it in differently

Per article, counting the primary tag:

| | `20260901.en` | `20260901.ja` |
|---|---|---|
| with a Wikidata id | 99.9% | 99.1% |
| `gt_type` missing | 57.6% | 25.2% |
| `gt_country` set | 54.2% | 73.8% |
| `gt_region` set | 18.7% | 26.6% |
| `gt_name` set | 2.8% | 14.0% |
| primary tag not on Earth | 3,306 | 303 |

Japanese Wikipedia is the more careful of the two: two thirds of its articles
carry a type where English manages under a half. Filtering by `gt_type` is
therefore a different proposition in each subset, and neither is reliable on
its own. Note also that 300 Japanese articles are typed `admin2nd`, which is a
misspelling of `adm2nd`; a filter written from the documented list misses them.

### Why `tags` is an array

A page can carry several coordinates. The primary one is where the article's
subject is; the others are places it mentions. 42,269 English pages have two
tags and 6,520 have three. The top-level `lat`, `lon` and `gt_*` columns are
the primary tag, and `tags` keeps all of them.

## What is here that is not a place

This takes everything `geo_tags` lists, mechanically, and leaves the filtering
to you. Wikipedia attaches coordinates to more than places.

**6.1% of the English articles are not places at all.** `Apollo 11`,
`Alexander the Great`, `Alfred Nobel`, `American National Standards
Institute`. Their coordinates are a landing site, a birthplace, a
headquarters. These are the articles whose `qid` is not in
`wikidata-gazetteer`.

**Organisations rank high.** Sorted by how many other geotagged articles link
to them, the English leaders are `National Park Service` 80,126, `United
States Geological Survey` 47,487, `2020 United States census` 44,544 and
`United States Department of the Interior` 38,299. None is a place. Every
American settlement article cites them by template.

**Some tags are not on Earth**: mostly the moon and Mars, but also Ganymede,
Enceladus and Itokawa. Filter on `gt_globe` if you want this planet only.

### Filtering

By globe, which is exact:

    SELECT * FROM train WHERE gt_globe = 'earth'

By type, which is not, and which differs between the subsets:

    SELECT * FROM train WHERE gt_type IN ('city','adm1st','adm2nd','admin2nd','adm3rd','isle')

By what Wikidata says the thing is, which is the reliable way. Join `qid`
against [`wikidata-gazetteer`](https://huggingface.co/datasets/yuiseki/wikidata-gazetteer)
and use its `instance_of`. That card lists the classes to exclude, including
the 729 languages Wikidata gives coordinates to and about 36,000 organisations.

## How dense in place names is it

Measured against the English names in `wikidata-gazetteer` with the languages
excluded, requiring a one-word name to have 100 sitelinks before it counts, on
a sample of 20,000 English articles:

| | wikipedia-geotagged | wikivoyage-geotagged |
|---|---|---|
| mentions per 1,000 characters | 5.46 | 3.85 |
| articles naming at least one place | 99.7% | 99.2% |
| distinct names, per 20,000 articles | 34,642 | 48,103 |
| one-word matches at a sentence start | 1.8% | 2.8% |

Densest of six corpora measured the same way, ahead of UN documents at 3.50,
Wikinews at 3.40, the OpenStreetMap Wiki at 1.32 and World Bank reports at
0.23. Not the most varied: a Wikivoyage article is three times longer and
names more distinct places, though fewer per character.

The last row is the measurement's own error bar. A single capitalised word at
the start of a sentence is where false positives gather, and 1.8% is the
lowest of the six; UN documents put 15.2% of their matches there.

The sitelinks floor is not a detail. Without it the same sample reads 10.62 per
1,000 characters and 11.8% at a sentence start, because `This`, `They` and
`Most` are all place names somewhere.

## What the text is

The current revision as of the dump, with wikitext flattened. Templates and
tables are unwrapped rather than removed, because an infobox carries facts the
prose does not repeat. A file link leaves its caption, which an editor wrote
and which often names a place the body does not. Galleries leave their
captions. References, comments, and blocks of music, mathematics or code are
dropped whole.

Some markup survives. Measured on the published text rather than on the dump:

| | `20260901.en` | `20260901.ja` |
|---|---|---|
| a stray `[[` or `]]` | 0.9% | 0.3% |
| an unclosed file link | 0.6% | 0.2% |
| a `\|thumb\|` or `\|NNNpx\|` run | 0.7% | 0.3% |
| a `style=` run | 0.2% | 1.4% |
| a stray `{{` | 0.0% | 0.0% |

Before these were fixed the first three stood at 96.3%, 55.6% and 55.3% in
English. `provenance.yaml` records what each defect was.

## What is not here

English and Japanese. `geo_tags` exists for every language edition and the
same code would build them.

Redirects are dropped, and so are pages outside the article namespace.
