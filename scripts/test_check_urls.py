"""URL resolution and sitemap policy regressions using temporary site fixtures."""
import json
import struct
import tempfile
import unittest
from pathlib import Path
from xml.sax.saxutils import escape

import check


class LocalPathTest(unittest.TestCase):
    def test_external_urls(self):
        for ref in (
            'https://natwong.dev.example.com/x.png',
            'https://natwong.devtools.io/a',
            '//example.com/x.png',
            '//natwong.dev/x.png',
            'https://natwong.dev:443/x.png',
            'https://natwong.dev@example.com/x.png',
            'ftp://natwong.dev/x.png',
        ):
            with self.subTest(ref=ref):
                self.assertIsNone(check.local_path(ref))

    def test_local_urls(self):
        for ref, expected in (
            ('http://natwong.dev/og.png', 'og.png'),
            ('https://natwong.dev/og.png', 'og.png'),
            ('my%20file.png', 'my file.png'),
            ('/my%20file.png?v=1#image', 'my file.png'),
            ('https://natwong.dev/my%20file.png', 'my file.png'),
            ('http://natwong.dev/', 'index.html'),
            ('/', 'index.html'),
        ):
            with self.subTest(ref=ref):
                self.assertEqual(check.local_path(ref), expected)

    def test_ignored_references(self):
        for ref in (None, '', '#section', 'data:image/png;base64,AA',
                    'mailto:test@example.com', 'tel:123', '/_vercel/insights/script.js'):
            with self.subTest(ref=ref):
                self.assertIsNone(check.local_path(ref))


class SiteURLTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.html = '''<!doctype html><html lang="en"><head>
<title>URL checks</title>
<meta name="description" content="URL fixture">
<meta name="viewport" content="width=device-width">
<meta property="og:title" content="URL checks">
<meta property="og:description" content="URL fixture">
<meta property="og:url" content="https://natwong.dev/">
<meta property="og:image" content="https://natwong.dev/share.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://natwong.dev/share.png">
<link rel="canonical" href="https://natwong.dev/">
</head><body><main><h1>URL checks</h1>{extra}</main></body></html>'''
        self.write_html()
        self.write('robots.txt', 'Sitemap: https://natwong.dev/sitemap.xml\n')
        self.write_sitemap(['https://natwong.dev/'])
        self.write('vercel.json', json.dumps({'headers': [{
            'source': '/resume.pdf',
            'headers': [{'key': 'X-Robots-Tag', 'value': 'noindex'}],
        }]}))
        (self.root / 'share.png').write_bytes(
            b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR'
            + struct.pack('>II', 1200, 630)
        )

    def write(self, name, content):
        (self.root / name).write_text(content, encoding='utf-8')

    def write_html(self, extra=''):
        self.write('index.html', self.html.format(extra=extra))

    def write_sitemap(self, locations):
        self.write('sitemap.xml',
                   '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                   + ''.join(f'<url><loc>{escape(loc)}</loc></url>' for loc in locations)
                   + '</urlset>')

    def test_valid_fixture(self):
        self.assertEqual(check.check_site(self.root), [])

    def test_external_references_do_not_require_files(self):
        for ref in ('https://natwong.dev.example.com/x.png',
                    'https://natwong.devtools.io/a', '//example.com/x.png'):
            with self.subTest(ref=ref):
                self.write_html(f'<a href="{ref}">External</a>')
                self.assertEqual(check.check_site(self.root), [])

    def test_http_same_site_reference_requires_file(self):
        self.write_html('<a href="http://natwong.dev/og.png">Image</a>')
        self.assertEqual(len(failures := check.check_site(self.root)), 1, failures)
        self.assertIn('http://natwong.dev/og.png does not exist', failures[0])
        (self.root / 'og.png').touch()
        self.assertEqual(check.check_site(self.root), [])

    def test_percent_encoded_reference_requires_decoded_file(self):
        for ref in ('my%20file.png', 'https://natwong.dev/my%20file.png'):
            with self.subTest(ref=ref):
                self.write_html(f'<a href="{ref}">Image</a>')
                self.assertTrue(any(f'{ref} does not exist' in error
                                    for error in check.check_site(self.root)))
        (self.root / 'my file.png').touch()
        for ref in ('my%20file.png', 'https://natwong.dev/my%20file.png'):
            with self.subTest(ref=ref):
                self.write_html(f'<a href="{ref}">Image</a>')
                self.assertEqual(check.check_site(self.root), [])

    def test_sitemap_rejects_noncanonical_locations_even_with_homepage(self):
        for loc in ('https://example.com/', 'https://natwong.dev.example.com/x.png',
                    'https://natwong.devtools.io/a', 'http://natwong.dev/',
                    '//natwong.dev/', '/', 'https://natwong.dev', ''):
            with self.subTest(loc=loc):
                self.write_sitemap(['https://natwong.dev/', loc])
                failures = check.check_site(self.root)
                self.assertEqual(len(failures), 1, failures)
                self.assertIn('must start with https://natwong.dev/', failures[0])

    def test_sitemap_requires_exact_homepage(self):
        for locations in ([], ['https://natwong.dev/share.png'],
                          ['https://natwong.dev/?query=1'], ['https://natwong.dev/#home']):
            with self.subTest(locations=locations):
                self.write_sitemap(locations)
                self.assertEqual(check.check_site(self.root),
                                 ['sitemap.xml: must include https://natwong.dev/ exactly'])

    def test_sitemap_checks_local_files_with_decoded_paths(self):
        self.write_sitemap(['https://natwong.dev/', 'https://natwong.dev/my%20file.png'])
        self.assertTrue(any('does not exist' in error
                            for error in check.check_site(self.root)))
        (self.root / 'my file.png').touch()
        self.assertEqual(check.check_site(self.root), [])


if __name__ == '__main__':
    unittest.main()
