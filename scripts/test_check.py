"""Regression tests for the site checker, using temporary stdlib-only fixtures."""
import json
import struct
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import check


class SiteChecksTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.html = '''<!doctype html>
<html lang="en">
<head>
<title>Test site</title>
<meta name="description" content="Test description">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta property="og:title" content="Test site">
<meta property="og:description" content="Test description">
<meta property="og:image" content="https://natwong.dev/share.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:url" content="https://natwong.dev/">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://natwong.dev/share.png">
<link rel="canonical" href="https://natwong.dev/">
<script type="application/ld+json">{"url":"https://natwong.dev/"}</script>
</head>
<body><main>
<h1>Test site</h1>
<h2>Section</h2>
<h3>Detail</h3>
<img src="share.png" alt="Test image" width="1200" height="630">
<a href="/" target="_blank" rel="noopener">Home
<span class="sr-only">(opens in a new tab)</span></a>
</main></body>
</html>
'''
        self.write('index.html', self.html)
        self.write('robots.txt', 'User-agent: *\nSitemap: https://natwong.dev/sitemap.xml\n')
        self.sitemap = '''<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://natwong.dev/</loc><lastmod>{lastmod}</lastmod></url>
</urlset>'''
        self.write('sitemap.xml', self.sitemap.format(lastmod=date.today().isoformat()))
        self.write('vercel.json', json.dumps({'headers': [{
            'source': '/resume.pdf',
            'headers': [{'key': 'X-Robots-Tag', 'value': 'noindex'}],
        }]}))
        # Only the PNG signature and IHDR dimensions are read by the checker.
        (self.root / 'share.png').write_bytes(
            b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR'
            + struct.pack('>II', 1200, 630)
        )

    def write(self, name, text):
        (self.root / name).write_text(text, encoding='utf-8')

    def replace_html(self, old, new):
        self.assertIn(old, self.html)
        self.write('index.html', self.html.replace(old, new))

    def assert_failure(self, message):
        failures = check.check_site(self.root)
        self.assertEqual(len(failures), 1, failures)
        self.assertIn(message, failures[0])

    def test_valid_site(self):
        self.assertEqual(check.check_site(self.root), [])

    def test_missing_lang(self):
        self.replace_html(' lang="en"', '')
        self.assert_failure('<html> is missing lang')

    def test_two_h1(self):
        self.replace_html('<h2>Section</h2>', '<h1>Section</h1><h2>Subsection</h2>')
        self.assert_failure('expected exactly one <h1>')

    def test_heading_jump(self):
        self.replace_html('<h3>Detail</h3>', '<h4>Detail</h4>')
        self.assert_failure('heading jumps from h2 to h4')

    def test_image_without_alt(self):
        self.replace_html(' alt="Test image"', '')
        self.assert_failure('<img> without alt')

    def test_blank_link_without_noopener(self):
        self.replace_html(' rel="noopener"', '')
        self.assert_failure('target=_blank without rel=noopener')

    def test_broken_local_href(self):
        self.replace_html('<a href="/"', '<a href="/missing.html"')
        self.assert_failure('/missing.html does not exist in the repo')

    def test_resume_link(self):
        # Keep the target present so only the unlinked-resume rule fails.
        (self.root / 'resume.pdf').touch()
        self.replace_html('<a href="/"', '<a href="/resume.pdf"')
        self.assert_failure('mentions resume.pdf — it must never be linked from the site')

    def test_future_lastmod(self):
        tomorrow = date.today() + timedelta(days=1)
        self.write('sitemap.xml', self.sitemap.format(lastmod=tomorrow.isoformat()))
        self.assert_failure(f'lastmod {tomorrow.isoformat()} is in the future')

    def test_og_image_size_mismatch(self):
        self.replace_html('content="1200"', 'content="600"')
        self.assert_failure('is 1200x630 but og:image:width/height say 600x630')

    def test_missing_noindex_header(self):
        self.write('vercel.json', json.dumps({'headers': []}))
        self.assert_failure('/resume.pdf must keep its X-Robots-Tag noindex header')

    def test_errors_do_not_leak_between_runs(self):
        self.replace_html(' lang="en"', '')
        first_errors = check.check_site(self.root)
        self.assertEqual(first_errors, ['index.html: <html> is missing lang'])
        self.write('index.html', self.html)
        self.assertEqual(check.check_site(self.root), [])
        self.assertEqual(first_errors, ['index.html: <html> is missing lang'])


if __name__ == '__main__':
    unittest.main()
