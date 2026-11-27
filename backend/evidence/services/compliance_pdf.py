"""Download Aptem compliance PDFs and extract planned OTJ hours."""

import re
from decimal import Decimal, InvalidOperation
from io import BytesIO
from multiprocessing import get_context

from pypdf import PdfReader


PLANNED_HOURS_PATTERNS = (
    re.compile(
        r"\bILR\s+planned\s+hours\s*:\s*"
        r"(?P<hours>\d{1,5}(?:\.\d+)?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"agreed\s+planned\s+hours.{0,180}?\bare\s+"
        r"(?P<hours>\d{1,5}(?:\.\d+)?)\s+hours",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"planned\s+amount\s+of\s+off[\s\-–—]*the[\s\-–—]*job\s+training"
        r"\s*\(hours\)\s*\(see\s+note\s+\d+\)\s*:?\s*"
        r"(?P<hours>\d{1,5}(?:\.\d+)?)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"planned\s+amount\s+of\s+off[\s\-–—]*the[\s\-–—]*job\s+training"
        r"\s*\(hours\)\s*:?\s*(?P<hours>\d{1,5}(?:\.\d+)?)\b",
        re.IGNORECASE | re.DOTALL,
    ),
)

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 30


def normalize_extracted_text(text):
    """Normalize ordinary PDF text and legacy PDFs with spaced-out glyphs."""
    normalized_lines = []
    for line in text.splitlines():
        groups = re.split(r" {2,}", line.strip())
        normalized_groups = []
        for group in groups:
            tokens = group.split()
            single_character_ratio = (
                sum(len(token) == 1 for token in tokens) / len(tokens)
                if tokens
                else 0
            )
            if len(tokens) >= 2 and single_character_ratio >= 0.65:
                normalized_groups.append("".join(tokens))
            else:
                normalized_groups.append(group)
        normalized_lines.append(" ".join(normalized_groups))
    return "\n".join(normalized_lines)


def extract_planned_off_the_job_hours(pdf_bytes):
    """Return the planned OTJ hours from a text-based compliance PDF."""
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise ValueError("PDF exceeds the 10 MB extraction limit.")
    reader = PdfReader(BytesIO(pdf_bytes), strict=False)
    raw_text = "\n".join(
        page.extract_text() or "" for page in reader.pages[:MAX_PDF_PAGES]
    )
    text = re.sub(r"[\u00a0\t ]+", " ", raw_text)
    spaced_text = normalize_extracted_text(raw_text)
    searchable_text = f"{text}\n{spaced_text}"

    for pattern in PLANNED_HOURS_PATTERNS:
        match = pattern.search(searchable_text)
        if not match:
            continue
        try:
            return Decimal(match.group("hours"))
        except InvalidOperation:
            continue

    lines = [line.strip() for line in spaced_text.splitlines() if line.strip()]
    label_patterns = (
        re.compile(r"^ILR\s+Planned\s+Hours\s*:", re.IGNORECASE),
        re.compile(
            r"^Planned\s+amount\s+of\s+off[\s-]*the[\s-]*job",
            re.IGNORECASE,
        ),
    )
    for index, line in enumerate(lines):
        if not any(pattern.search(line) for pattern in label_patterns):
            continue
        for candidate in lines[index + 1 : index + 13]:
            number_match = re.fullmatch(r"\d{1,5}(?:\.\d+)?", candidate)
            if number_match:
                return Decimal(number_match.group(0))
    return None


def _extract_worker(pdf_bytes, result_queue):
    try:
        value = extract_planned_off_the_job_hours(pdf_bytes)
        result_queue.put(("ok", str(value) if value is not None else None))
    except Exception as exc:  # noqa: BLE001 - relay parser failures to the parent.
        result_queue.put(("error", str(exc)))


def extract_planned_hours_with_timeout(pdf_bytes, timeout=15):
    """Run PDF parsing out-of-process so malformed PDFs cannot block a backfill."""
    context = get_context("spawn")
    result_queue = context.Queue(maxsize=1)
    process = context.Process(target=_extract_worker, args=(pdf_bytes, result_queue))
    process.start()
    process.join(timeout)
    if process.is_alive():
        process.terminate()
        process.join()
        raise TimeoutError(f"PDF text extraction exceeded {timeout} seconds.")
    if result_queue.empty():
        raise ValueError("PDF parser exited without returning a result.")
    status, value = result_queue.get()
    if status == "error":
        raise ValueError(value)
    return Decimal(value) if value is not None else None


def download_compliance_pdf(client, url):
    """Download a PDF using the authenticated Aptem session, retrying once."""
    response = client.session.get(url, timeout=90)
    if response.status_code == 401:
        client.login()
        response = client.session.get(url, timeout=90)
    response.raise_for_status()

    content_type = (response.headers.get("content-type") or "").lower()
    if "pdf" not in content_type and not response.content.startswith(b"%PDF"):
        raise ValueError("Aptem returned a non-PDF response.")
    return response.content
