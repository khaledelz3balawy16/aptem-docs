from datetime import datetime


APPRENTICESHIP_AGREEMENT = "apprenticeship agreement"


def _integer(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_version_datetime(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def best_agreement_version_for_start(
    documents,
    program_id,
    start_date,
    reference_document_id=None,
):
    documents = documents if isinstance(documents, list) else []
    resolved_program_id = _integer(program_id)
    reference_document_id = _integer(reference_document_id)

    if reference_document_id is not None:
        reference_document = next(
            (
                document
                for document in documents
                if isinstance(document, dict)
                and _integer(document.get("Id")) == reference_document_id
                and str(document.get("ComplianceName") or "").strip().lower()
                == APPRENTICESHIP_AGREEMENT
            ),
            None,
        )
        if reference_document is not None:
            resolved_program_id = (
                _integer(reference_document.get("ProgramId")) or resolved_program_id
            )

    if resolved_program_id is None:
        return None

    candidates = []
    for document in documents:
        if not isinstance(document, dict):
            continue
        if str(document.get("ComplianceName") or "").strip().lower() != APPRENTICESHIP_AGREEMENT:
            continue
        document_program_id = _integer(document.get("ProgramId"))
        document_id = _integer(document.get("Id"))
        if document_program_id is None or document_id is None:
            continue
        if document_program_id != resolved_program_id:
            continue
        created_at = parse_version_datetime(document.get("CreateDateTime"))
        if created_at is None:
            continue
        candidates.append((created_at, document_id, document))

    if not candidates:
        return None

    on_or_before_start = [
        candidate for candidate in candidates if candidate[0].date() <= start_date
    ]
    if on_or_before_start:
        return max(
            on_or_before_start,
            key=lambda candidate: (candidate[0], candidate[1]),
        )[2]

    return min(candidates, key=lambda candidate: (candidate[0], candidate[1]))[2]


def agreement_version_url(base_url, document_id, learner_id):
    return (
        f"{str(base_url).rstrip('/')}/DownloadFile/Compliance/"
        f"{int(document_id)}?userId={int(learner_id)}"
    )
