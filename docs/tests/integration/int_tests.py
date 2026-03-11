"""
Integration Tests — grobid_analysis.py
========================================
These tests exercise the full pipeline against a **real, running GROBID**
instance and real PDF files on disk.

Prerequisites
─────────────
1. Start GROBID (docker recommended):
       docker run --rm -p 8070:8070 grobid/grobid:0.8.0-crf

2. Place at least one PDF in the directory pointed to by GROBID_TEST_PDF_DIR
   (default: ./data/).  A single real academic PDF is enough.

3. Optionally override env-vars:
       GROBID_URL=http://localhost:8070
       GROBID_TEST_PDF_DIR=./data

Run:
    python3 -m unittest test_integration -v

If GROBID is unreachable, every test in this module is *skipped* gracefully
rather than erroring, so the unit-test suite stays green in CI.
"""

import os
import sys
import glob
import types
import shutil
import tempfile
import unittest

import requests

# ─────────────────────────────────────────────────────────────────────────────
# Configuration from environment (override as needed)
# ─────────────────────────────────────────────────────────────────────────────
GROBID_URL = os.environ.get("GROBID_URL", "http://localhost:8070")
PDF_DIR = os.environ.get("GROBID_TEST_PDF_DIR", "./docs/data")

# ─────────────────────────────────────────────────────────────────────────────
# wordcloud import strategy
#
# Integration tests run against the real environment, so we always prefer the
# genuine 'wordcloud' package — that's what the application itself uses.
# The stub below is only injected when the package is genuinely absent (e.g. a
# bare CI runner that has GROBID but not wordcloud installed).
#
# KEY DIFFERENCE from the unit-test stub: if we do have to fake it, generate()
# must return a proper H×W×3 uint8 numpy array, otherwise matplotlib's
# ax.imshow() raises "Image data of dtype object cannot be converted to float".
# ─────────────────────────────────────────────────────────────────────────────
try:
    import wordcloud as _wc_real  # noqa: F401 — just testing availability
except ImportError:
    import numpy as _np

    _wc_stub = types.ModuleType("wordcloud")

    class _FakeWordCloud:
        STOPWORDS = set()

        def __init__(self, width: int = 800, height: int = 400, **kw):
            self._w = width
            self._h = height
            self._image = _np.zeros((height, width, 3), dtype=_np.uint8)

        def generate(self, text: str) -> "_FakeWordCloud":
            # Non-zero pixels so the saved PNG is distinguishable from empty
            self._image[:] = 42
            return self

        # ax.imshow(wc) internally calls np.asarray() — this makes it work
        def __array__(self, dtype=None):
            return self._image if dtype is None else self._image.astype(dtype)

    _wc_stub.WordCloud = _FakeWordCloud
    _wc_stub.STOPWORDS = set()
    sys.modules["wordcloud"] = _wc_stub

