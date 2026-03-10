"""
GROBID Paper Analysis Tool
===========================
Processes academic PDF papers using GROBID to:
  1. Generate a keyword cloud from paper abstracts
  2. Visualize the number of figures per article
  3. List all hyperlinks found in each paper

Requirements:
    pip install requests wordcloud matplotlib lxml beautifulsoup4

Usage:
    1. Start GROBID locally:
       docker run --rm -p 8070:8070 grobid/grobid:0.8.2-crf
    2. Place your PDF files in a folder (default: ./data/)
    3. Run:
       python grobid_analysis.py
       python grobid_analysis.py --pdf_dir PDF_DIR --grobid_url GROBID_URL
"""
import os
import re
import sys
import glob
import argparse
import requests
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for saving figures
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

from wordcloud import WordCloud, STOPWORDS
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
# Configuration defaults
# ─────────────────────────────────────────────
DEFAULT_GROBID_URL = "http://localhost:8070"
DEFAULT_PDF_DIR = "./data"
OUTPUT_DIR = "./results"

TEI_NS = "http://www.tei-c.org/ns/1.0"

# Extra domain-agnostic stopwords for abstracts
EXTRA_STOPWORDS = {
    "paper", "study", "propose", "proposed", "approach", "method",
    "result", "results", "show", "shown", "shows", "based", "using",
    "used", "use", "also", "however", "et", "al", "fig", "figure",
    "table", "section", "one", "two", "three", "new", "work",
    "first", "second", "third", "can", "may", "well", "thus",
    "therefore", "moreover", "furthermore", "article",
}

STOPWORDS_ALL = STOPWORDS | EXTRA_STOPWORDS


# ─────────────────────────────────────────────
# GROBID communication
# ─────────────────────────────────────────────

def process_pdf_with_grobid(pdf_path: str, grobid_url: str) -> str | None:
    """Send a single PDF to GROBID and return the TEI-XML string."""
    endpoint = f"{grobid_url}/api/processFulltextDocument"
    try:
        with open(pdf_path, "rb") as fh:
            response = requests.post(
                endpoint,
                files={"input": (os.path.basename(pdf_path), fh, "app/data")},
                data={"consolidateHeader": "1", "consolidateCitations": "0"},
                timeout=120,
            )
        if response.status_code == 200:
            return response.text
        else:
            print(f"  [WARN] GROBID returned HTTP {response.status_code} for {pdf_path}")
            return None
    except requests.exceptions.ConnectionError:
        print(
            f"\n[ERROR] Cannot connect to GROBID at {grobid_url}.\n"
            "  → Start it with:\n"
            "    docker run --rm -p 8070:8070 8070:8070 grobid/grobid:0.8.2-crf\n" 
        )
        sys.exit(1)


# ─────────────────────────────────────────────
# TEI-XML parsing helpers
# ─────────────────────────────────────────────

def parse_tei(tei_xml: str) -> BeautifulSoup:
    return BeautifulSoup(tei_xml, "xml")


def extract_title(soup: BeautifulSoup) -> str:
    tag = soup.find("titleStmt")
    if tag:
        t = tag.find("title")
        if t:
            return t.get_text(strip=True)
    return "Untitled"


def extract_abstract(soup: BeautifulSoup) -> str:
    tag = soup.find("abstract")
    if tag:
        return tag.get_text(separator=" ", strip=True)
    return ""


def extract_figure_count(soup: BeautifulSoup) -> int:
    """Count <figure> elements that are actual figures (not tables)."""
    figures = soup.find_all("figure")
    count = 0
    for fig in figures:
        fig_type = fig.get("type", "").lower()
        if fig_type != "table":
            count += 1
    return count


def extract_links(soup: BeautifulSoup) -> list[str]:
    """Extract all <ptr> and <ref type='url'> hyperlinks from TEI-XML."""
    links = []

    # <ptr target="..."/>
    for ptr in soup.find_all("ptr"):
        target = ptr.get("target", "").strip()
        if target.startswith("http"):
            links.append(target)

    # <ref type="url" target="...">
    for ref in soup.find_all("ref", {"type": "url"}):
        target = ref.get("target", "").strip()
        if target.startswith("http"):
            links.append(target)

    # plain URLs inside text nodes (fallback regex)
    full_text = soup.get_text(separator=" ")
    url_pattern = re.compile(r"https?://[^\s\]>\"']+")
    regex_urls = url_pattern.findall(full_text)
    for url in regex_urls:
        url = url.rstrip(".,);")
        if url not in links:
            links.append(url)

    return sorted(set(links))


# ─────────────────────────────────────────────
# Visualisation 
# ─────────────────────────────────────────────

PALETTE = [
    "#2563EB", "#7C3AED", "#DB2777", "#D97706",
    "#059669", "#DC2626", "#0891B2", "#65A30D",
]


def build_wordcloud(all_abstract_text: str, out_path: str) -> None:
    """Generate and save a keyword cloud from concatenated abstract text."""
    if not all_abstract_text.strip():
        print("  [WARN] No abstract text found – skipping word cloud.")
        return

    wc = WordCloud(
        width=1400,
        height=700,
        background_color="#0F172A",
        colormap="cool",
        stopwords=STOPWORDS_ALL,
        max_words=120,
        prefer_horizontal=0.85,
        collocations=False,
        min_font_size=10,
    ).generate(all_abstract_text)

    fig, ax = plt.subplots(figsize=(14, 7), facecolor="#0F172A")
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    ax.set_title(
        "Keyword Cloud — Paper Abstracts",
        color="white",
        fontsize=18,
        fontweight="bold",
        pad=16,
    )
    fig.tight_layout(pad=0.5)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="#0F172A")
    plt.close(fig)
    print(f"  ✔ Word cloud saved → {out_path}")


