# NOTES — natwong.dev

Working notes for maintenance runs. Static single-page site, Vercel deploys `main`.

## Checks
- `python3 scripts/check.py` — stdlib only, no install. CI runs it on every push and PR (`.github/workflows/check.yml`). Local refs resolve, JSON-LD / sitemap / vercel.json parse, sitemap lastmod dates are valid non-future YYYY-MM-DD dates, og:image PNG dimensions match width/height metadata, SEO meta present, a11y floor (lang, alt, one h1, heading order, one `<main>`, `rel=noopener` and screen-reader hints for new-tab links), and `/resume.pdf` is never linked or listed.
- `python3 -m unittest discover -s scripts -p 'test_*.py'` — stdlib unit tests for the checker; fixtures are generated in temporary directories, no install.
- Visual check: `python3 -m http.server` and load at 1280 and 390 wide.

## Done
- 2026-11-12: added CSS new-tab arrow markers with empty alternative text in supporting browsers, preserving the existing screen-reader hints (#42).
- 2026-11-07: a11y pass (`--ink-3` contrast 3.1:1 → 4.96:1, skip link, `<main>`, timeline scroller keyboard-focusable while it scrolls, timeline h4 → h3); headshot served as 400px `headshot-400.jpg` (72 KB → 29 KB); sitemap lastmod 2026-10-31; added `scripts/check.py`.

- 2026-11-10: `.github/workflows/check.yml` runs `scripts/check.py` on push and pull_request (approved by Nat 2026-11-09). Actions pinned to commit SHAs (checkout v6.1.0, setup-python v6.3.0), Python 3.13, read-only token, no dependencies.
- 2026-11-10: smooth scrolling only with `prefers-reduced-motion: no-preference`; card and timeline fade transitions disabled with reduced motion (#20).
- 2026-11-10: `scripts/check.py` validates sitemap lastmod dates (YYYY-MM-DD, not in the future) and checks og:image PNG dimensions against width/height metadata (#21).
- 2026-11-10: new-tab links include an “opens in a new tab” screen-reader hint via `.sr-only` spans (#22).
- 2026-11-11: added a Projects nav link and section with four anchored draft case studies; case-study definition lists stack on mobile (#24).

## Next
- Consider a 404 page (it's a new page, so Nat's call).

## Gotchas
- Bump `sitemap.xml`'s `lastmod` to the latest page-change commit date when page content changes.
- Everything in the repo root is publicly served by Vercel, including README.md, NOTES.md and scripts/. Don't put anything private here.
- Don't add a root `package.json`: Vercel would start treating the site as a Node build.
- `headshot.jpg` (700px) stays for the JSON-LD `image`; the page uses `headshot-400.jpg`.
- `/resume.pdf` is hosted unlinked with a noindex header (vercel.json). Never link it; check.py enforces this.
- Workflow actions are pinned by SHA; bump them deliberately (`git ls-remote --tags https://github.com/actions/<name>`), not to floating tags.
- `.github/` is in the repo root, so Vercel serves it too. Keep it free of anything private.
- Brief: quality work only, no bio/resume/personal-copy changes, no new pages.