import src.grobid_analysis as ga  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _grobid_is_alive(url: str, timeout: int = 5) -> bool:
    """Return True if GROBID's /api/isalive endpoint responds with HTTP 200."""
    try:
        r = requests.get(f"{url}/api/isalive", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def _find_pdfs(directory: str) -> list[str]:
    return sorted(
        set(
            glob.glob(os.path.join(directory, "**", "*.pdf"), recursive=True)
            + glob.glob(os.path.join(directory, "*.pdf"))
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# Module-level skip decorators (evaluated once at collection time)
# ─────────────────────────────────────────────────────────────────────────────

_GROBID_ALIVE = _grobid_is_alive(GROBID_URL)
_PDFS_PRESENT = bool(_find_pdfs(PDF_DIR))

skip_no_grobid = unittest.skipUnless(
    _GROBID_ALIVE,
    f"GROBID not reachable at {GROBID_URL} — start it and re-run",
)
skip_no_pdfs = unittest.skipUnless(
    _PDFS_PRESENT,
    f"No PDF files found in '{PDF_DIR}' — add at least one and re-run",
)
skip_integration = unittest.skipUnless(
    _GROBID_ALIVE and _PDFS_PRESENT,
    "Integration tests require both a live GROBID and at least one PDF",
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. GROBID connectivity
# ─────────────────────────────────────────────────────────────────────────────

@skip_no_grobid
class TestGrobidConnectivity(unittest.TestCase):
    """Verify the GROBID service is correctly configured and reachable."""

    def test_isalive_returns_200(self):
        r = requests.get(f"{GROBID_URL}/api/isalive", timeout=10)
        self.assertEqual(r.status_code, 200)

    def test_processFulltextDocument_endpoint_exists(self):
        """A malformed POST should not return 404 — the endpoint must exist."""
        try:
            r = requests.post(
                f"{GROBID_URL}/api/processFulltextDocument",
                data={},
                timeout=10,
            )
            self.assertNotEqual(r.status_code, 404)
        except requests.exceptions.ConnectionError:
            self.fail("Could not connect to GROBID processFulltextDocument endpoint")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Single-PDF processing
# ─────────────────────────────────────────────────────────────────────────────

@skip_integration
class TestSinglePdfProcessing(unittest.TestCase):
    """Send one real PDF through GROBID and check what comes back."""

    @classmethod
    def setUpClass(cls):
        cls.pdf_path = _find_pdfs(PDF_DIR)[0]
        print(f"\n  [integration] Using PDF: {cls.pdf_path}")
        cls.tei_xml = ga.process_pdf_with_grobid(cls.pdf_path, GROBID_URL)
        cls.soup = ga.parse_tei(cls.tei_xml) if cls.tei_xml else None

    def test_grobid_returns_non_empty_response(self):
        self.assertIsNotNone(self.tei_xml)
        self.assertGreater(len(self.tei_xml), 0)

    def test_response_is_valid_tei_xml(self):
        self.assertIn("<TEI", self.tei_xml)

    def test_title_is_non_empty_string(self):
        title = ga.extract_title(self.soup)
        self.assertIsInstance(title, str)
        self.assertGreater(len(title), 0)

    def test_title_is_not_placeholder(self):
        """GROBID should extract a real title, not 'Untitled'."""
        title = ga.extract_title(self.soup)
        self.assertNotEqual(
            title, "Untitled",
            "GROBID returned 'Untitled' — the PDF may have no machine-readable title",
        )

    def test_abstract_is_string(self):
        self.assertIsInstance(ga.extract_abstract(self.soup), str)

    def test_figure_count_is_non_negative_integer(self):
        count = ga.extract_figure_count(self.soup)
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    def test_links_is_a_list_of_strings(self):
        links = ga.extract_links(self.soup)
        self.assertIsInstance(links, list)
        for link in links:
            self.assertIsInstance(link, str)

    def test_all_extracted_links_start_with_http(self):
        for link in ga.extract_links(self.soup):
            self.assertTrue(
                link.startswith("http"),
                f"Unexpected non-http link: {link}",
            )

    def test_links_are_deduplicated(self):
        links = ga.extract_links(self.soup)
        self.assertEqual(len(links), len(set(links)))

    def test_links_are_sorted(self):
        links = ga.extract_links(self.soup)
        self.assertEqual(links, sorted(links))


# ─────────────────────────────────────────────────────────────────────────────
# 3. Full pipeline — main() writes real output files
# ─────────────────────────────────────────────────────────────────────────────

@skip_integration
class TestFullPipeline(unittest.TestCase):
    """
    Run main() end-to-end against real GROBID and real PDFs.
    Checks that all three output artefacts are produced and well-formed.
    """

    @classmethod
    def setUpClass(cls):
        cls.out_dir = tempfile.mkdtemp(prefix="grobid_integration_")
        cls._original_out_dir = ga.DEFAULT_OUTPUT_DIR
        ga.DEFAULT_OUTPUT_DIR = cls.out_dir
        print(f"\n  [integration] Output dir: {cls.out_dir}")
        ga.main(PDF_DIR, GROBID_URL, cls.out_dir)

    @classmethod
    def tearDownClass(cls):
        ga.DEFAULT_OUTPUT_DIR = cls._original_out_dir
        shutil.rmtree(cls.out_dir, ignore_errors=True)

    # ── existence ────────────────────────────────────────────────────────────

    def test_wordcloud_png_created(self):
        self.assertTrue(
            os.path.exists(os.path.join(self.out_dir, "wordcloud.png")),
            "wordcloud.png was not created",
        )

    def test_figures_chart_png_created(self):
        self.assertTrue(
            os.path.exists(os.path.join(self.out_dir, "figures_per_article.png")),
            "figures_per_article.png was not created",
        )

    def test_links_report_txt_created(self):
        self.assertTrue(
            os.path.exists(os.path.join(self.out_dir, "links_report.txt")),
            "links_report.txt was not created",
        )

    # ── size / content ───────────────────────────────────────────────────────

    def test_wordcloud_png_is_non_empty(self):
        self.assertGreater(
            os.path.getsize(os.path.join(self.out_dir, "wordcloud.png")), 0
        )

    def test_figures_chart_is_non_empty(self):
        self.assertGreater(
            os.path.getsize(os.path.join(self.out_dir, "figures_per_article.png")), 0
        )

    def test_links_report_contains_header(self):
        with open(os.path.join(self.out_dir, "links_report.txt"), encoding="utf-8") as fh:
            self.assertIn("LINKS FOUND IN EACH PAPER", fh.read())

    def test_links_report_mentions_each_pdf(self):
        with open(os.path.join(self.out_dir, "links_report.txt"), encoding="utf-8") as fh:
            content = fh.read()
        for pdf in _find_pdfs(PDF_DIR):
            filename = os.path.basename(pdf)
            self.assertIn(filename, content, f"PDF '{filename}' not mentioned in links report")

    # ── magic-bytes sanity ───────────────────────────────────────────────────

    def test_wordcloud_png_has_valid_png_header(self):
        with open(os.path.join(self.out_dir, "wordcloud.png"), "rb") as fh:
            self.assertEqual(fh.read(4), b"\x89PNG",
                "wordcloud.png does not begin with PNG magic bytes")

    def test_figures_chart_has_valid_png_header(self):
        with open(os.path.join(self.out_dir, "figures_per_article.png"), "rb") as fh:
            self.assertEqual(fh.read(4), b"\x89PNG",
                "figures_per_article.png does not begin with PNG magic bytes")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Multi-PDF consistency checks
# ─────────────────────────────────────────────────────────────────────────────

@skip_integration
class TestMultiPdfConsistency(unittest.TestCase):
    """
    Process every PDF in PDF_DIR individually and verify cross-paper invariants.
    """

    @classmethod
    def setUpClass(cls):
        cls.pdfs = _find_pdfs(PDF_DIR)
        cls.results = []
        for pdf in cls.pdfs:
            tei_xml = ga.process_pdf_with_grobid(pdf, GROBID_URL)
            if tei_xml is None:
                continue
            s = ga.parse_tei(tei_xml)
            cls.results.append({
                "filename": os.path.basename(pdf),
                "title": ga.extract_title(s),
                "abstract": ga.extract_abstract(s),
                "figure_count": ga.extract_figure_count(s),
                "links": ga.extract_links(s),
            })

    def test_at_least_one_paper_processed(self):
        self.assertGreater(
            len(self.results), 0,
            "GROBID failed to process any PDF — check GROBID logs",
        )

    def test_every_paper_has_a_non_empty_title(self):
        for r in self.results:
            with self.subTest(file=r["filename"]):
                self.assertGreater(len(r["title"]), 0)

    def test_figure_counts_are_all_non_negative(self):
        for r in self.results:
            with self.subTest(file=r["filename"]):
                self.assertGreaterEqual(r["figure_count"], 0)

    def test_all_links_are_valid_http_urls(self):
        for r in self.results:
            for link in r["links"]:
                with self.subTest(file=r["filename"], link=link):
                    self.assertTrue(
                        link.startswith("http"),
                        f"Non-http link found: {link}",
                    )

    def test_no_duplicate_links_per_paper(self):
        for r in self.results:
            with self.subTest(file=r["filename"]):
                self.assertEqual(len(r["links"]), len(set(r["links"])))

    def test_titles_are_unique_across_papers(self):
        if len(self.results) < 2:
            self.skipTest("Need at least 2 PDFs to check title uniqueness")
        titles = [r["title"] for r in self.results]
        self.assertEqual(
            len(titles), len(set(titles)),
            "Two or more papers share the same extracted title",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)