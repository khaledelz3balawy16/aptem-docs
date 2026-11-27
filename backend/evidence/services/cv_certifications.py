"""Extract education and certification entries from CV documents."""

import html
import re
import zipfile
from io import BytesIO
from xml.etree import ElementTree

from pypdf import PdfReader


SECTION_HEADINGS = {
    "education": {
        "academic background",
        "academic qualifications",
        "education",
        "education and qualifications",
        "education history",
        "education and training",
        "education qualifications",
        "educational background",
        "qualifications",
    },
    "certification": {
        "certificates",
        "certification",
        "certifications",
        "courses",
        "courses and certifications",
        "courses training and certifications",
        "courses trainings certifications",
        "cpd and training",
        "professional development",
        "professional certifications",
        "professional qualifications",
        "professional training and development",
        "training and certifications",
    },
}

STOP_HEADINGS = {
    "about me",
    "achievements",
    "additional information",
    "affiliations",
    "attributes",
    "career history",
    "contact",
    "contact details",
    "core competencies",
    "employment",
    "employment history",
    "experience",
    "hobbies",
    "interests",
    "key skills",
    "languages",
    "personal details",
    "personal profile",
    "profile",
    "professional experience",
    "references",
    "skills",
    "skills and attributes",
    "skills attributes",
    "skill highlights",
    "summary",
    "technical skills",
    "work experience",
    "work history",
}

QUALIFICATION_RE = re.compile(
    r"(?i)\b(?:award|bachelor|ba\b|bsc\b|certificate|certification|course|degree|"
    r"diploma|doctorate|foundation|gcse|hnd\b|hnc\b|iosh|ilm\b|masters?|mba\b|"
    r"msc\b|nebosh|nvq|phd\b|prince\s*2|qualification|training|university|college|"
    r"city\s*(?:and|&)\s*guilds|cipd|apm\b|pmp\b|level\s*\d)\b"
)
ORGANISATION_RE = re.compile(
    r"(?i)\b(?:academy|association|board|college|council|guilds|institute|institution|"
    r"school|services|training|university)\b"
)
YEAR_RE = re.compile(
    r"\b(?:19|20)\d{2}(?:\s*(?:-|–|—|to|&)\s*(?:19|20)\d{2})?\b"
)
MONTH_YEAR_RE = re.compile(
    r"(?i)\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\s+(?:19|20)\d{2}\b"
)
CREDENTIAL_RE = re.compile(
    r"(?i)\b(?:credential|certificate|licen[cs]e)\s*(?:id|no\.?|number)\s*[:#-]?\s*"
    r"([A-Z0-9][A-Z0-9./-]{3,})"
)
EXPIRY_RE = re.compile(
    r"(?i)\b(?:expiry|expires?|valid until)\s*[:.-]?\s*"
    r"((?:(?:19|20)\d{2})|(?:\d{1,2}/\d{1,2}/(?:19|20)\d{2}))"
)


class UnsupportedCvFormat(ValueError):
    pass


def _normalized_heading(value):
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _compact_heading(value):
    return _normalized_heading(value).replace(" ", "")


def _docx_text(document_bytes):
    with zipfile.ZipFile(BytesIO(document_bytes)) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    lines = []
    for paragraph in root.iter(f"{namespace}p"):
        text = "".join(
            node.text or "" for node in paragraph.iter(f"{namespace}t")
        ).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def extract_cv_text(document_bytes, content_type="", file_name=""):
    normalized_type = str(content_type or "").lower()
    normalized_name = str(file_name or "").lower()
    if document_bytes.startswith(b"%PDF") or "pdf" in normalized_type:
        reader = PdfReader(BytesIO(document_bytes), strict=False)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if (
        document_bytes.startswith(b"PK")
        or "wordprocessingml" in normalized_type
        or normalized_name.endswith(".docx")
    ):
        return _docx_text(document_bytes)
    raise UnsupportedCvFormat("Only text-based PDF and DOCX CV files are supported")


def _section_kind(line):
    normalized = _normalized_heading(line)
    compact = normalized.replace(" ", "")
    if len(compact) > 55:
        return None
    if normalized == "courses" and line.rstrip().endswith("."):
        return None
    if normalized.endswith(" qualifications"):
        return "education" if normalized.startswith(("academic ", "education ")) else "certification"
    for kind, headings in SECTION_HEADINGS.items():
        if normalized in headings or compact in {
            heading.replace(" ", "") for heading in headings
        }:
            return kind
    return None


def _is_stop_heading(line):
    normalized = _normalized_heading(line)
    compact = normalized.replace(" ", "")
    if len(compact) > 70:
        return False
    return (
        normalized in STOP_HEADINGS
        or compact in {heading.replace(" ", "") for heading in STOP_HEADINGS}
        or normalized.endswith((" work experience", " employment history"))
    )


