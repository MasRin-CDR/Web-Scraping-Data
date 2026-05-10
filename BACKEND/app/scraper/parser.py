"""
scraper/parser.py — HTML Parser for Mahkamah Agung Direktori
Uses BeautifulSoup to extract structured data from page HTML.
Multiple parsing strategies handle layout variations.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from app.utils.helpers import (
    clean_text,
    extract_case_number,
    extract_year,
    is_pdf_url,
    normalize_url,
    parse_indonesian_date,
)
from app.utils.logger import log

BASE_URL = "https://putusan3.mahkamahagung.go.id"


class PageParser:
    """
    Extracts putusan records from raw HTML using BeautifulSoup.
    Implements three strategies (table / card / anchor) with fallback.
    """

    def parse_search_results(
        self, html: str, page_num: int = 1
    ) -> List[Dict[str, Any]]:
        """Parse a search/directory listing page. Returns list of raw dicts."""
        soup = BeautifulSoup(html, "html.parser")
        records: List[Dict[str, Any]] = []

        # Strategy 1: Table rows
        records = self._parse_table(soup, page_num)
        if records:
            log.debug("Strategy 'table' found {} records on page {}", len(records), page_num)
            return records

        # Strategy 2: Card-based layout
        records = self._parse_cards(soup, page_num)
        if records:
            log.debug("Strategy 'cards' found {} records on page {}", len(records), page_num)
            return records

        # Strategy 3: Generic anchors
        records = self._parse_anchors(soup, page_num)
        log.debug("Strategy 'anchors' found {} records on page {}", len(records), page_num)
        return records

    # ─── Strategy 1: Table ────────────────────────────────────────────────────

    def _parse_table(self, soup: BeautifulSoup, page_num: int) -> List[Dict]:
        results = []
        tables = soup.select("table.table tbody tr, #table-putusan tbody tr, table tbody tr")
        for row in tables:
            cells = row.find_all("td")
            if not cells:
                continue

            link = row.find("a", href=True)
            pdf_link = row.find("a", href=re.compile(r"\.pdf|pdf", re.I))

            judul = clean_text(link.get_text()) if link else clean_text(cells[0].get_text())
            if not judul or len(judul) < 5:
                continue

            url_detail = normalize_url(BASE_URL, link["href"]) if link else ""
            url_pdf = normalize_url(BASE_URL, pdf_link["href"]) if pdf_link else ""

            # Extract metadata from cells
            cell_texts = [clean_text(c.get_text()) for c in cells]
            nomor = extract_case_number(judul) or extract_case_number(url_detail)
            tahun = extract_year(judul) or (cell_texts[4] if len(cell_texts) > 4 else None)

            # Parse date from cells (typically 2nd or 3rd cell)
            tanggal_raw = cell_texts[2] if len(cell_texts) > 2 else ""
            tanggal = parse_indonesian_date(tanggal_raw)

            record = {
                "nomor_perkara": nomor or judul[:60],
                "tahun": tahun,
                "lokasi": cell_texts[1] if len(cell_texts) > 1 else "",
                "jenis_peradilan": self._guess_jenis(cell_texts),
                "judul": judul,
                "tanggal_putusan": tanggal,
                "url_detail": url_detail,
                "url_pdf": url_pdf,
                "klasifikasi": cell_texts[3] if len(cell_texts) > 3 else "",
                "source_page": page_num,
            }
            results.append(record)
        return results

    # ─── Strategy 2: Cards ────────────────────────────────────────────────────

    def _parse_cards(self, soup: BeautifulSoup, page_num: int) -> List[Dict]:
        results = []
        selectors = [
            ".card-putusan", ".list-item", ".search-result-item",
            "[class*='putusan']", "[class*='direktori']",
            ".skel-result", ".row-result",
        ]
        cards = []
        for sel in selectors:
            cards = soup.select(sel)
            if cards:
                break
        if not cards:
            return []

        for card in cards:
            link = card.find("a", href=True)
            pdf_link = card.find("a", href=re.compile(r"\.pdf", re.I))
            heading = card.find(["h3", "h4", "h5", "strong"])
            date_el = card.find(class_=re.compile(r"date|tanggal", re.I))

            judul = clean_text(link.get_text()) if link else ""
            if not judul and heading:
                judul = clean_text(heading.get_text())
            if not judul or len(judul) < 5:
                continue

            full_text = clean_text(card.get_text())
            nomor = extract_case_number(judul) or extract_case_number(full_text)

            record = {
                "nomor_perkara": nomor or judul[:60],
                "tahun": extract_year(judul),
                "lokasi": self._extract_field(full_text, r"lembaga\s*peradilan[:\s]+([^\n|]+)"),
                "jenis_peradilan": self._extract_field(full_text, r"jenis\s*lembaga[:\s]+([^\n|]+)"),
                "judul": judul,
                "tanggal_putusan": parse_indonesian_date(
                    clean_text(date_el.get_text()) if date_el else ""
                ),
                "url_detail": normalize_url(BASE_URL, link["href"]) if link else "",
                "url_pdf": normalize_url(BASE_URL, pdf_link["href"]) if pdf_link else "",
                "source_page": page_num,
            }
            results.append(record)
        return results

    # ─── Strategy 3: Anchors ──────────────────────────────────────────────────

    def _parse_anchors(self, soup: BeautifulSoup, page_num: int) -> List[Dict]:
        results = []
        anchors = soup.find_all("a", href=re.compile(r"putusan|detail", re.I))
        seen_urls = set()

        for a in anchors:
            href = normalize_url(BASE_URL, a.get("href", ""))
            if href in seen_urls or not href:
                continue
            seen_urls.add(href)

            judul = clean_text(a.get_text())
            if not judul or len(judul) < 10:
                continue

            parent_text = ""
            parent = a.find_parent(["li", "tr", "div", "article"])
            if parent:
                parent_text = clean_text(parent.get_text())

            record = {
                "nomor_perkara": extract_case_number(judul) or judul[:60],
                "tahun": extract_year(judul),
                "lokasi": "",
                "jenis_peradilan": "",
                "judul": judul,
                "tanggal_putusan": None,
                "url_detail": href,
                "url_pdf": href if is_pdf_url(href) else "",
                "source_page": page_num,
            }
            results.append(record)
        return results

    # ─── Detail Page Parsing ──────────────────────────────────────────────────

    def parse_detail_page(self, html: str) -> Dict[str, Any]:
        """Extract full metadata from a putusan detail page."""
        soup = BeautifulSoup(html, "html.parser")
        detail: Dict[str, Any] = {"metadata": {}}

        # Find PDF link
        pdf_el = soup.find("a", href=re.compile(r"\.pdf|download|unduh", re.I))
        if pdf_el:
            detail["url_pdf"] = normalize_url(BASE_URL, pdf_el.get("href", ""))

        # Extract metadata from table rows or dl/dt/dd
        meta = {}
        # Try table-based metadata
        for row in soup.select("table tr, .table-detail tr, .metadata tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                key = clean_text(cells[0].get_text()).lower().replace(" ", "_")
                val = clean_text(cells[1].get_text())
                if key and val:
                    meta[key] = val

        # Try dl/dt/dd pattern
        for dt in soup.find_all("dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                key = clean_text(dt.get_text()).lower().replace(" ", "_")
                val = clean_text(dd.get_text())
                if key and val:
                    meta[key] = val

        # Map common field names
        field_map = {
            "nomor": "nomor_perkara",
            "nomor_perkara": "nomor_perkara",
            "nomor_putusan": "nomor_perkara",
            "tanggal_putusan": "tanggal_putusan",
            "tanggal_register": "tanggal_register",
            "klasifikasi": "klasifikasi",
            "sub_klasifikasi": "sub_klasifikasi",
            "lembaga_peradilan": "lokasi",
            "jenis_lembaga_peradilan": "jenis_peradilan",
            "tingkat_proses": "tingkat_proses",
            "hakim_ketua": "hakim",
            "hakim": "hakim",
            "majelis_hakim": "hakim",
            "panitera": "panitera",
            "panitera_pengganti": "panitera",
            "amar": "amar_putusan",
            "amar_putusan": "amar_putusan",
            "para_pihak": "para_pihak",
            "catatan_amar": "catatan",
        }

        for raw_key, value in meta.items():
            for pattern, mapped in field_map.items():
                if pattern in raw_key:
                    detail[mapped] = value
                    break
            else:
                detail["metadata"][raw_key] = value

        # Parse dates
        if detail.get("tanggal_putusan"):
            detail["tanggal_putusan"] = parse_indonesian_date(detail["tanggal_putusan"]) or detail["tanggal_putusan"]
        if detail.get("tanggal_register"):
            detail["tanggal_register"] = parse_indonesian_date(detail["tanggal_register"]) or detail["tanggal_register"]

        return detail

    # ─── Pagination ───────────────────────────────────────────────────────────

    def parse_next_page_url(self, html: str, current_page: int) -> Optional[str]:
        """Find the URL for the next pagination page."""
        soup = BeautifulSoup(html, "html.parser")

        # Try "next" button
        next_selectors = [
            'a[aria-label="Next"]', 'a.next', '[class*="next"] a',
            '.pagination li:last-child a', 'a[rel="next"]',
        ]
        for sel in next_selectors:
            el = soup.select_one(sel)
            if el and el.get("href") and "disabled" not in (el.get("class") or []):
                return normalize_url(BASE_URL, el["href"])

        # Try numbered page link
        page_links = soup.select(".pagination a, nav.pagination a")
        for link in page_links:
            try:
                num = int(clean_text(link.get_text()))
                if num == current_page + 1:
                    return normalize_url(BASE_URL, link["href"])
            except ValueError:
                continue

        return None

    def parse_total_results(self, html: str) -> Optional[int]:
        """Try to extract total result count from the page."""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()

        # Pattern: "X hasil" or "total X"
        patterns = [
            r"(\d[\d.,]*)\s*(?:hasil|putusan|data|records)",
            r"(?:total|jumlah|ditemukan)\s*:?\s*(\d[\d.,]*)",
            r"dari\s+(\d[\d.,]*)\s+(?:hasil|data)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.I)
            if m:
                return int(m.group(1).replace(".", "").replace(",", ""))
        return None

    # ─── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_field(text: str, pattern: str) -> str:
        m = re.search(pattern, text, re.I | re.DOTALL)
        return clean_text(m.group(1)) if m else ""

    @staticmethod
    def _guess_jenis(cell_texts: List[str]) -> str:
        """Guess jenis peradilan from cell content."""
        full = " ".join(cell_texts).lower()
        if "agama" in full:
            return "Peradilan Agama"
        if "tun" in full or "tata usaha" in full:
            return "Peradilan Tata Usaha Negara"
        if "militer" in full or "dilmil" in full:
            return "Peradilan Militer"
        if "mahkamah agung" in full:
            return "Mahkamah Agung"
        return "Peradilan Umum"


# ─── Singleton ────────────────────────────────────────────────────────────────
parser = PageParser()
