"""
scraper/parser.py - HTML Parser for Mahkamah Agung Direktori
Extracts structured PutusanRecord data from page content.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urljoin

from playwright.async_api import Page

from config import settings
from database.models import PutusanMetadata, PutusanRecord
from utils.helpers import clean_text, is_pdf_url, normalize_url, parse_indonesian_date
from utils.logger import log

BASE_URL = "https://putusan3.mahkamahagung.go.id"


class DirectoriParser:
    """
    Parses the Mahkamah Agung direktori listing pages.
    Extracts verdict cards and their metadata.
    """

    async def extract_records(self, page: Page, page_num: int) -> list[PutusanRecord]:
        """
        Extract all PutusanRecord items from the current page state.
        Tries multiple CSS selector strategies to handle layout changes.
        """
        records: list[PutusanRecord] = []

        # Try to extract cards from the listing
        cards_data = await page.evaluate(self._js_extract_cards())

        if not cards_data:
            log.warning("No cards found on page {} — trying fallback selectors", page_num)
            cards_data = await self._fallback_extract(page)

        for raw in cards_data:
            record = self._parse_card(raw, page_num)
            if record:
                records.append(record)

        log.info("Page {} | extracted {} records", page_num, len(records))
        return records

    def _js_extract_cards(self) -> str:
        """
        JavaScript to extract card data from the DOM.
        Returns a list of raw data objects.
        """
        return """
        () => {
            const results = [];

            // Strategy 1: Table rows (common layout)
            const tableRows = document.querySelectorAll('table.table tbody tr, #table-putusan tbody tr');
            if (tableRows.length > 0) {
                tableRows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length === 0) return;

                    const linkEl = row.querySelector('a[href]');
                    const pdfEl = row.querySelector('a[href*=".pdf"], a[href*="pdf"]');

                    const data = {
                        type: 'table_row',
                        judul: linkEl ? linkEl.innerText.trim() : cells[0]?.innerText.trim() || '',
                        url_detail: linkEl ? linkEl.href : '',
                        url_pdf: pdfEl ? pdfEl.href : '',
                        tanggal: cells[2]?.innerText.trim() || cells[1]?.innerText.trim() || '',
                        metadata_text: row.innerText,
                        cells: Array.from(cells).map(c => c.innerText.trim()),
                    };
                    if (data.judul) results.push(data);
                });
                return results;
            }

            // Strategy 2: Card-based layout
            const cards = document.querySelectorAll(
                '.card-putusan, .list-item, .search-result-item, ' +
                '[class*="putusan"], [class*="direktori"]'
            );
            if (cards.length > 0) {
                cards.forEach(card => {
                    const linkEl = card.querySelector('a[href]');
                    const pdfEl = card.querySelector('a[href*=".pdf"]');
                    const dateEl = card.querySelector('[class*="date"], [class*="tanggal"], time');

                    results.push({
                        type: 'card',
                        judul: linkEl ? linkEl.innerText.trim() : card.querySelector('h3,h4,h5')?.innerText.trim() || '',
                        url_detail: linkEl ? linkEl.href : '',
                        url_pdf: pdfEl ? pdfEl.href : '',
                        tanggal: dateEl ? dateEl.innerText.trim() : '',
                        metadata_text: card.innerText,
                    });
                });
                return results;
            }

            // Strategy 3: Any anchor with verdict-like content
            const anchors = document.querySelectorAll('a[href*="putusan"], a[href*="detail"]');
            anchors.forEach(a => {
                results.push({
                    type: 'anchor',
                    judul: a.innerText.trim(),
                    url_detail: a.href,
                    url_pdf: '',
                    tanggal: '',
                    metadata_text: a.closest('li,tr,div')?.innerText || '',
                });
            });

            return results;
        }
        """

    async def _fallback_extract(self, page: Page) -> list[dict]:
        """Fallback: dump all anchor tags with context."""
        return await page.evaluate("""
        () => {
            return Array.from(document.querySelectorAll('a')).map(a => ({
                type: 'fallback',
                judul: a.innerText.trim(),
                url_detail: a.href,
                url_pdf: a.href.includes('.pdf') ? a.href : '',
                tanggal: '',
                metadata_text: a.parentElement?.innerText || '',
            })).filter(d => d.judul.length > 10);
        }
        """)

    def _parse_card(self, raw: dict, page_num: int) -> Optional[PutusanRecord]:
        """Convert a raw card dict into a validated PutusanRecord."""
        judul = clean_text(raw.get("judul", ""))
        if not judul or len(judul) < 5:
            return None

        # Parse PDF URL
        url_pdf = raw.get("url_pdf", "") or ""
        url_detail = raw.get("url_detail", "") or ""

        # Normalize relative URLs
        if url_detail:
            url_detail = normalize_url(BASE_URL, url_detail)
        if url_pdf:
            url_pdf = normalize_url(BASE_URL, url_pdf)

        # Parse date
        tanggal_text = clean_text(raw.get("tanggal", ""))
        tanggal = parse_indonesian_date(tanggal_text) if tanggal_text else None

        # Parse metadata from full text
        meta_text = raw.get("metadata_text", "")
        cells = raw.get("cells", [])
        metadata = self._extract_metadata(meta_text, cells)

        # Extract nomor putusan from judul or URL
        from utils.helpers import extract_case_number
        nomor = extract_case_number(judul) or extract_case_number(url_detail or "")

        try:
            return PutusanRecord(
                judul=judul,
                nomor_putusan=nomor,
                tanggal_putusan=tanggal,
                url_detail=url_detail or None,
                url_pdf=url_pdf or None,
                metadata=metadata,
                source_page=page_num,
            )
        except Exception as exc:
            log.debug("Failed to create PutusanRecord: {} | raw={}", exc, str(raw)[:120])
            return None

    def _extract_metadata(self, text: str, cells: list[str]) -> PutusanMetadata:
        """
        Extract structured metadata from the full card text or table cells.
        Uses regex patterns matching common Mahkamah Agung data formats.
        """
        meta = PutusanMetadata()

        # Helper patterns
        def find(pattern: str, src: str) -> Optional[str]:
            m = re.search(pattern, src, re.IGNORECASE | re.DOTALL)
            return clean_text(m.group(1)) if m else None

        # From structured cells (table layout)
        if len(cells) >= 4:
            meta.lembaga_peradilan = cells[1] if len(cells) > 1 else None
            meta.klasifikasi = cells[3] if len(cells) > 3 else None
            meta.tahun = cells[4] if len(cells) > 4 else None

        # From text patterns
        meta.klasifikasi = meta.klasifikasi or find(
            r"klasifikasi[:\s]+([^\n\|]+)", text
        )
        meta.sub_klasifikasi = find(r"sub[\s-]*klasifikasi[:\s]+([^\n\|]+)", text)
        meta.jenis_lembaga_peradilan = find(
            r"jenis lembaga[:\s]+([^\n\|]+)", text
        )
        meta.lembaga_peradilan = meta.lembaga_peradilan or find(
            r"lembaga peradilan[:\s]+([^\n\|]+)", text
        )
        meta.tingkat_proses = find(r"tingkat proses[:\s]+([^\n\|]+)", text)
        meta.para_pihak = find(r"para pihak[:\s]+([^\n\|]+)", text)
        meta.amar_putusan = find(r"amar[:\s]+([^\n\|]+)", text)

        return meta

    # ─── Detail Page Parsing ──────────────────────────────────────────────────

    async def extract_detail(self, page: Page) -> dict:
        """
        Extract additional data from a verdict detail page.
        Returns a dict with pdf_url and enriched metadata.
        """
        result = {"url_pdf": None, "metadata": {}}

        # Find PDF link
        pdf_link = await page.query_selector(
            "a[href$='.pdf'], a[href*='download'], a[href*='pdf']"
        )
        if pdf_link:
            href = await pdf_link.get_attribute("href")
            if href:
                result["url_pdf"] = normalize_url(BASE_URL, href)

        # Extract all metadata table rows
        rows = await page.query_selector_all("table.table-detail tr, .metadata tr, dl dt")
        meta_dict = {}
        for row in rows:
            cells = await row.query_selector_all("td, dd")
            if len(cells) >= 2:
                key = clean_text(await cells[0].inner_text())
                val = clean_text(await cells[1].inner_text())
                if key and val:
                    meta_dict[key.lower().replace(" ", "_")] = val

        result["metadata"] = meta_dict
        return result

    # ─── Pagination ───────────────────────────────────────────────────────────

    async def get_total_pages(self, page: Page) -> Optional[int]:
        """
        Detect total page count from pagination elements.
        Returns None if unable to determine.
        """
        # Try common pagination patterns
        total = await page.evaluate("""
        () => {
            // Pattern 1: "Halaman X dari Y"
            const text = document.body.innerText;
            const m = text.match(/halaman\\s+(\\d+)\\s+dari\\s+(\\d+)/i);
            if (m) return parseInt(m[2]);

            // Pattern 2: Last page number in pagination links
            const pageLinks = document.querySelectorAll(
                '.pagination a, [aria-label="pagination"] a, nav a'
            );
            const nums = Array.from(pageLinks)
                .map(a => parseInt(a.innerText.trim()))
                .filter(n => !isNaN(n));
            if (nums.length) return Math.max(...nums);

            // Pattern 3: data attribute
            const pager = document.querySelector('[data-total-pages], [data-pages]');
            if (pager) return parseInt(pager.dataset.totalPages || pager.dataset.pages);

            return null;
        }
        """)
        return total

    async def get_next_page_url(self, page: Page, current_page: int) -> Optional[str]:
        """Return the URL of the next page, or None if at the end."""
        next_url = await page.evaluate("""
        (current) => {
            // Try "next" button
            const nextBtn = document.querySelector(
                'a[aria-label="Next"], a.next, [class*="next"] a, ' +
                '.pagination li:last-child a, a[rel="next"]'
            );
            if (nextBtn && !nextBtn.classList.contains('disabled')) {
                return nextBtn.href || null;
            }

            // Try page number link
            const pageLinks = document.querySelectorAll('.pagination a, nav.pagination a');
            for (const link of pageLinks) {
                const num = parseInt(link.innerText.trim());
                if (num === current + 1) return link.href;
            }

            return null;
        }
        """, current_page)
        return next_url
