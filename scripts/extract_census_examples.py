"""
Download official Census API example pages and write markdown summaries.

Each source page is saved as a markdown file under the app_description directory
containing every example URL listed in the source HTML table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Sequence
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Tag


@dataclass(frozen=True)
class SourcePage:
    slug: str
    url: str


SOURCE_PAGES: Sequence[SourcePage] = (
    SourcePage(
        slug="2023_acs_acs5_examples",
        url="https://api.census.gov/data/2023/acs/acs5/examples.html",
    ),
    SourcePage(
        slug="2023_acs_acs5_profile_examples",
        url="https://api.census.gov/data/2023/acs/acs5/profile/examples.html",
    ),
    SourcePage(
        slug="2023_acs_acs5_cprofile_examples",
        url="https://api.census.gov/data/2023/acs/acs5/cprofile/examples.html",
    ),
    SourcePage(
        slug="2023_acs_acs5_subject_examples",
        url="https://api.census.gov/data/2023/acs/acs5/subject/examples.html",
    ),
    SourcePage(
        slug="2024_acs_acs1_spp_geography",
        url="https://api.census.gov/data/2024/acs/acs1/spp/geography.html",
    ),
)

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = WORKSPACE_ROOT / "app_description"


def extract_cell_text(cell: Tag, base_url: str) -> str:
    """Return the most useful text from a table cell."""
    link = cell.find("a", href=True)
    if link and link.get("href", "").strip():
        href = link["href"].strip()
        if href.startswith(("http://", "https://")):
            return href
        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        return base + href

    code = cell.find("code")
    if code:
        return code.get_text(" ", strip=True)

    return cell.get_text(" ", strip=True)


def parse_table(
    table: Tag, base_url: str
) -> tuple[List[str], List[str], List[List[str]]]:
    """Parse a single HTML table into headers, notes, and data rows."""
    rows = table.find_all("tr")
    if not rows:
        return [], [], []

    header_cells = rows[0].find_all(["th", "td"])
    headers = [cell.get_text(" ", strip=True) for cell in header_cells]

    notes: List[str] = []
    data_rows: List[List[str]] = []
    current_values: List[str] = [""] * len(headers)

    for row in rows[1:]:
        cells = row.find_all(["th", "td"])
        if not cells:
            continue

        cell_texts = [extract_cell_text(cell, base_url) for cell in cells]

        if len(cell_texts) == 1 and len(headers) > 1:
            note_text = cell_texts[0].strip()
            if note_text:
                notes.append(note_text)
            continue

        new_values = current_values.copy()

        if len(cell_texts) == len(headers):
            for idx, text in enumerate(cell_texts):
                text = text.strip()
                if text:
                    new_values[idx] = text
        elif len(cell_texts) < len(headers):
            start = len(headers) - len(cell_texts)
            for offset, text in enumerate(cell_texts):
                text = text.strip()
                if text:
                    new_values[start + offset] = text
        else:
            for idx, text in enumerate(cell_texts[: len(headers)]):
                text = text.strip()
                if text:
                    new_values[idx] = text

        if any(value.strip() for value in new_values):
            data_rows.append(new_values.copy())
            current_values = new_values

    return headers, notes, data_rows


def build_markdown(
    title: str, url: str, headers: List[str], notes: List[str], rows: List[List[str]]
) -> str:
    """Render a markdown document for a parsed table."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
    lines: List[str] = []

    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- Source: {url}")
    lines.append(f"- Retrieved: {timestamp}")

    if notes:
        lines.append("- Notes:")
        for note in notes:
            lines.append(f"  - {note}")

    lines.append("")
    lines.append("## Table 1")
    lines.append("")

    if not headers or not rows:
        lines.append("_No table data found._")
        lines.append("")
        return "\n".join(lines)

    header_line = " | ".join(header.replace("|", "\\|") for header in headers)
    separator_line = " | ".join("---" for _ in headers)
    lines.append(f"| {header_line} |")
    lines.append(f"| {separator_line} |")

    for row in rows:
        row_values = [
            (value.replace("|", "\\|") if value else "")
            for value in row[: len(headers)]
        ]
        lines.append(f"| {' | '.join(row_values)} |")

    lines.append("")
    return "\n".join(lines)


def ensure_slug(source: SourcePage) -> str:
    """Return a filesystem-friendly slug for the source."""
    if source.slug:
        return source.slug

    parsed = urlparse(source.url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if "data" in path_parts:
        path_parts = path_parts[path_parts.index("data") + 1 :]
    if path_parts and path_parts[-1].endswith(".html"):
        path_parts[-1] = path_parts[-1][:-5]
    return "_".join(path_parts)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for source in SOURCE_PAGES:
        response = requests.get(source.url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else source.url

        tables = soup.find_all("table")
        if not tables:
            raise RuntimeError(f"No tables found at {source.url}")

        # Current pages only expose a single table, but handle multiple just in case.
        combined_headers: List[str] = []
        combined_notes: List[str] = []
        combined_rows: List[List[str]] = []

        for idx, table in enumerate(tables, start=1):
            headers, notes, rows = parse_table(table, source.url)
            if idx == 1:
                combined_headers = headers
            elif headers and headers != combined_headers:
                raise RuntimeError(
                    f"Table {idx} at {source.url} has different headers; "
                    "this script expects consistent structure."
                )
            combined_notes.extend(notes)
            combined_rows.extend(rows)

        markdown = build_markdown(
            title, source.url, combined_headers, combined_notes, combined_rows
        )

        filename = ensure_slug(source) + ".md"
        output_path = OUTPUT_DIR / filename
        output_path.write_text(markdown, encoding="utf-8")
        print(f"Wrote {output_path.relative_to(WORKSPACE_ROOT)}")


if __name__ == "__main__":
    main()
