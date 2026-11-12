#!/usr/bin/env python3
"""Static checks for natwong.dev. Standard library only; run from the repo root:

    python3 scripts/check.py

Exits non-zero and lists every failure. Covers build health (every local
reference resolves, JSON-LD and vercel.json parse), SEO hygiene (title,
description, canonical, OG image, sitemap) and an accessibility floor (lang,
alt text, heading order, one h1, main landmark, safe target=_blank with
screen-reader hints).
It also checks that every sitemap <lastmod> is a valid, non-future YYYY-MM-DD
date and that the og:image PNG's real dimensions match og:image:width/height.
Share metadata must agree: og:url matches the canonical URL, twitter:image
matches og:image, and optional Twitter titles/descriptions match Open Graph.
It also enforces that /resume.pdf is never linked from the site.
Local references use exact HTTP(S) site matching and decoded URL paths.
Sitemap URLs must use https://natwong.dev/ and include that exact homepage URL.
"""
import json
import os
import re
import struct
import sys
from datetime import date
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import unquote, urlparse

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
        self._blank_line = None
        self._link_hint = False
        self._link_elements = []  # (tag, text chunks if sr-only, otherwise None)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        line = self.getpos()[0]
        self.tags.append((tag, a, line))
        if tag == "a" and a.get("target") == "_blank":
            self._blank_line = line
            self._link_hint = False
            self._link_elements = []
        elif self._blank_line is not None and tag not in {
            "area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr",
        }:
            chunks = [] if "sr-only" in (a.get("class") or "").split() else None
            self._link_elements.append((tag, chunks))
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
        if self._blank_line is not None:
            # Keep descendant text together even when inline tags split the hint.
            for i in range(len(self._link_elements) - 1, -1, -1):
                if self._link_elements[i][0] == tag or tag == "a":
                    for _, chunks in self._link_elements[i:]:
                        if chunks is not None and "opens in a new tab" in " ".join("".join(chunks).split()):
                            self._link_hint = True
                    del self._link_elements[i:]
                    if tag != "a":
                        break
            if tag == "a":
                if not self._link_hint:
                    fail(f'index.html:{self._blank_line}: target=_blank link without an "(opens in a new tab)" hint')
                self._blank_line = None
        if tag == "script":
            self._in_jsonld = False
        if tag == "title" and self._title is not None:
            self.title, self._title = self._title.strip(), None

    def handle_data(self, data):
        for _, chunks in self._link_elements:
            if chunks is not None:
                chunks.append(data)
        if self._in_jsonld:
            self.jsonld[-1] += data
        if self._title is not None:
            self._title += data


def local_path(ref):
    """Map a same-site URL to a file in the repo, or None if it's external/anchor/data."""
    if not ref or ref.startswith(("#", "data:", "mailto:", "tel:")):
        return None
    u = urlparse(ref)
    if (u.scheme or u.netloc) and not (
        u.scheme in ("http", "https") and u.netloc == urlparse(SITE).netloc
    ):
        return None
    path = unquote(u.path).lstrip("/")
    if path.startswith("_vercel/"):  # injected by Vercel at deploy time
        return None
    return path or "index.html"


