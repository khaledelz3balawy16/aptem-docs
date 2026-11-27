"""Extract the full costs table from an Aptem Written Agreement PDF."""

import re
from decimal import Decimal
from io import BytesIO

from pypdf import PdfReader

from evidence.services.compliance_pdf import normalize_extracted_text


COST_KEYS = (
    ("total_price", ("total price of apprenticeship",)),
    ("funding_band_maximum", ("funding band maximum value", "funding band maximum")),
    ("balance_due", ("balance due",)),
    ("other_non_fundable_costs", ("any other costs not fundable",)),
    ("distance_online_blended", ("distance online or blended learning",)),
    ("english_maths", ("english maths training",)),
    ("training_delivery", ("training that",)),
    ("assessment_progress_reviews", ("assessment that",)),
    ("registration_exam_certification", ("registration examination and certification",)),
    ("materials", ("materials non capital items",)),
    ("administration_including_epa", ("administration costs directly linked",)),
    ("subcontractor_training", ("training delivered by the subcontractor",)),
    ("subcontractor_assessment", ("assessment undertaken by the subcontractor",)),
    ("subcontractor_support", ("support that",)),
    ("monitoring", ("monitoring that",)),
    ("end_point_assessment", ("end point assessment",)),
    ("apprenticeship_certification", ("apprenticeship certification",)),
    ("external_quality_assurance", ("external quality assurance",)),
)

COLUMN_ITEM_LABELS = (
    ("training_delivery", "Training delivered to the Apprentice Off the Job"),
    ("distance_online_blended", "Distance, online or blended learning"),
    ("english_maths", "English & maths training (L3+ only)"),
    ("assessment_progress_reviews", "Assessment including Progress Reviews"),
    ("registration_exam_certification", "Registration, examination and certification"),
    ("materials", "Materials used in the delivery of the apprenticeship"),
    ("administration_including_epa", "Administration costs including EPA"),
    ("subcontractor_training", "Training delivered by the Subcontractor"),
    ("subcontractor_assessment", "Assessment undertaken by the Subcontractor"),
    ("subcontractor_support", "Support provided to the Subcontractor"),
    ("monitoring", "Monitoring undertaken by the provider"),
    ("end_point_assessment", "End Point Assessment"),
    ("apprenticeship_certification", "Apprenticeship Certification"),
    ("external_quality_assurance", "External Quality Assurance"),
)

CURRENCY_TOKEN_RE = re.compile(r"[£Ł]\s*([\d,]*(?:\.\d{1,2})?)")


def _normalized_label(value):
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _cost_key(label):
    normalized = _normalized_label(label)
    for key, phrases in COST_KEYS:
        if any(phrase in normalized for phrase in phrases):
            return key
    return None


def _money_object(label, symbol, raw_amount):
    normalized_amount = raw_amount.replace(",", "").strip()
    value = Decimal(normalized_amount) if normalized_amount else None
    # Some Aptem PDFs map the pound glyph to the visually similar Polish Ł
    # when their embedded font is decoded. Store a consistent currency glyph.
    raw_value = f"£ {raw_amount}".strip()
    return {
        "value": int(value) if value is not None and value == value.to_integral() else (
            float(value) if value is not None else None
        ),
        "currency": "GBP",
        "raw_value": raw_value,
        "evidence_text": f"{label.strip()} {raw_value}".strip(),
    }


def _column_major_breakdown(section, breakdown):
    """Handle PDFs whose text layer emits all labels before the value column."""
    if "training_delivery" in breakdown or "Associated price" not in section:
        return breakdown

    before_prices, after_prices = section.split("Associated price", 1)
    item_values, separator, funding_tail = after_prices.partition("Funding Band")
    amounts = CURRENCY_TOKEN_RE.findall(item_values)
    if len(amounts) < len(COLUMN_ITEM_LABELS):
        return breakdown

    rebuilt = {
        key: _money_object(label, "£", amount)
        for (key, label), amount in zip(COLUMN_ITEM_LABELS, amounts, strict=False)
    }

    leading_amounts = CURRENCY_TOKEN_RE.findall(before_prices)
    numeric_leading = [amount for amount in leading_amounts if amount.strip()]
    total_amount = numeric_leading[-1] if numeric_leading else ""
    rebuilt["other_non_fundable_costs"] = _money_object(
        "Any other costs not fundable by Levy funds or DfE contribution",
        "£",
        "",
    )
    rebuilt["total_price"] = _money_object(
        "Total price of Apprenticeship", "£", total_amount
    )

    funding_amounts = CURRENCY_TOKEN_RE.findall(funding_tail) if separator else []
    numeric_funding = [amount for amount in funding_amounts if amount.strip()]
    rebuilt["funding_band_maximum"] = _money_object(
        "Funding Band Maximum value",
        "£",
        numeric_funding[0] if numeric_funding else "",
    )
    rebuilt["balance_due"] = _money_object("Balance due", "£", "")
    return rebuilt


def extract_written_agreement_funding(pdf_bytes):
    reader = PdfReader(BytesIO(pdf_bytes), strict=False)
    raw_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    text = normalize_extracted_text(raw_text)

    start_match = re.search(r"(?im)^Costs\s*:", text)
    if not start_match:
        return None
    section = text[start_match.end() :]
    end_match = re.search(r"(?im)^Please refer to Guidance document", section)
    if end_match:
        section = section[: end_match.start()]

    rows = []
    label_parts = []
    for line in (line.strip() for line in section.splitlines() if line.strip()):
        currency_match = re.search(r"([£Ł])\s*([\d,]*(?:\.\d{1,2})?)\s*$", line)
        if not currency_match:
            label_parts.append(line)
            continue
        label_parts.append(line[: currency_match.start()])
        label = " ".join(part for part in label_parts if part).strip()
        key = _cost_key(label)
        if key:
            rows.append(
                (
                    key,
                    label,
                    _money_object(label, currency_match.group(1), currency_match.group(2)),
                )
            )
        label_parts = []

    breakdown = {}
    for key, _label, money in rows:
        breakdown[key] = money
    breakdown = _column_major_breakdown(section, breakdown)
    if not breakdown:
        return None

    total = breakdown.get("total_price")
    endpoint = breakdown.get("end_point_assessment")
    actual_value = None
    if total and endpoint and total["value"] is not None and endpoint["value"] is not None:
        actual_value = total["value"] - endpoint["value"]

    return {
        "actual_funding": {
            "value": actual_value,
            "formula": "total_price_of_apprenticeship - end_point_assessment",
            "currency": "GBP",
            "calculation_status": "calculated" if actual_value is not None else "incomplete",
        },
        "end_point_assessment": breakdown.get("end_point_assessment"),
        "funding_band_maximum_value": breakdown.get("funding_band_maximum"),
        "total_price_of_apprenticeship": breakdown.get("total_price"),
        "balance_due": breakdown.get("balance_due"),
        "cost_breakdown": breakdown,
    }
