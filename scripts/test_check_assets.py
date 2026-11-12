"""Subresource policy and byte-budget regressions using temporary assets."""
import struct
import tempfile
import unittest
from pathlib import Path

import check


class AssetChecksTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.html = '''<!doctype html><html lang="en"><head>
<title>Fixture</title>
<meta name="description" content="Fixture">
<meta name="viewport" content="width=device-width">
<meta property="og:title" content="Fixture">
<meta property="og:description" content="Fixture">
<meta property="og:url" content="https://natwong.dev/">
<meta property="og:image" content="https://example.com/share.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://example.com/share.png">
<link rel="canonical" href="https://natwong.dev/">
</head><body><main><h1>Fixture</h1>{assets}</main></body></html>'''

    def run_checks(self, assets="", html=None):
        (self.root / "index.html").write_text(
            self.html.replace("{assets}", assets) if html is None else html,
            encoding="utf-8",
        )
        check.errors.clear()
        check.check_html(self.root)
        return check.errors.copy()

    def asset(self, name, size):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b" " * size)

    def assert_rejected(self, markup, message="third-party subresource"):
        failures = self.run_checks(markup)
        self.assertEqual(len(failures), 1, failures)
        self.assertIn(message, failures[0])

    def test_external_stylesheet(self):
        self.assert_rejected('<link rel="stylesheet" href="https://cdn.example/style.css">')

    def test_external_script(self):
        self.assert_rejected('<script src="https://cdn.example/script.js"></script>')

    def test_external_resource_attributes(self):
        markups = [
            '<link rel="alternate STYLESHEET" href="//cdn.example/style.css">',
            '<link rel="preload" href="https://cdn.example/font.woff2" as="font">',
            '<link rel="modulepreload" href="https://cdn.example/module.js">',
            '<link rel="shortcut icon" href="https://cdn.example/icon.svg">',
            '<img src="https://cdn.example/photo.jpg" alt="" width="1" height="1">',
            '<img srcset="https://cdn.example/photo.jpg 2x" alt="" width="1" height="1">',
            '<source src="https://cdn.example/movie.mp4">',
            '<source srcset="https://cdn.example/photo.avif 1x">',
            '<iframe src="https://example.com/"></iframe>',
            '<video src="https://cdn.example/movie.mp4"></video>',
            '<video poster="https://cdn.example/poster.jpg"></video>',
            '<audio src="https://cdn.example/sound.mp3"></audio>',
            '<style>body { background: URL( "https://cdn.example/bg.png" ); }</style>',
            '<div style="background:url(//cdn.example/bg.png)"></div>',
            '<style>@import "https://cdn.example/style.css";</style>',
        ]
        for markup in markups:
            with self.subTest(markup=markup):
                self.assert_rejected(markup)

    def test_vercel_script(self):
        self.assertEqual(self.run_checks('<script src="/_vercel/insights/script.js"></script>'), [])

    def test_external_anchor_and_share_metadata(self):
        self.assertEqual(self.run_checks('<a href="https://example.com/">External</a>'), [])

    def test_same_site_urls_and_data(self):
        self.asset("photo.jpg", 100)
        self.assertEqual(self.run_checks('''
<img src="https://natwong.dev/photo.jpg" alt="" width="1" height="1">
<img src="//natwong.dev/photo.jpg" alt="" width="1" height="1">
<img srcset="data:image/png;base64,AAAA 1x, photo.jpg 2x" alt="" width="1" height="1">
<link rel="icon" href="data:image/svg+xml,%3Csvg/%3E">
<style>body { background: url(data:image/png;base64,AAAA); }</style>'''), [])

    def test_external_srcset_after_data(self):
        self.assert_rejected('''<img alt="" width="1" height="1"
srcset="data:image/png;base64,AAAA 1x, https://cdn.example/photo.jpg 2x">''')

    def test_oversized_image(self):
        self.asset("large.jpg", check.MAX_IMAGE_BYTES + 1)
        self.assert_rejected('<img src="large.jpg" alt="" width="1" height="1">',
                             "image is 120001 bytes, exceeds 120000-byte budget")

    def test_image_at_budget(self):
        self.asset("photo.jpg", check.MAX_IMAGE_BYTES)
        self.assertEqual(self.run_checks('<img src="photo.jpg" alt="" width="1" height="1">'), [])

    def test_oversized_srcset_image(self):
        self.asset("large.webp", check.MAX_IMAGE_BYTES + 1)
        self.assert_rejected('<source srcset="large.webp 2x">', "image is")

    def test_oversized_css_image(self):
        self.asset("large.png", check.MAX_IMAGE_BYTES + 1)
        self.assert_rejected('<style>body { background:url(large.png); }</style>', "image is")

    def test_font_budget(self):
        self.asset("font.woff2", check.MAX_FONT_BYTES)
        markup = '<style>@font-face { src: url(font.woff2); }</style>'
        self.assertEqual(self.run_checks(markup), [])
        self.asset("font.woff2", check.MAX_FONT_BYTES + 1)
        self.assert_rejected(markup, "font is 60001 bytes, exceeds 60000-byte budget")

    def test_html_budget_uses_bytes(self):
        html = self.html.replace("{assets}", "")
        html += " " * (check.MAX_HTML_BYTES - len(html.encode("utf-8")))
        self.assertEqual(self.run_checks(html=html), [])
        failures = self.run_checks(html=html[:-1] + "é")
        self.assertEqual(len(failures), 1, failures)
        self.assertIn("60001 bytes, exceeds 60000-byte HTML budget", failures[0])

    def test_total_budget_and_duplicate_references(self):
        self.asset("photo.jpg", check.MAX_IMAGE_BYTES)
        self.asset("font.woff2", check.MAX_FONT_BYTES)
        markup = '''<link rel="preload" as="font" href="font.woff2">
<style>@font-face { src:url(font.woff2); }</style>
<img src="photo.jpg" srcset="/photo.jpg 1x, https://natwong.dev/photo.jpg?v=2 2x"
alt="" width="1" height="1">'''
        html_size = len(self.html.replace("{assets}", markup).encode("utf-8"))
        remaining = check.MAX_TOTAL_BYTES - html_size - check.MAX_IMAGE_BYTES - check.MAX_FONT_BYTES
        self.asset("extra.js", remaining)
        # Include the script tag itself in the exact total.
        markup += '<script src="extra.js"></script>'
        self.asset("extra.js", remaining - len('<script src="extra.js"></script>'))
        self.assertEqual(self.run_checks(markup), [])
        with (self.root / "extra.js").open("ab") as f:
            f.write(b" ")
        self.assert_rejected(markup, "250001 bytes, exceeds 250000-byte total budget")

    def test_metadata_and_links_are_excluded_from_budgets(self):
        self.asset("headshot.jpg", check.MAX_TOTAL_BYTES + 1)
        header = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 1200, 630)
        (self.root / "og-image.png").write_bytes(header + b" " * check.MAX_TOTAL_BYTES)
        self.html = self.html.replace("https://example.com/share.png", "https://natwong.dev/og-image.png")
        self.html = self.html.replace("</head>", '''
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630"></head>''')
        self.assertEqual(self.run_checks('''
<a href="headshot.jpg">Photo</a>
<script type="application/ld+json">{"image":"https://natwong.dev/headshot.jpg"}</script>'''), [])

    def test_local_stylesheet_relative_resources_and_imports(self):
        (self.root / "css").mkdir()
        (self.root / "css/site.css").write_text('@import "nested.css";', encoding="utf-8")
        (self.root / "css/nested.css").write_text(
            '@import "site.css"; body { background: url(../photo.png); }', encoding="utf-8")
        self.asset("photo.png", check.MAX_IMAGE_BYTES)
        markup = '<link rel="stylesheet" href="css/site.css">'
        self.assertEqual(self.run_checks(markup), [])
        self.asset("photo.png", check.MAX_IMAGE_BYTES + 1)
        self.assert_rejected(markup, "image is")

    def test_external_resource_in_local_stylesheet(self):
        (self.root / "site.css").write_text(
            'body { background:url(https://cdn.example/photo.png); }', encoding="utf-8")
        self.assert_rejected('<link rel="stylesheet" href="site.css">')

    def test_css_comments_and_script_text_are_not_requests(self):
        self.assertEqual(self.run_checks('''
<style>/* background:url(https://example.com/unused.png) */</style>
<script>const example = "url(https://example.com/example.png)";</script>'''), [])


if __name__ == "__main__":
    unittest.main()
