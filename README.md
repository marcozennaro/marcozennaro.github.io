# Marco Zennaro — personal website

Personal page focused on three research areas: **TinyML**, **low-cost weather station
networks** and **Delay Tolerant Networking (DTN)**. Built with Jekyll and served by
GitHub Pages — no build step needed; just edit and push.

## How to update

| What | Where |
|---|---|
| Bio, contact links | `index.html` (section `#about`) and `_config.yml` (`author:`) |
| Research-area texts | `_data/areas.yml` |
| Workshops (and their slides) | `_data/workshops.yml` (add `end: "YYYY-MM-DD"` to show an *Upcoming* badge) |
| News items | `_data/news.yml` |
| TinyML network map | `assets/img/tinyml4d-network.png` (settings in `_data/areas.yml`) |
| Papers | `_data/papers.json` — regenerate with the script below |
| Profile photo | add `assets/img/marco.jpg` (square, ~600×600 px) |
| Colors / layout | `assets/css/style.css` |

### Add a workshop with slides

1. Copy your PDF into `slides/`, e.g. `slides/2026-dtn-workshop.pdf`.
2. Add an entry at the top of `_data/workshops.yml`:

   ```yaml
   - title: "Workshop on Delay Tolerant Networking"
     year: 2026
     place: "Trieste, Italy"
     area: dtn            # tinyml | weather | dtn | iot
     url: https://indico.ictp.it/event/XXXX
     slides:
       - label: "Opening"
         link: slides/2026-dtn-workshop.pdf
   ```
3. Commit and push.

### Refresh papers from Google Scholar

```bash
python3 scripts/update_papers.py
git add _data/papers.json && git commit -m "Update papers" && git push
```

The script reads the public Scholar profile (`qOtlP1AAAAAJ`), removes duplicates, and tags
each paper with a research area using the keyword lists at the top of the script.
Google Scholar blocks automated access from cloud servers, so run it from your own computer.

### Preview locally (optional)

```bash
jekyll serve
```
then open http://localhost:4000.
