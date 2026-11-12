"""ARIA reference and accessible control name regressions using stdlib fixtures."""
import tempfile
import unittest
from pathlib import Path

import check


class AriaChecksTest(unittest.TestCase):
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
</head><body><main><h1>Fixture</h1>{content}</main></body></html>'''

    def run_checks(self, content):
        (self.root / "index.html").write_text(
            self.html.replace("{content}", content), encoding="utf-8")
        check.errors.clear()
        check.check_html(self.root)
        return check.errors.copy()

    def assert_rejected(self, markup, message):
        failures = self.run_checks(markup)
        self.assertEqual(len(failures), 1, failures)
        self.assertIn(message, failures[0])
        self.assertRegex(failures[0], r"index\.html:\d+:")

    def test_dangling_aria_references(self):
        for attr in ("aria-labelledby", "aria-describedby", "aria-controls", "aria-owns"):
            with self.subTest(attr=attr):
                self.assert_rejected(
                    f'<div {attr}="present missing"></div><span id="present">Text</span>',
                    f"{attr} references #missing with no matching id")

    def test_dangling_label_for(self):
        self.assert_rejected('<label for="missing">Name</label>',
                             "for references #missing with no matching id")

    def test_forward_references_and_whitespace_separated_lists(self):
        self.assertEqual(self.run_checks('''
<label for="field">Name</label><input id="field">
<div aria-labelledby="first second" aria-describedby="first\tsecond"
aria-controls="first\nsecond" aria-owns="first second"></div>
<span id="first">First</span><span id="second">Second</span>'''), [])

    def test_icon_only_controls(self):
        for opening, closing in (('<a href="/">', '</a>'), ('<button>', '</button>')):
            with self.subTest(opening=opening):
                self.assert_rejected(
                    opening + '<svg aria-hidden="true"><title>Icon</title></svg>' + closing,
                    "without an accessible name")

    def test_empty_or_whitespace_names(self):
        for markup in ('<a href="/"> \n </a>', '<button></button>',
                       '<button aria-label=" \t " aria-labelledby=" "> </button>'):
            with self.subTest(markup=markup):
                self.assert_rejected(markup, "without an accessible name")

    def test_aria_label(self):
        self.assertEqual(self.run_checks('''
<a href="/" aria-label="Home"><svg aria-hidden="true"></svg></a>
<button aria-label="Close"></button>'''), [])

    def test_aria_labelledby(self):
        self.assertEqual(self.run_checks('''
<a href="/" aria-labelledby="name"></a><button aria-labelledby="name"></button>
<span id="name">Home</span>'''), [])

    def test_labelled_control_still_requires_valid_reference(self):
        self.assert_rejected('<button aria-labelledby="missing">Close</button>',
                             "aria-labelledby references #missing with no matching id")

    def test_image_alt_names_controls(self):
        for opening, closing in (('<a href="/">', '</a>'), ('<button>', '</button>')):
            with self.subTest(opening=opening):
                self.assertEqual(self.run_checks(
                    opening + '<img alt="Home" width="1" height="1">' + closing), [])

    def test_hidden_descendants_do_not_name_controls(self):
        for content in ('<span aria-hidden="true"><b>Hidden</b></span>',
                        '<span aria-hidden="true"><i aria-hidden="false">Hidden</i></span>',
                        '<img aria-hidden="true" alt="Hidden" width="1" height="1">',
                        '<span aria-hidden="true"><img alt="Hidden" width="1" height="1"></span>',
                        '<img alt=" " width="1" height="1">',
                        '<script>Hidden</script><style>button {color:red}</style>'):
            with self.subTest(content=content):
                self.assert_rejected('<button>' + content + '</button>',
                                     "<button> without an accessible name")

    def test_nested_text_and_sr_only_names(self):
        self.assertEqual(self.run_checks('''
<a href="/"><span class="sr-only">Home <b>page</b></span></a>
<button><svg aria-hidden="true"><title>Hidden</title></svg><span>Close</span></button>
<button><svg aria-hidden="true"/><span>Open</span></button>'''), [])

    def test_names_do_not_leak_to_sibling_controls(self):
        self.assert_rejected('<a href="/">Home</a><button> </button>Outside text',
                             "<button> without an accessible name")

    def test_anchor_without_href_is_not_a_control(self):
        self.assertEqual(self.run_checks('<a id="target"></a>'), [])


if __name__ == "__main__":
    unittest.main()