def build_figure_chart(paper_data: list[dict], out_path: str) -> None:
    """Bar chart: number of figures per article."""
    if not paper_data:
        print("  [WARN] No paper data – skipping figure chart.")
        return

    labels = [d["short_title"] for d in paper_data]
    counts = [d["figure_count"] for d in paper_data]
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(labels))]

    fig, ax = plt.subplots(
        figsize=(max(8, len(labels) * 1.6), 6),
        facecolor="#0F172A",
    )
    ax.set_facecolor("#1E293B")

    bars = ax.bar(labels, counts, color=colors, edgecolor="#334155", linewidth=0.8, zorder=3)

    # value labels on top of bars
    for bar, count in zip(bars, counts):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.15,
            str(count),
            ha="center",
            va="bottom",
            color="white",
            fontsize=11,
            fontweight="bold",
        )

    ax.set_xlabel("Article", color="#94A3B8", fontsize=12, labelpad=8)
    ax.set_ylabel("Number of Figures", color="#94A3B8", fontsize=12, labelpad=8)
    ax.set_title(
        "Figures per Article",
        color="white",
        fontsize=16,
        fontweight="bold",
        pad=14,
    )
    ax.tick_params(colors="#94A3B8", labelsize=9)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right", color="#CBD5E1", fontsize=9)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#334155")
    ax.grid(axis="y", color="#334155", linewidth=0.6, zorder=0)
    ax.set_ylim(0, max(counts) * 1.2 + 1 if counts else 5)

    fig.tight_layout(pad=1.5)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="#0F172A")
    plt.close(fig)
    print(f"  ✔ Figure chart saved → {out_path}")


def build_links_report(paper_data: list[dict], out_path: str) -> None:
    """Write a formatted plain-text report of links per paper."""
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("=" * 70 + "\n")
        fh.write("  LINKS FOUND IN EACH PAPER\n")
        fh.write("=" * 70 + "\n\n")

        for d in paper_data:
            fh.write(f"▸ {d['title']}\n")
            fh.write(f"  File: {d['filename']}\n")
            if d["links"]:
                for i, link in enumerate(d["links"], 1):
                    fh.write(f"  [{i:>3}] {link}\n")
            else:
                fh.write("       (no links found)\n")
            fh.write("\n")

    print(f"  ✔ Links report saved → {out_path}")


# ─────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────

def shorten_title(title: str, max_len: int = 50) -> str:
    return title if len(title) <= max_len else title[:max_len].rstrip() + "…"


def main(pdf_dir: str, grobid_url: str) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pdf_files = sorted(
        glob.glob(os.path.join(pdf_dir, "**", "*.pdf"), recursive=True)
        + glob.glob(os.path.join(pdf_dir, "*.pdf"))
    )
    pdf_files = sorted(set(pdf_files))  # deduplicate

    if not pdf_files:
        print(f"[ERROR] No PDF files found in '{pdf_dir}'.")
        print("  Place your PDF papers there and re-run.")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  GROBID Paper Analyser  –  {len(pdf_files)} PDF(s) found")
    print(f"  GROBID endpoint : {grobid_url}")
    print(f"  Output folder   : {os.path.abspath(OUTPUT_DIR)}")
    print(f"{'='*60}\n")

    all_abstract_text = []
    paper_data = []

    for idx, pdf_path in enumerate(pdf_files, 1):
        filename = os.path.basename(pdf_path)
        print(f"[{idx}/{len(pdf_files)}] Processing: {filename}")

        tei_xml = process_pdf_with_grobid(pdf_path, grobid_url)
        if tei_xml is None:
            continue

        soup = parse_tei(tei_xml)

        title = extract_title(soup)
        abstract = extract_abstract(soup)
        fig_count = extract_figure_count(soup)
        links = extract_links(soup)

        print(f"       Title    : {title[:75]}")
        print(f"       Abstract : {len(abstract)} chars")
        print(f"       Figures  : {fig_count}")
        print(f"       Links    : {len(links)}")

        if abstract:
            all_abstract_text.append(abstract)

        paper_data.append({
            "filename": filename,
            "title": title,
            "short_title": shorten_title(title),
            "abstract": abstract,
            "figure_count": fig_count,
            "links": links,
        })

    if not paper_data:
        print("\n[ERROR] No papers were successfully processed.")
        sys.exit(1)

    print(f"\n{'─'*60}")
    print("  Generating outputs …")
    print(f"{'─'*60}")

    # 1. Word cloud
    build_wordcloud(
        " ".join(all_abstract_text),
        os.path.join(OUTPUT_DIR, "wordcloud.png"),
    )

    # 2. Figure count chart
    build_figure_chart(
        paper_data,
        os.path.join(OUTPUT_DIR, "figures_per_article.png"),
    )

    # 3. Links report
    build_links_report(
        paper_data,
        os.path.join(OUTPUT_DIR, "links_report.txt"),
    )

    # 4. Quick console summary
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for d in paper_data:
        print(f"  • {d['short_title']}")
        print(f"      Figures : {d['figure_count']}")
        print(f"      Links   : {len(d['links'])}")
        print(f"      Abstract: {len(d['abstract'])} chars")
    print(f"{'='*60}")
    print(f"\n  All outputs saved in: {os.path.abspath(OUTPUT_DIR)}/\n")


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyse academic PDFs with GROBID",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--pdf_dir",
        default=DEFAULT_PDF_DIR,
        help="Directory containing the PDF papers to analyse",
    )
    parser.add_argument(
        "--grobid_url",
        default=DEFAULT_GROBID_URL,
        help="Base URL of the running GROBID instance",
    )
    args = parser.parse_args()
    main(args.pdf_dir, args.grobid_url)