"""
Unit Tests — grobid_analysis.py
=================================
All external I/O (network, filesystem, matplotlib, wordcloud) is mocked.
No running GROBID instance or PDF files are required.

Run:
    python3 -m unittest test_unit -v
"""

import os
import sys
import types
import textwrap
import unittest
from io import StringIO
from contextlib import ExitStack
from unittest.mock import patch, MagicMock, mock_open

# ─────────────────────────────────────────────────────────────────────────────
# Stub 'wordcloud' before importing the module under test so the suite runs
# even when the package is not installed.
# ─────────────────────────────────────────────────────────────────────────────
_wc_stub = types.ModuleType("wordcloud")

class _FakeWordCloud:
    STOPWORDS = set()
    def __init__(self, **kwargs): self._kwargs = kwargs
    def generate(self, text):
        self._text = text
        return self

_wc_stub.WordCloud = _FakeWordCloud
_wc_stub.STOPWORDS = set()
sys.modules.setdefault("wordcloud", _wc_stub)

import src.grobid_analysis as ga


# ─────────────────────────────────────────────────────────────────────────────
# TEI-XML fixtures
# ─────────────────────────────────────────────────────────────────────────────

FULL_TEI = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <TEI xmlns="http://www.tei-c.org/ns/1.0">
      <teiHeader>
        <fileDesc>
          <titleStmt>
            <title>Deep Learning for Natural Language Processing</title>
          </titleStmt>
        </fileDesc>
      </teiHeader>
      <text>
        <front>
          <abstract>
            <p>We propose a novel transformer-based approach to NLP tasks.
               Our method achieves state-of-the-art results on multiple benchmarks.</p>
          </abstract>
        </front>
        <body>
          <figure xml:id="fig_1"><head>Figure 1</head><figDesc>Model architecture</figDesc></figure>
          <figure xml:id="fig_2"><head>Figure 2</head><figDesc>Training curves</figDesc></figure>
          <figure xml:id="tab_1" type="table"><head>Table 1</head><figDesc>Results</figDesc></figure>
          <ptr target="https://github.com/example/repo"/>
          <ref type="url" target="https://arxiv.org/abs/1234.5678"/>
        </body>
      </text>
    </TEI>
""")

MINIMAL_TEI = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <TEI xmlns="http://www.tei-c.org/ns/1.0">
      <teiHeader><fileDesc><titleStmt></titleStmt></fileDesc></teiHeader>
      <text><body></body></text>
    </TEI>
""")

NO_FIGURES_TEI = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <TEI xmlns="http://www.tei-c.org/ns/1.0">
      <teiHeader><fileDesc><titleStmt>
        <title>A Paper Without Figures</title>
      </titleStmt></fileDesc></teiHeader>
      <text>
        <front><abstract><p>Abstract text here.</p></abstract></front>
        <body></body>
      </text>
    </TEI>
""")

TABLES_ONLY_TEI = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <TEI xmlns="http://www.tei-c.org/ns/1.0">
      <teiHeader><fileDesc><titleStmt><title>Tables Only</title></titleStmt></fileDesc></teiHeader>
      <text><body>
        <figure type="table"><head>Table 1</head></figure>
        <figure type="table"><head>Table 2</head></figure>
      </body></text>
    </TEI>
""")

LINKS_TEI = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <TEI xmlns="http://www.tei-c.org/ns/1.0">
      <teiHeader><fileDesc><titleStmt><title>Links Paper</title></titleStmt></fileDesc></teiHeader>
      <text><body>
        <ptr target="https://ptr-link.com/path"/>
        <ref type="url" target="https://ref-link.org/page"/>
        <p>Visit https://inline-link.io/resource for details.</p>
      </body></text>
    </TEI>