def _clean_line(line):
    value = html.unescape(str(line or ""))
    value = re.sub(r"^[\s•●▪◦*·\-–—]+", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _has_qualification(line):
    if QUALIFICATION_RE.search(line):
        return True
    compact = _compact_heading(line)
    if re.match(r"^(?:ba|bed|beng|ma|meng)(?:hons)?[a-z]", compact):
        return True
    return any(
        marker in compact
        for marker in (
            "alevel",
            "bachelor",
            "bsc",
            "btec",
            "certificate",
            "certified",
            "degree",
            "diploma",
            "gcse",
            "hnd",
            "level",
            "master",
            "nvq",
            "qualification",
            "training",
        )
    )


def _looks_like_issuer(line):
    return (
        len(line) <= 120
        and not YEAR_RE.search(line)
        and " by " not in line.lower()
        and bool(ORGANISATION_RE.search(line))
        and not _has_qualification(
            line.replace("University", "").replace("College", "")
        )
    )


def _parse_entry(line, category, issuer_override=None):
    evidence = _clean_line(line).rstrip(".;")
    if len(evidence) < 3 or len(evidence) > 500:
        return None

    expiry_match = EXPIRY_RE.search(evidence)
    credential_match = CREDENTIAL_RE.search(evidence)
    dates = MONTH_YEAR_RE.findall(evidence) or YEAR_RE.findall(evidence)
    issued_date = dates[-1] if dates else None

    without_dates = MONTH_YEAR_RE.sub("", evidence)
    without_dates = YEAR_RE.sub("", without_dates)
    without_dates = re.sub(r"\(\s*\)", "", without_dates)
    without_dates = re.sub(r"\s*[,;\-–—]\s*$", "", without_dates).strip()
    parts = [
        part.strip(" ,.;-–—")
        for part in re.split(
            r"\s*(?:–|—|\|)\s*|\s+-\s*|(?<=[a-z)])-(?=[A-Z])",
            without_dates,
        )
        if part.strip(" ,.;-–—")
    ]
    name = parts[0] if parts else without_dates
    issuer = issuer_override
    if issuer is None and len(parts) > 1 and len(parts[1]) <= 2:
        name = " - ".join(parts)
    elif issuer is None and len(parts) > 1:
        issuer = " - ".join(parts[1:])
    if not name:
        return None

    return {
        "name": name,
        "issuer": issuer or None,
        "expiry_date": expiry_match.group(1) if expiry_match else None,
        "issued_date": issued_date,
        "credential_id": credential_match.group(1) if credential_match else None,
        "evidence_text": evidence,
        "category": category,
    }


def extract_certifications_and_education(text):
    sections = []
    current_kind = None
    current_lines = []

    def finish_section():
        nonlocal current_kind, current_lines
        if current_kind and current_lines:
            sections.append((current_kind, current_lines))
        current_kind = None
        current_lines = []

    for raw_line in str(text or "").splitlines():
        line = _clean_line(raw_line)
        if not line:
            continue
        kind = _section_kind(line)
        if kind:
            finish_section()
            current_kind = kind
            continue
        if current_kind and _is_stop_heading(line):
            finish_section()
            continue
        if current_kind:
            current_lines.append(line)
    finish_section()

    results = []
    seen = set()
    for category, lines in sections:
        lines = [
            part.strip()
            for line in lines
            for part in re.split(r"\s*;\s*", line)
            if part.strip()
        ]
        index = 0
        while index < len(lines):
            line = lines[index]
            if (
                category == "certification"
                and re.search(
                    r"(?i)\b(?:administrator|coordinator|director|executive|manager|officer)\b",
                    line,
                )
                and index + 1 < len(lines)
                and (
                    lines[index + 1].lstrip().startswith(("-", "–", "—"))
                    or re.search(r"(?i)\b(?:19|20)\d{2}\b", lines[index + 1])
                )
            ):
                break
            issuer_override = None
            if (
                _looks_like_issuer(line)
                and index + 1 < len(lines)
                and _has_qualification(lines[index + 1])
            ):
                issuer_override = line
                index += 1
                line = lines[index]
                evidence = line
            else:
                evidence = line

            if category == "education" and not _has_qualification(evidence):
                index += 1
                continue
            entry = _parse_entry(evidence, category, issuer_override)
            if entry:
                if issuer_override:
                    entry["evidence_text"] = f"{issuer_override}\n{line}"
                key = _normalized_heading(entry["name"])
                if key and key not in seen:
                    seen.add(key)
                    results.append(entry)
            index += 1
    return results