def check_html(root=ROOT):
    with open(os.path.join(root, "index.html"), encoding="utf-8") as f:
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
    for key in ("description", "viewport", "og:title", "og:description", "og:image", "og:url", "twitter:card", "twitter:image"):
        if not metas.get(key):
            fail(f"index.html: missing <meta> {key}")
    canon = [a.get("href") for t, a, _ in p.tags if t == "link" and a.get("rel") == "canonical"]
    if canon != [SITE + "/"]:
        fail(f"index.html: canonical should be exactly {SITE}/ (got {canon})")
    if [metas.get("og:url")] != canon:
        fail("index.html: og:url must match the canonical href")
    for field in ("image", "title", "description"):
        twitter_key, og_key = f"twitter:{field}", f"og:{field}"
        if twitter_key in metas and metas[twitter_key] != metas.get(og_key):
            fail(f"index.html: {twitter_key} must match {og_key}")

    # og:image really is the size the og:image:width/height meta tags promise
    og_path = local_path(metas.get("og:image"))
    if og_path and os.path.isfile(os.path.join(root, og_path)):
        with open(os.path.join(root, og_path), "rb") as f:
            head = f.read(24)
        if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
            fail(f"{og_path}: og:image is not a valid PNG")
        else:
            actual = struct.unpack(">II", head[16:24])
            try:
                promised = (int(metas.get("og:image:width")), int(metas.get("og:image:height")))
            except (TypeError, ValueError):
                fail("index.html: og:image:width / og:image:height missing or not integers")
            else:
                if actual != promised:
                    fail(f"{og_path}: is {actual[0]}x{actual[1]} but og:image:width/height say "
                         f"{promised[0]}x{promised[1]}")

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
        if path and not os.path.isfile(os.path.join(root, path)):
            fail(f"index.html:{line}: {ref} does not exist in the repo")
    for m in re.finditer(r"url\(([^)]+)\)", src):
        path = local_path(m.group(1).strip("'\""))
        if path and not os.path.isfile(os.path.join(root, path)):
            fail(f"index.html: CSS url({m.group(1)}) does not exist in the repo")

    for blob in p.jsonld:
        try:
            data = json.loads(blob)
        except ValueError as e:
            fail(f"index.html: JSON-LD does not parse: {e}")
            continue
        for key in ("image", "url"):
            path = local_path(data.get(key, ""))
            if path and not os.path.isfile(os.path.join(root, path)):
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


def check_files(root=ROOT):
    sitemap_errors = []
    for name in ("robots.txt", "sitemap.xml"):
        with open(os.path.join(root, name), encoding="utf-8") as f:
            if "resume" in f.read().lower():
                message = f"{name}: mentions the resume — it must stay unlisted"
                if name == "sitemap.xml":
                    sitemap_errors.append(message)
                else:
                    fail(message)

    with open(os.path.join(root, "robots.txt"), encoding="utf-8") as f:
        if f"Sitemap: {SITE}/sitemap.xml" not in f.read():
            fail("robots.txt: missing Sitemap line")

    try:
        tree = ET.parse(os.path.join(root, "sitemap.xml"))
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locations = [(loc.text or "").strip()
                     for loc in tree.getroot().iterfind("s:url/s:loc", ns)]
        for loc in locations:
            if not loc.startswith(SITE + "/"):
                sitemap_errors.append(f"sitemap.xml: loc {loc!r} must start with {SITE}/")
            path = local_path(loc)
            if path and not os.path.isfile(os.path.join(root, path)):
                fail(f"sitemap.xml: {loc} does not exist in the repo")
        if SITE + "/" not in locations:
            sitemap_errors.append(f"sitemap.xml: must include {SITE}/ exactly")
        for lm in tree.getroot().iterfind("s:url/s:lastmod", ns):
            text = (lm.text or "").strip()
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
                    raise ValueError
                day = date.fromisoformat(text)
            except ValueError:
                fail(f"sitemap.xml: lastmod {text!r} is not a valid YYYY-MM-DD date")
                continue
            if day > date.today():
                fail(f"sitemap.xml: lastmod {text} is in the future")
    except ET.ParseError as e:
        fail(f"sitemap.xml: does not parse: {e}")
    if sitemap_errors:
        # Report sitemap URL policy violations together, including unlisted files.
        fail("; ".join(sitemap_errors))

    try:
        with open(os.path.join(root, "vercel.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        noindex = [h for h in cfg.get("headers", []) if h.get("source") == "/resume.pdf"
                   and any(x.get("key") == "X-Robots-Tag" and "noindex" in x.get("value", "") for x in h.get("headers", []))]
        if not noindex:
            fail("vercel.json: /resume.pdf must keep its X-Robots-Tag noindex header")
    except ValueError as e:
        fail(f"vercel.json: does not parse: {e}")


def check_site(root=ROOT):
    """Check a site directory, returning only the errors from this run."""
    errors.clear()
    check_html(root)
    check_files(root)
    return errors.copy()


if __name__ == "__main__":
    failures = check_site()
    if failures:
        print("\n".join("FAIL " + e for e in failures))
        sys.exit(1)
    print("OK: all site checks passed")
