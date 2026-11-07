#!/usr/bin/env python3
"""Refresh _data/papers.json from Marco Zennaro's Google Scholar profile.

Usage (from the repository root):
    python3 scripts/update_papers.py
Then commit and push:
    git add _data/papers.json && git commit -m "Update papers" && git push

Uses only the Python standard library plus curl. Google Scholar has no official API and
sometimes blocks automated requests (especially from cloud/CI machines), so
run this from your own computer. If it gets blocked, just try again later.
"""
import difflib
import html
import json
import re
import subprocess
import time
from pathlib import Path

SCHOLAR_ID = "qOtlP1AAAAAJ"
MAX_PAPERS = 2000
OUT = Path(__file__).resolve().parent.parent / "_data" / "papers.json"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# Keywords (lower-case, matched against the title) that assign a paper to one
# of the three research areas shown on the site. Edit freely.
AREAS = {
    "tinyml": ["tinyml", "tiny ml", "tiny machine learning", "edge ai",
               "edge ml", "edge machine learning", "embedded machine learning",
               "machine learning at the edge", "edge impulse", "microcontroller",
               "on-device", "quantized", "frugal intelligence", "aiot"],
    "weather": ["weather", "meteorolog", "rain gauge", "rainfall",
                "precipitation", "hydro-meteo"],
    "dtn": ["delay tolerant", "delay-tolerant", "disruption tolerant",
            "disruption-tolerant", "dtn", "bundle protocol", "data mule",
            "store-and-forward", "store and forward", "opportunistic network",
            "intermittent connectivity", "bytewalla"],
}


def fetch(cstart, pagesize=100):
    url = (f"https://scholar.google.com/citations?user={SCHOLAR_ID}&hl=en"
           f"&sortby=pubdate&cstart={cstart}&pagesize={pagesize}")
    # curl (not urllib) so it works with macOS python.org builds that ship
    # without CA certificates.
    out = subprocess.run(["curl", "-sL", "--max-time", "30", "-A", UA, url],
                         capture_output=True, check=True)
    return out.stdout.decode("utf-8", "replace")


def text(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def parse_rows(page):
    rows = []
    for m in re.finditer(r'<tr class="gsc_a_tr">(.*?)</tr>', page, re.S):
        r = m.group(1)
        title = re.search(r'class="gsc_a_at"[^>]*>(.*?)</a>', r)
        link = re.search(r'href="([^"]+)" class="gsc_a_at"', r)
        grays = re.findall(r'<div class="gs_gray">(.*?)</div>', r)
        year = re.search(r'gsc_a_h gsc_a_hc gs_ibl">(\d*)<', r)
        cites = re.search(r'class="gsc_a_ac gs_ibl">(\d*)<', r)
        if not title:
            continue
        venue = text(grays[1]) if len(grays) > 1 else ""
        venue = re.sub(r",\s*\d{4}$", "", venue).replace(" …", "…")
        rows.append({
            "title": text(title.group(1)),
            "authors": text(grays[0]) if grays else "",
            "venue": venue,
            "year": year.group(1) if year else "",
            "cites": int(cites.group(1)) if cites and cites.group(1) else 0,
            "url": "https://scholar.google.com" + html.unescape(link.group(1)) if link else "",
        })
    return rows


def areas_for(title):
    t = title.lower()
    return [a for a, kws in AREAS.items() if any(k in t for k in kws)]


# Scholar lists some works several times under different titles that the
# automatic checks below cannot match. Each group is a list of patterns
# (searched in the normalized title: lower-case letters and digits only);
# entries matching any pattern of a group are counted as one work.
SAME_WORK = [
    # IRTF GAIA document: six Internet-Draft revisions and the final RFC 7962
    ["globalaccesstotheinternetforalljsaldana", "alternativenetworkdeployments",
     "requestforcomments7962"],
    ["binarygreywolfoptimi"],
    ["widespreadapplicationoflowcosttechnologiesincoastaloceanobserving"],
    ["wirelessnetworkinginthedevelopingworld"],  # 2006 and 2013 editions
    ["solarmonitoringsysteminmalawi"],
    ["bytewalla3", "bytewallaiii"],
]

# Entries that are not publications at all (case-insensitive regex on title).
NOT_PAPERS = [
    r"organizing committee",
    r"^project proposal",
]


def norm(title):
    t = re.sub(r"^(research article|refereed paper|original article|rfc \d+:)\s+",
               "", title.lower().strip())
    return re.sub(r"[^a-z0-9]", "", t)


def same_work(p, q):
    a, b = norm(p["title"]), norm(q["title"])
    for group in SAME_WORK:
        if any(g in a for g in group) and any(g in b for g in group):
            return True
    # Only compare titles from the same year, so a conference paper and its
    # later journal version (often with the same title) are counted separately.
    same_year = p["year"] == q["year"] or not p["year"] or not q["year"]
    if not same_year:
        return False
    if a == b:
        return True
    short, long_ = sorted((a, b), key=len)
    if len(short) >= 6 and long_.startswith(short):
        return True  # e.g. "RFTrack" and "RFTrack: a tool for ..."
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.95


def main():
    first = fetch(0)
    stats = re.findall(r'gsc_rsb_std">(\d+)<', first)
    rows = parse_rows(first)
    while len(rows) < MAX_PAPERS and len(rows) % 100 == 0 and rows:
        time.sleep(3)
        more = parse_rows(fetch(len(rows)))
        if not more:
            break
        rows += more
    if not rows:
        raise SystemExit("No papers parsed - Scholar may be blocking the request. Try later.")

    # Scholar often lists the same work more than once (preprint and published
    # version, parsing errors, draft revisions); keep one entry per work, the
    # one with more citations.
    papers, merged, dropped = [], [], []
    for p in rows:
        if any(re.search(rx, p["title"], re.I) for rx in NOT_PAPERS):
            dropped.append(p["title"])
            continue
        kept = next((q for q in papers if same_work(p, q)), None)
        if kept is None:
            papers.append(p)
            continue
        merged.append((p["title"], kept["title"]))
        if p["cites"] > kept["cites"]:
            kept.update(p)
    for p in papers:
        p["areas"] = areas_for(p["title"])

    data = {
        "updated": time.strftime("%Y-%m-%d"),
        "scholar_id": SCHOLAR_ID,
        "citations": int(stats[0]) if stats else None,
        "h_index": int(stats[2]) if len(stats) > 2 else None,
        "i10_index": int(stats[4]) if len(stats) > 4 else None,
        "papers": papers,
    }
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    counts = {a: sum(a in p["areas"] for p in papers) for a in AREAS}
    print(f"Scholar entries: {len(rows)}; duplicates merged: {len(merged)}; "
          f"non-papers dropped: {len(dropped)}")
    for dup, into in merged:
        print(f"  merged:  {dup[:70]}\n     into: {into[:70]}")
    for t in dropped:
        print(f"  dropped: {t[:70]}")
    print(f"Wrote {len(papers)} papers to {OUT} ({counts})")


if __name__ == "__main__":
    main()
