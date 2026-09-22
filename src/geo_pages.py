#!/usr/bin/env python3
"""Which English Wikipedia articles are about a place, and what are they called?

Two dumps answer this together. `geo_tags` is the GeoData extension's table of
coordinates attached to pages, so a page id appearing there is a page about
something with a location. `page` maps a page id to its title and namespace.

Neither is a corpus. The point of joining them first is to see what 1.4 million
geographic articles actually are before downloading the 25.7 GB of article text
that would be needed to read them.

The SQL dumps put their values on the lines after `INSERT INTO ... VALUES`, not
on the same line, which is why these are parsed by scanning for tuples rather
than by splitting on the INSERT.
"""
import argparse
import collections
import gzip
import json
import re

# (gt_id, gt_page_id, gt_globe, gt_primary, gt_lat, gt_lon, gt_dim, gt_type, ...)
GEO = re.compile(rb"\((\d+),(\d+),'([^']*)',(\d+),([-\d.]+|NULL),([-\d.]+|NULL),"
                 rb"([-\d]+|NULL),(NULL|'[^']*')")
# (page_id, page_namespace, page_title, page_is_redirect, page_is_new, ...)
PAGE = re.compile(rb"\((\d+),(\d+),'((?:[^'\\]|\\.)*)',(\d+),(\d+),")

ARTICLE_NAMESPACE = 0


def values(path):
    """Every tuple line in a MediaWiki SQL dump."""
    with gzip.open(path, "rb") as f:
        for line in f:
            if line.startswith(b"(") or b"),(" in line:
                yield line


def read_geo(path):
    """page id -> (primary tag?, type, lat, lon)."""
    out = {}
    for line in values(path):
        for m in GEO.finditer(line):
            pid = int(m.group(2))
            primary = m.group(4) == b"1"
            raw = m.group(8)
            # The dump writes an absent value as the literal NULL, without
            # quotes. Decoding it as text stores the string "NULL" and hides
            # that 57.5% of tags carry no type at all.
            kind = None if raw == b"NULL" else (raw.strip(b"'").decode("utf-8", "ignore") or None)
            lat = None if m.group(5) == b"NULL" else float(m.group(5))
            lon = None if m.group(6) == b"NULL" else float(m.group(6))
            # A page can carry several tags. The primary one is the page's own
            # location; the rest are places it mentions.
            if primary or pid not in out:
                out[pid] = (primary, kind, lat, lon)
    return out


def read_titles(path, wanted):
    """page id -> title, for article-namespace pages that are not redirects."""
    out = {}
    for line in values(path):
        for m in PAGE.finditer(line):
            pid = int(m.group(1))
            if pid not in wanted:
                continue
            if int(m.group(2)) != ARTICLE_NAMESPACE or m.group(4) == b"1":
                continue
            out[pid] = m.group(3).decode("utf-8", "ignore").replace("_", " ")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--geo-tags", required=True)
    ap.add_argument("--page", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    geo = read_geo(a.geo_tags)
    print(f"geo_tags pages\t{len(geo):,}", flush=True)
    titles = read_titles(a.page, geo)
    print(f"articles, not redirects\t{len(titles):,}", flush=True)

    kinds = collections.Counter()
    with open(a.out, "w", encoding="utf-8") as f:
        for pid, title in sorted(titles.items()):
            primary, kind, lat, lon = geo[pid]
            kinds[kind or "(none)"] += 1
            f.write(json.dumps({"page_id": pid, "title": title,
                                "primary": primary, "gt_type": kind,
                                "lat": lat, "lon": lon}, ensure_ascii=False) + "\n")
    print("gt_type\tcount")
    for k, n in kinds.most_common(15):
        print(f"{k}\t{n:,}")


if __name__ == "__main__":
    main()