""")


def soup(tei_xml: str):
    return ga.parse_tei(tei_xml)


# ─────────────────────────────────────────────────────────────────────────────
# parse_tei
# ─────────────────────────────────────────────────────────────────────────────

class TestParseTei(unittest.TestCase):

    def test_returns_beautifulsoup_object(self):
        from bs4 import BeautifulSoup
        self.assertIsInstance(ga.parse_tei(FULL_TEI), BeautifulSoup)

    def test_finds_title_tag(self):
        self.assertIsNotNone(ga.parse_tei(FULL_TEI).find("title"))

    def test_invalid_xml_does_not_raise(self):
        self.assertIsNotNone(ga.parse_tei("<broken><unclosed>"))

    def test_empty_string_does_not_raise(self):
        self.assertIsNotNone(ga.parse_tei(""))


# ─────────────────────────────────────────────────────────────────────────────
# extract_title
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractTitle(unittest.TestCase):

    def test_extracts_title_correctly(self):
        self.assertEqual(
            ga.extract_title(soup(FULL_TEI)),
            "Deep Learning for Natural Language Processing",
        )

    def test_returns_untitled_when_no_titlestmt(self):
        self.assertEqual(ga.extract_title(soup("<TEI/>")), "Untitled")

    def test_returns_untitled_when_title_tag_missing(self):
        tei = textwrap.dedent("""\
            <TEI xmlns="http://www.tei-c.org/ns/1.0">
              <teiHeader><fileDesc><titleStmt></titleStmt></fileDesc></teiHeader>
            </TEI>
        """)
        self.assertEqual(ga.extract_title(soup(tei)), "Untitled")

    def test_strips_whitespace(self):
        tei = textwrap.dedent("""\
            <TEI xmlns="http://www.tei-c.org/ns/1.0">
              <teiHeader><fileDesc><titleStmt>
                <title>  Spaced Title  </title>
              </titleStmt></fileDesc></teiHeader>
            </TEI>
        """)
        self.assertEqual(ga.extract_title(soup(tei)), "Spaced Title")

    def test_minimal_tei_returns_untitled(self):
        self.assertEqual(ga.extract_title(soup(MINIMAL_TEI)), "Untitled")


# ─────────────────────────────────────────────────────────────────────────────
# extract_abstract
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractAbstract(unittest.TestCase):

    def test_extracts_abstract_text(self):
        abstract = ga.extract_abstract(soup(FULL_TEI))
        self.assertIn("transformer-based", abstract)
        self.assertIn("NLP tasks", abstract)

    def test_returns_empty_string_when_no_abstract(self):
        self.assertEqual(ga.extract_abstract(soup(MINIMAL_TEI)), "")

    def test_returns_empty_string_for_empty_tei(self):
        self.assertEqual(ga.extract_abstract(soup("<TEI/>")), "")

    def test_abstract_is_string(self):
        self.assertIsInstance(ga.extract_abstract(soup(FULL_TEI)), str)

    def test_abstract_has_no_surrounding_whitespace(self):
        abstract = ga.extract_abstract(soup(FULL_TEI))
        self.assertEqual(abstract.strip(), abstract)


# ─────────────────────────────────────────────────────────────────────────────
# extract_figure_count
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractFigureCount(unittest.TestCase):

    def test_counts_only_non_table_figures(self):
        # FULL_TEI: 2 real figures + 1 table → expect 2
        self.assertEqual(ga.extract_figure_count(soup(FULL_TEI)), 2)

    def test_tables_only_returns_zero(self):
        self.assertEqual(ga.extract_figure_count(soup(TABLES_ONLY_TEI)), 0)

    def test_no_figures_returns_zero(self):
        self.assertEqual(ga.extract_figure_count(soup(NO_FIGURES_TEI)), 0)

    def test_returns_integer(self):
        self.assertIsInstance(ga.extract_figure_count(soup(FULL_TEI)), int)

    def test_figure_without_type_attribute_is_counted(self):
        tei = textwrap.dedent("""\
            <TEI xmlns="http://www.tei-c.org/ns/1.0">
              <text><body>
                <figure><head>Fig 1</head></figure>
                <figure><head>Fig 2</head></figure>
              </body></text>
            </TEI>
        """)
        self.assertEqual(ga.extract_figure_count(soup(tei)), 2)

    def test_type_table_comparison_is_case_insensitive(self):
        tei = textwrap.dedent("""\
            <TEI xmlns="http://www.tei-c.org/ns/1.0">
              <text><body>
                <figure type="TABLE"><head>Big Table</head></figure>
                <figure type="Table"><head>Another Table</head></figure>
              </body></text>
            </TEI>
        """)
        self.assertEqual(ga.extract_figure_count(soup(tei)), 0)


# ─────────────────────────────────────────────────────────────────────────────
# extract_links
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractLinks(unittest.TestCase):

    def test_extracts_ptr_links(self):
        self.assertIn("https://github.com/example/repo", ga.extract_links(soup(FULL_TEI)))

    def test_extracts_ref_url_links(self):
        self.assertIn("https://arxiv.org/abs/1234.5678", ga.extract_links(soup(FULL_TEI)))

    def test_extracts_all_three_link_types(self):
        links = ga.extract_links(soup(LINKS_TEI))
        self.assertIn("https://ptr-link.com/path", links)
        self.assertIn("https://ref-link.org/page", links)
        self.assertIn("https://inline-link.io/resource", links)

    def test_returns_sorted_unique_list(self):
        links = ga.extract_links(soup(FULL_TEI))
        self.assertEqual(links, sorted(set(links)))

    def test_no_links_returns_empty_list(self):
        self.assertEqual(ga.extract_links(soup(MINIMAL_TEI)), [])

    def test_returns_list(self):
        self.assertIsInstance(ga.extract_links(soup(FULL_TEI)), list)

    def test_strips_trailing_punctuation_from_regex_urls(self):
        tei = textwrap.dedent("""\
            <TEI xmlns="http://www.tei-c.org/ns/1.0">
              <text><body><p>See https://example.com/page. for details.</p></body></text>
            </TEI>
        """)
        links = ga.extract_links(soup(tei))
        self.assertFalse(any(lnk.endswith(".") for lnk in links))
        self.assertTrue(any("https://example.com/page" in lnk for lnk in links))

    def test_ignores_non_http_targets(self):
        tei = textwrap.dedent("""\
            <TEI xmlns="http://www.tei-c.org/ns/1.0">
              <text><body>
                <ptr target="ftp://old.server.com/file"/>
                <ptr target="mailto:author@example.com"/>
                <ptr target="https://valid.com"/>
              </body></text>
            </TEI>
        """)
        links = ga.extract_links(soup(tei))
        self.assertNotIn("ftp://old.server.com/file", links)
        self.assertNotIn("mailto:author@example.com", links)
        self.assertIn("https://valid.com", links)


# ─────────────────────────────────────────────────────────────────────────────
# shorten_title
# ─────────────────────────────────────────────────────────────────────────────

class TestShortenTitle(unittest.TestCase):

    def test_short_title_unchanged(self):
        t = "Short Title"
        self.assertEqual(ga.shorten_title(t), t)

    def test_exactly_max_len_unchanged(self):
        t = "A" * 50
        self.assertEqual(ga.shorten_title(t), t)

    def test_long_title_ends_with_ellipsis(self):
        self.assertTrue(ga.shorten_title("A" * 80).endswith("…"))

    def test_truncated_respects_custom_max_len(self):
        result = ga.shorten_title("Word " * 20, max_len=20)
        self.assertLessEqual(len(result.rstrip("…")), 20)

    def test_custom_max_len_adds_ellipsis(self):
        result = ga.shorten_title("Hello World This Is A Long Title", max_len=10)
        self.assertTrue(result.endswith("…"))

    def test_empty_string(self):
        self.assertEqual(ga.shorten_title(""), "")


# ─────────────────────────────────────────────────────────────────────────────
# process_pdf_with_grobid  (network mocked)
# ─────────────────────────────────────────────────────────────────────────────

class TestProcessPdfWithGrobid(unittest.TestCase):

    @patch("src.grobid_analysis.requests.post")
    @patch("builtins.open", mock_open(read_data=b"%PDF-1.4"))
    def test_returns_tei_xml_on_200(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, text=FULL_TEI)
        self.assertEqual(
            ga.process_pdf_with_grobid("paper.pdf", "http://localhost:8070"),
            FULL_TEI,
        )

    @patch("src.grobid_analysis.requests.post")
    @patch("builtins.open", mock_open(read_data=b"%PDF-1.4"))
    def test_returns_none_on_non_200(self, mock_post):
        mock_post.return_value = MagicMock(status_code=503)
        self.assertIsNone(ga.process_pdf_with_grobid("paper.pdf", "http://localhost:8070"))

    @patch(
        "src.grobid_analysis.requests.post",
        side_effect=__import__("requests").exceptions.ConnectionError,
    )
    @patch("builtins.open", mock_open(read_data=b"%PDF-1.4"))
    def test_exits_on_connection_error(self, mock_post):
        with self.assertRaises(SystemExit):
            ga.process_pdf_with_grobid("paper.pdf", "http://localhost:8070")

    @patch("src.grobid_analysis.requests.post")
    @patch("builtins.open", mock_open(read_data=b"%PDF-1.4"))
    def test_posts_to_correct_endpoint(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, text="")
        ga.process_pdf_with_grobid("paper.pdf", "http://grobid.server:8080")
        self.assertEqual(
            mock_post.call_args[0][0],
            "http://grobid.server:8080/api/processFulltextDocument",
        )

    @patch("src.grobid_analysis.requests.post")
    @patch("builtins.open", mock_open(read_data=b"%PDF-1.4"))
    def test_sends_consolidate_header_param(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, text="")
        ga.process_pdf_with_grobid("paper.pdf", "http://localhost:8070")
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["data"]["consolidateHeader"], "1")


# ─────────────────────────────────────────────────────────────────────────────
# build_links_report  (filesystem mocked)
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildLinksReport(unittest.TestCase):

    SAMPLE_DATA = [
        {"title": "Paper One", "filename": "paper1.pdf", "links": ["https://a.com", "https://b.com"]},
        {"title": "Paper Two", "filename": "paper2.pdf", "links": []},
    ]

    def _capture(self, data):
        with patch("builtins.open", mock_open()) as m:
            ga.build_links_report(data, "/fake/links_report.txt")
            return "".join(c.args[0] for c in m().write.call_args_list)

    def test_contains_all_titles(self):
        content = self._capture(self.SAMPLE_DATA)
        self.assertIn("Paper One", content)
        self.assertIn("Paper Two", content)

    def test_contains_links(self):
        content = self._capture(self.SAMPLE_DATA)
        self.assertIn("https://a.com", content)
        self.assertIn("https://b.com", content)

    def test_shows_no_links_message(self):
        self.assertIn("no links found", self._capture(self.SAMPLE_DATA))

    def test_contains_filenames(self):
        content = self._capture(self.SAMPLE_DATA)
        self.assertIn("paper1.pdf", content)
        self.assertIn("paper2.pdf", content)

    def test_written_to_correct_path(self):
        with patch("builtins.open", mock_open()) as m:
            ga.build_links_report(self.SAMPLE_DATA, "/some/path/links.txt")
            m.assert_called_once_with("/some/path/links.txt", "w", encoding="utf-8")

    def test_empty_data_writes_header(self):
        self.assertIn("LINKS FOUND IN EACH PAPER", self._capture([]))


# ─────────────────────────────────────────────────────────────────────────────
# build_wordcloud  (matplotlib + wordcloud mocked)
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildWordcloud(unittest.TestCase):

    def _mock_wc(self):
        inst = MagicMock()
        inst.generate.return_value = inst
        return inst

    @patch("src.grobid_analysis.plt")
    @patch("src.grobid_analysis.WordCloud")
    def test_saves_to_expected_path(self, MockWC, mock_plt):
        MockWC.return_value = self._mock_wc()
        fig = MagicMock()
        mock_plt.subplots.return_value = (fig, MagicMock())
        ga.build_wordcloud("neural networks deep learning", "/out/wordcloud.png")
        self.assertEqual(fig.savefig.call_args[0][0], "/out/wordcloud.png")

    @patch("src.grobid_analysis.plt")
    @patch("src.grobid_analysis.WordCloud")
    def test_skips_on_empty_text(self, MockWC, mock_plt):
        ga.build_wordcloud("   ", "/out/wordcloud.png")
        MockWC.assert_not_called()
        mock_plt.subplots.assert_not_called()

    @patch("src.grobid_analysis.plt")
    @patch("src.grobid_analysis.WordCloud")
    def test_calls_generate_with_text(self, MockWC, mock_plt):
        inst = self._mock_wc()
        MockWC.return_value = inst
        mock_plt.subplots.return_value = (MagicMock(), MagicMock())
        ga.build_wordcloud("machine learning transformers", "/out/wc.png")
        inst.generate.assert_called_once_with("machine learning transformers")

    @patch("src.grobid_analysis.plt")
    @patch("src.grobid_analysis.WordCloud")
    def test_closes_figure_after_save(self, MockWC, mock_plt):
        MockWC.return_value = self._mock_wc()
        fig = MagicMock()
        mock_plt.subplots.return_value = (fig, MagicMock())
        ga.build_wordcloud("some text", "/out/wc.png")
        mock_plt.close.assert_called_once_with(fig)


# ─────────────────────────────────────────────────────────────────────────────
# build_figure_chart  (matplotlib mocked)
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildFigureChart(unittest.TestCase):

    DATA = [
        {"short_title": "Paper A", "figure_count": 3},
        {"short_title": "Paper B", "figure_count": 0},
        {"short_title": "Paper C", "figure_count": 7},
    ]

    def _setup_plt(self, mock_plt):
        fig, ax = MagicMock(), MagicMock()
        ax.bar.return_value = [MagicMock() for _ in self.DATA]
        mock_plt.subplots.return_value = (fig, ax)
        mock_plt.MaxNLocator.return_value = MagicMock()
        return fig, ax

    @patch("src.grobid_analysis.plt")
    def test_saves_to_expected_path(self, mock_plt):
        fig, _ = self._setup_plt(mock_plt)
        ga.build_figure_chart(self.DATA, "/out/figures.png")
        self.assertEqual(fig.savefig.call_args[0][0], "/out/figures.png")

    @patch("src.grobid_analysis.plt")
    def test_skips_on_empty_data(self, mock_plt):
        ga.build_figure_chart([], "/out/figures.png")
        mock_plt.subplots.assert_not_called()

    @patch("src.grobid_analysis.plt")
    def test_passes_correct_labels_and_counts(self, mock_plt):
        _, ax = self._setup_plt(mock_plt)
        ga.build_figure_chart(self.DATA, "/out/figures.png")
        labels, counts = ax.bar.call_args[0][0], ax.bar.call_args[0][1]
        self.assertEqual(labels, ["Paper A", "Paper B", "Paper C"])
        self.assertEqual(counts, [3, 0, 7])

    @patch("src.grobid_analysis.plt")
    def test_closes_figure_after_save(self, mock_plt):
        fig, _ = self._setup_plt(mock_plt)
        ga.build_figure_chart(self.DATA, "/out/figures.png")
        mock_plt.close.assert_called_once_with(fig)


# ─────────────────────────────────────────────────────────────────────────────
# main() orchestration  (everything mocked)
# ─────────────────────────────────────────────────────────────────────────────

class TestMainOrchestration(unittest.TestCase):

    def _patch_all(self, pdf_files, grobid_return=FULL_TEI):
        return [
            patch("src.grobid_analysis.os.makedirs"),
            patch("src.grobid_analysis.glob.glob", return_value=pdf_files),
            patch("src.grobid_analysis.process_pdf_with_grobid", return_value=grobid_return),
            patch("src.grobid_analysis.build_wordcloud"),
            patch("src.grobid_analysis.build_figure_chart"),
            patch("src.grobid_analysis.build_links_report"),
        ]

    def test_calls_all_three_output_builders(self):
        patches = self._patch_all(["p1.pdf", "p2.pdf"])
        with ExitStack() as stack:
            mocks = [stack.enter_context(p) for p in patches]
            ga.main("./docs/data", "http://localhost:8070", "./docs/results")
            wc, chart, links = mocks[3], mocks[4], mocks[5]
            wc.assert_called_once()
            chart.assert_called_once()
            links.assert_called_once()

    def test_exits_when_no_pdfs_found(self):
        patches = self._patch_all([])
        with ExitStack() as stack:
            [stack.enter_context(p) for p in patches]
            with self.assertRaises(SystemExit):
                ga.main("./empty", "http://localhost:8070", "./docs/results")

    def test_exits_when_all_grobid_calls_fail(self):
        patches = self._patch_all(["bad.pdf"], grobid_return=None)
        with ExitStack() as stack:
            [stack.enter_context(p) for p in patches]
            with self.assertRaises(SystemExit):
                ga.main("./docs/data", "http://localhost:8070", "./docs/results")

    def test_deduplicates_pdf_list(self):
        patches = self._patch_all(["p1.pdf", "p1.pdf", "p2.pdf"])
        with ExitStack() as stack:
            mocks = [stack.enter_context(p) for p in patches]
            ga.main("./docs/data", "http://localhost:8070", "./docs/results")
            # p1.pdf deduplicated → only 2 unique PDFs processed
            self.assertEqual(mocks[2].call_count, 2)

    def test_paper_data_has_expected_keys(self):
        patches = self._patch_all(["paper.pdf"])
        with ExitStack() as stack:
            mocks = [stack.enter_context(p) for p in patches]
            ga.main("./docs/data", "http://localhost:8070", "./docs/results")
            chart_data = mocks[4].call_args[0][0]
            self.assertIsInstance(chart_data, list)
            self.assertEqual(len(chart_data), 1)
            for key in ("figure_count", "links", "title", "abstract"):
                self.assertIn(key, chart_data[0])


# ─────────────────────────────────────────────────────────────────────────────
# STOPWORDS_ALL constant
# ─────────────────────────────────────────────────────────────────────────────

class TestStopwords(unittest.TestCase):

    def test_extra_stopwords_present(self):
        for word in ("paper", "study", "propose", "method"):
            with self.subTest(word=word):
                self.assertIn(word, ga.STOPWORDS_ALL)

    def test_stopwords_all_is_set(self):
        self.assertIsInstance(ga.STOPWORDS_ALL, set)

    def test_stopwords_all_is_superset_of_extra(self):
        self.assertTrue(ga.EXTRA_STOPWORDS.issubset(ga.STOPWORDS_ALL))


if __name__ == "__main__":
    unittest.main(verbosity=2)