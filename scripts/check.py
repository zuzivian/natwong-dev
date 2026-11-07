#!/usr/bin/env python3
"""Static checks for natwong.dev. Standard library only; run from the repo root:

    python3 scripts/check.py

Exits non-zero and lists every failure. Covers build health (every local
reference resolves, JSON-LD and vercel.json parse), SEO hygiene (title,
description, canonical, OG image, sitemap) and an accessibility floor (lang,
alt text, heading order, one h1, main landmark, safe target=_blank).
It also enforces that /resume.pdf is never linked from the site.
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://natwong.dev"
errors = []


def fail(msg):
    errors.append(msg)


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []      # (tag, attrs dict, line)
        self.headings = []  # (level, line)
        self.ids = set()
        self.jsonld = []
        self._in_jsonld = False
        self._title = None
        self.title = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        line = self.getpos()[0]
        self.tags.append((tag, a, line))
        if "id" in a:
            if a["id"] in self.ids:
                fail(f"index.html:{line}: duplicate id #{a['id']}")
            self.ids.add(a["id"])
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append((int(tag[1]), line))
        if tag == "script" and a.get("type") == "application/ld+json":
            self._in_jsonld = True
            self.jsonld.append("")
        if tag == "title":
            self._title = ""

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_jsonld = False
        if tag == "title" and self._title is not None:
            self.title, self._title = self._title.strip(), None

    def handle_data(self, data):
        if self._in_jsonld:
            self.jsonld[-1] += data
        if self._title is not None:
            self._title += data


def local_path(ref):
    """Map a same-site URL to a file in the repo, or None if it's external/anchor/data."""
    if not ref or ref.startswith(("#", "data:", "mailto:", "tel:")):
        return None
    u = urlparse(ref)
    if u.scheme and not ref.startswith(SITE):
        return None
    path = u.path.lstrip("/")
    if path.startswith("_vercel/"):  # injected by Vercel at deploy time
        return None
    return path or "index.html"


def check_html():
    with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
        src = f.read()
    p = Page()
    p.feed(src)

    if "resume.pdf" in src.lower():
        fail("index.html: mentions resume.pdf — it must never be linked from the site")

    html = next((a for t, a, _ in p.tags if t == "html"), {})
    if not html.get("lang"):
        fail("index.html: <html> is missing lang")
    if not p.title:
        fail("index.html: empty <title>")

    metas = {(a.get("name") or a.get("property")): a.get("content") for t, a, _ in p.tags if t == "meta"}
    for key in ("description", "viewport", "og:title", "og:description", "og:image", "og:url", "twitter:card"):
        if not metas.get(key):
            fail(f"index.html: missing <meta> {key}")
    canon = [a.get("href") for t, a, _ in p.tags if t == "link" and a.get("rel") == "canonical"]
    if canon != [SITE + "/"]:
        fail(f"index.html: canonical should be exactly {SITE}/ (got {canon})")

    # every local reference resolves to a file in the repo
    refs = []
    for t, a, line in p.tags:
        for attr in ("href", "src"):
            if attr in a:
                refs.append((a[attr], line))
        if "srcset" in a:
            refs += [(c.strip().split()[0], line) for c in a["srcset"].split(",") if c.strip()]
        if t == "meta" and (a.get("property") or a.get("name") or "").endswith(":image"):
            refs.append((a.get("content"), line))
    for ref, line in refs:
        if ref and ref.startswith("#") and len(ref) > 1 and ref[1:] not in p.ids:
            fail(f"index.html:{line}: anchor {ref} has no matching id")
        path = local_path(ref)
        if path and not os.path.isfile(os.path.join(ROOT, path)):
            fail(f"index.html:{line}: {ref} does not exist in the repo")
    for m in re.finditer(r"url\(([^)]+)\)", src):
        path = local_path(m.group(1).strip("'\""))
        if path and not os.path.isfile(os.path.join(ROOT, path)):
            fail(f"index.html: CSS url({m.group(1)}) does not exist in the repo")

    for blob in p.jsonld:
        try:
            data = json.loads(blob)
        except ValueError as e:
            fail(f"index.html: JSON-LD does not parse: {e}")
            continue
        for key in ("image", "url"):
            path = local_path(data.get(key, ""))
            if path and not os.path.isfile(os.path.join(ROOT, path)):
                fail(f"index.html: JSON-LD {key} {data[key]} does not exist in the repo")

    # accessibility floor
    for t, a, line in p.tags:
        if t == "img" and "alt" not in a:
            fail(f"index.html:{line}: <img> without alt")
        if t == "img" and not (a.get("width") and a.get("height")):
            fail(f"index.html:{line}: <img> without width/height (layout shift)")
        if t == "a" and a.get("target") == "_blank" and "noopener" not in (a.get("rel") or ""):
            fail(f"index.html:{line}: target=_blank without rel=noopener")
    if sum(1 for lvl, _ in p.headings if lvl == 1) != 1:
        fail("index.html: expected exactly one <h1>")
    prev = 0
    for lvl, line in p.headings:
        if lvl > prev + 1:
            fail(f"index.html:{line}: heading jumps from h{prev} to h{lvl}")
        prev = lvl
    if sum(1 for t, _, _ in p.tags if t == "main") != 1:
        fail("index.html: expected exactly one <main> landmark")


def check_files():
    for name in ("robots.txt", "sitemap.xml"):
        with open(os.path.join(ROOT, name), encoding="utf-8") as f:
            if "resume" in f.read().lower():
                fail(f"{name}: mentions the resume — it must stay unlisted")

    with open(os.path.join(ROOT, "robots.txt"), encoding="utf-8") as f:
        if f"Sitemap: {SITE}/sitemap.xml" not in f.read():
            fail("robots.txt: missing Sitemap line")

    try:
        tree = ET.parse(os.path.join(ROOT, "sitemap.xml"))
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for loc in tree.getroot().iterfind("s:url/s:loc", ns):
            path = local_path(loc.text.strip())
            if path and not os.path.isfile(os.path.join(ROOT, path)):
                fail(f"sitemap.xml: {loc.text} does not exist in the repo")
    except ET.ParseError as e:
        fail(f"sitemap.xml: does not parse: {e}")

    try:
        with open(os.path.join(ROOT, "vercel.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        noindex = [h for h in cfg.get("headers", []) if h.get("source") == "/resume.pdf"
                   and any(x.get("key") == "X-Robots-Tag" and "noindex" in x.get("value", "") for x in h.get("headers", []))]
        if not noindex:
            fail("vercel.json: /resume.pdf must keep its X-Robots-Tag noindex header")
    except ValueError as e:
        fail(f"vercel.json: does not parse: {e}")


check_html()
check_files()
if errors:
    print("\n".join("FAIL " + e for e in errors))
    sys.exit(1)
print("OK: all site checks passed")
