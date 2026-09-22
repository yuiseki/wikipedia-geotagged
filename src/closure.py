#!/usr/bin/env python3
"""Every ancestor of every place, not just its immediate parent.

Comparing P131 to Wikipedia's links without this is unfair to Wikidata. P131
names only the containing unit one step up, so Escondido points at San Diego
County and not at California; the article links straight to the state, and the
comparison counted that as a relation Wikidata did not have. It has it, two
steps away.

P17, the country, is included as a stated relation of its own. An article about
a village in Iran links to Iran directly and almost never walks the chain.

Chains can loop, because Wikidata is edited by people. A visited set per node
keeps a cycle from running forever.
"""
import argparse
import collections
import csv
import json
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stated", required=True, help="stated_edges.csv")
    ap.add_argument("--geo-pages", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-depth", type=int, default=12)
    a = ap.parse_args()

    page_of_qid = {}
    with open(a.geo_pages, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("qid"):
                page_of_qid[r["qid"]] = r["page_id"]

    parents = collections.defaultdict(set)
    direct = 0
    with open(a.stated, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            c, p = r["child"], r["parent"]
            if c and p and c != p:
                parents[c].add(p)
                direct += 1
    print(f"stated edges\t{direct:,}", flush=True)
    print(f"nodes with a parent\t{len(parents):,}", flush=True)

    written = 0
    depth_hist = collections.Counter()
    with open(a.out, "w", encoding="utf-8") as out:
        for child in parents:
            cp = page_of_qid.get(child)
            if cp is None:
                continue
            seen = set()
            frontier = {child}
            for depth in range(1, a.max_depth + 1):
                nxt = set()
                for node in frontier:
                    for p in parents.get(node, ()):
                        if p in seen or p == child:
                            continue
                        seen.add(p)
                        nxt.add(p)
                if not nxt:
                    break
                for p in nxt:
                    pp = page_of_qid.get(p)
                    if pp is not None:
                        out.write(f"{cp}\t{pp}\t{depth}\n")
                        written += 1
                        depth_hist[depth] += 1
                frontier = nxt
            if written and written % 2_000_000 < len(seen):
                print(f"  {written:,} ancestor pairs", flush=True)
    print(f"ancestor pairs\t{written:,}")
    print("by depth:", dict(sorted(depth_hist.items())))


if __name__ == "__main__":
    sys.exit(main())
