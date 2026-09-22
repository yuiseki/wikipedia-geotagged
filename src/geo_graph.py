#!/usr/bin/env python3
"""The links between geographic Wikipedia articles.

MediaWiki no longer stores a link as a pair of page ids. `pagelinks` holds
`pl_from` and `pl_target_id`, and `linktarget` maps that target id to a
namespace and a title, so resolving a link means going through the title and
back into `page`. Redirects are followed, because an article linking to
"USA" is linking to the United States.

Only links where both ends are geographic articles are kept. Everything else
is the rest of Wikipedia.
"""
import argparse
import collections
import gzip
import json
import re
import sys

PAGELINK = re.compile(rb"\((\d+),(\d+),(\d+)\)")
LINKTARGET = re.compile(rb"\((\d+),(\d+),'((?:[^'\\]|\\.)*)'\)")
REDIRECT = re.compile(rb"\((\d+),(\d+),'((?:[^'\\]|\\.)*)',")
ARTICLE = 0


def tuples(path):
    with gzip.open(path, "rb") as f:
        for line in f:
            if line.startswith(b"(") or b"),(" in line:
                yield line


def read_linktargets(path, titles_wanted):
    """target id -> title, for titles that name a geographic article."""
    out = {}
    for line in tuples(path):
        for m in LINKTARGET.finditer(line):
            if int(m.group(2)) != ARTICLE:
                continue
            t = m.group(3).decode("utf-8", "ignore").replace("_", " ")
            if t in titles_wanted:
                out[int(m.group(1))] = t
    return out


def read_redirects(path, title_to_page):
    """page id -> the title it redirects to, when that title is geographic."""
    out = {}
    for line in tuples(path):
        for m in REDIRECT.finditer(line):
            if int(m.group(2)) != ARTICLE:
                continue
            t = m.group(3).decode("utf-8", "ignore").replace("_", " ")
            if t in title_to_page:
                out[int(m.group(1))] = t
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--geo-pages", required=True, help="geo_pages_qid.jsonl")
    ap.add_argument("--pagelinks", required=True)
    ap.add_argument("--linktarget", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    page_of_title = {}
    qid_of_page = {}
    with open(a.geo_pages, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            page_of_title[r["title"]] = r["page_id"]
            if r.get("qid"):
                qid_of_page[r["page_id"]] = r["qid"]
    print(f"geographic articles\t{len(page_of_title):,}", flush=True)

    targets = read_linktargets(a.linktarget, page_of_title)
    print(f"link targets that are geographic\t{len(targets):,}", flush=True)
    target_page = {tid: page_of_title[t] for tid, t in targets.items()}

    edges = 0
    out_degree = collections.Counter()
    with open(a.out, "w", encoding="utf-8") as out:
        for line in tuples(a.pagelinks):
            for m in PAGELINK.finditer(line):
                src = int(m.group(1))
                if int(m.group(2)) != ARTICLE or src not in qid_of_page:
                    continue
                dst = target_page.get(int(m.group(3)))
                if dst is None or dst == src:
                    continue
                out.write(f"{src}\t{dst}\n")
                out_degree[src] += 1
                edges += 1
                if edges % 2_000_000 == 0:
                    print(f"  {edges:,} edges", flush=True)
    print(f"edges\t{edges:,}")
    print(f"articles with at least one outgoing geo link\t{len(out_degree):,}")


if __name__ == "__main__":
    sys.exit(main())
