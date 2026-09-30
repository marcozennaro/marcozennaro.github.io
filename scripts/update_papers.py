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
import html
import json
import re
import subprocess
import time
from pathlib import Path

SCHOLAR_ID = "qOtlP1AAAAAJ"
MAX_PAPERS = 300
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


def norm(title):
    return re.sub(r"[^a-z0-9]", "", title.lower())


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

    # Scholar often lists a preprint and the published version separately;
    # keep the entry with more citations (or the first one, which is newer).
    seen, papers = {}, []
    for p in rows:
        key = norm(p["title"])
        if key in seen:
            kept = seen[key]
            if p["cites"] > kept["cites"]:
                kept.update(p)
            continue
        p["areas"] = areas_for(p["title"])
        seen[key] = p
        papers.append(p)

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
    print(f"Wrote {len(papers)} papers to {OUT} ({counts})")


if __name__ == "__main__":
    main()
