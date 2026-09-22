#!/usr/bin/env python3
"""Where Wikipedia's links and Wikidata's hierarchy agree, and where they do not.

Wikidata's P131 says one place is inside another. A link between two articles
says an editor thought one worth mentioning in the other. Three ways they can
differ, each informative:

  both        the containment is stated and also written about
  hierarchy   stated but never linked: formal containment with no prose
  link only   linked but not contained: adjacency, history, or mention

The third is the one no existing dataset holds.

Links run mostly from child to parent, because an article about a town names
its country more often than a country names its towns, so a P131 edge counts
as linked if the link runs either way.

Memory is the constraint. There are 121 million links, and holding them as a
set of qid string pairs costs about 14.5 GB; this machine has no swap, so
running out does not kill the process, it stops the machine. So the links are
never all held at once. P131 is small enough to hold, as page-id pairs packed
into single integers, and the link file is streamed against it.
"""
import argparse
import collections
import csv
import json


def pack(a, b):
    """Two page ids as one integer. Page ids fit comfortably in 32 bits."""
    return (a << 32) | b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--geo-pages", required=True)
    ap.add_argument("--edges", required=True, help="geo_edges.tsv, page id pairs")
    ap.add_argument("--p131", default=None, help="p131_edges.csv, qid pairs")
    ap.add_argument("--ancestors", default=None,
                    help="ancestors.tsv from closure.py, page id pairs with depth")
    ap.add_argument("--out", default=None, help="write the link-only edges here")
    ap.add_argument("--out-limit", type=int, default=2_000_000)
    a = ap.parse_args()

    page_of_qid = {}
    title_of = {}
    with open(a.geo_pages, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            title_of[r["page_id"]] = r["title"]
            if r.get("qid"):
                page_of_qid[r["qid"]] = r["page_id"]
    print(f"articles\t{len(title_of):,}", flush=True)

    # P131 as packed page-id pairs, plus the reverse, so a link either way
    # counts. 1.26 million edges is about 100 MB held this way.
    stated = set()
    either_way = set()
    if a.ancestors:
        # Ancestors rather than parents. P131 names only the unit one step up,
        # so an article that links straight to its country looked like a
        # relation Wikidata lacked when it has it, several steps away.
        with open(a.ancestors, encoding="utf-8") as f:
            for line in f:
                c, p, _ = line.split("\t")
                key = pack(int(c), int(p))
                stated.add(key)
                either_way.add(key)
                either_way.add(pack(int(p), int(c)))
        print(f"ancestor pairs\t{len(stated):,}", flush=True)
    else:
        with open(a.p131, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                c, p = page_of_qid.get(r["child"]), page_of_qid.get(r["parent"])
                if c is None or p is None:
                    continue
                stated.add(pack(c, p))
                either_way.add(pack(c, p))
                either_way.add(pack(p, c))
        print(f"P131 edges with both ends here\t{len(stated):,}", flush=True)

    linked = set()          # the P131 edges that are also linked, packed
    links = link_only = 0
    indeg = collections.Counter()
    out = open(a.out, "w", encoding="utf-8") if a.out else None
    written = 0
    with open(a.edges, encoding="utf-8") as f:
        for line in f:
            s, _, d = line.partition("\t")
            src, dst = int(s), int(d)
            links += 1
            indeg[dst] += 1
            key = pack(src, dst)
            if key in either_way:
                # Record it against the stated direction, whichever way it ran.
                linked.add(key if key in stated else pack(dst, src))
            else:
                link_only += 1
                if out and written < a.out_limit:
                    out.write(json.dumps(
                        {"from_title": title_of.get(src), "to_title": title_of.get(dst)},
                        ensure_ascii=False) + "\n")
                    written += 1
    if out:
        out.close()

    both = len(linked & stated)
    print(f"links between geographic articles\t{links:,}")
    print(f"\ncontainment stated and linked\t{both:,}\t{both/len(stated)*100:.1f}% of stated")
    print(f"stated but never linked\t{len(stated)-both:,}\t"
          f"{(len(stated)-both)/len(stated)*100:.1f}%")
    print(f"linked but not contained\t{link_only:,}\t{link_only/links*100:.1f}% of links")
    if out:
        print(f"wrote {written:,} link-only edges to {a.out}")

    print("\nmost linked-to geographic articles:")
    for pid, n in indeg.most_common(12):
        print(f"  {str(title_of.get(pid))[:38]:<40} {n:>9,} incoming")


if __name__ == "__main__":
    main()
