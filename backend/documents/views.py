import json
from datetime import date
from urllib.parse import urlparse

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from .services import (
    create_document,
    database_is_ready,
    delete_document,
    list_documents,
    update_document,
)
from .comparison_services import (
    list_start_date_comparisons,
    update_apprenticeship_agreement_date,
)
from .hours_comparison_services import list_planned_hours_comparisons
from .funding_comparison_services import list_funding_comparisons
from .prior_learning_services import list_prior_learning
from .endpoint_assessment_services import list_endpoint_assessments
from .monthly_hours_services import list_monthly_hours
from .skills_radar_services import list_skills_radar_audit
from .written_agreement_refetch_services import (
    get_refetch_job,
    start_written_agreement_refetch,
)


def error_response(message, status=400):
    return JsonResponse({"message": message}, status=status)


def parse_json(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def valid_url(value):
    try:
        parsed = urlparse(str(value))
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except (TypeError, ValueError):
        return False


def validate_document(data, creating=False):
    if not isinstance(data, dict):
        return "Invalid request data."

    required = ["file", "documentName", "category"]
    if creating:
        required.extend(["learnerId", "fullName", "programName"])

    for field in required:
        if str(data.get(field, "")).strip() == "":
            return "Complete all required fields and try again."

    if not valid_url(data.get("file")):
        return "The file URL must begin with http:// or https://."

    if len(str(data["file"])) > 2000:
        return "The file URL is too long."

    updated_to = data.get("updatedTo")
    if updated_to not in (None, ""):
        try:
            date.fromisoformat(str(updated_to))
        except ValueError:
            return "Updated to must be a valid date."

    if creating:
        try:
            learner_id = int(data["learnerId"])
            if learner_id <= 0:
                raise ValueError
            data["learnerId"] = learner_id
        except (TypeError, ValueError):
            return "Invalid learner ID."

    return None


@require_GET
def health(_request):
    try:
        ready = database_is_ready()
        return JsonResponse({"status": "ok" if ready else "error"})
    except Exception:
        return error_response("Database unavailable", status=503)


@require_GET
def start_date_comparisons(request):
    try:
        result = list_start_date_comparisons(
            page=request.GET.get("page", "1"),
            search=request.GET.get("search", ""),
            comparison_filter=request.GET.get("filter", "all"),
            program_status=request.GET.get("programStatus", "all"),
        )
        return JsonResponse(result)
    except (TypeError, ValueError):
        return error_response("Invalid page number.")
    except Exception:
        return error_response("Unable to load date comparison data.", status=500)


@require_GET
def planned_hours_comparisons(request):
    try:
        result = list_planned_hours_comparisons(
            page=request.GET.get("page", "1"),
            search=request.GET.get("search", ""),
            comparison_filter=request.GET.get("filter", "all"),
            program_status=request.GET.get("programStatus", "all"),
        )
        return JsonResponse(result)
    except (TypeError, ValueError):
        return error_response("Invalid comparison request.")
    except Exception:
        return error_response("Unable to load hours comparison data.", status=500)


@require_GET
def funding_comparisons(request):
    try:
        result = list_funding_comparisons(
            page=request.GET.get("page", "1"),
            search=request.GET.get("search", ""),
            comparison_filter=request.GET.get("filter", "all"),
            program_status=request.GET.get("programStatus", "all"),
        )
        return JsonResponse(result)
    except (TypeError, ValueError):
        return error_response("Invalid comparison request.")
    except Exception:
        return error_response("Unable to load funding comparison data.", status=500)


@require_GET
def prior_learning(request):
    try:
        result = list_prior_learning(
            search=request.GET.get("search", ""),
            comparison_filter=request.GET.get("filter", "all"),
            program_status=request.GET.get("programStatus", "all"),
        )
        return JsonResponse(result)
    except ValueError:
        return error_response("Invalid prior-learning request.")
    except Exception:
        return error_response("Unable to load prior-learning data.", status=500)


@require_GET
def endpoint_assessments(request):
    try:
        result = list_endpoint_assessments(
            page=request.GET.get("page", "1"),
            search=request.GET.get("search", ""),
            timeline_filter=request.GET.get("filter", "all"),
            program_status=request.GET.get("programStatus", "all"),
        )
        return JsonResponse(result)
    except (TypeError, ValueError):
        return error_response("Invalid endpoint-assessment request.")
    except Exception:
        return error_response("Unable to load endpoint-assessment data.", status=500)


@require_GET
def monthly_hours(request):
    try:
        result = list_monthly_hours(
            page=request.GET.get("page", "1"),
            search=request.GET.get("search", ""),
            year=request.GET.get("year", ""),
            hours_filter=request.GET.get("filter", "all"),
            program_status=request.GET.get("programStatus", "all"),
        )
        return JsonResponse(result)
    except (TypeError, ValueError):
        return error_response("Invalid monthly-hours request.")
    except Exception:
        return error_response("Unable to load monthly-hours data.", status=500)


@require_GET
def skills_radar_audit(request):
    try:
        result = list_skills_radar_audit(
            page=request.GET.get("page", "1"),
            search=request.GET.get("search", ""),
            radar_filter=request.GET.get("filter", "all"),
            program_status=request.GET.get("programStatus", "all"),
        )
        return JsonResponse(result)
    except (TypeError, ValueError):
        return error_response("Invalid Skills Radar request.")
    except Exception:
        return error_response("Unable to load Skills Radar data.", status=500)


@csrf_exempt
def written_agreement_refetch(request):
    if request.method != "POST":
        return error_response("Method not allowed", status=405)
    data = parse_json(request)
    if not isinstance(data, dict):
        return error_response("Invalid request data.")
    try:
        job = start_written_agreement_refetch(data.get("scope"))
        return JsonResponse(job, status=202)
    except ValueError as exc:
        return error_response(str(exc))
    except Exception:
        return error_response("Unable to start Written Agreement refetch.", status=500)


@require_GET
def written_agreement_refetch_status(_request, job_id):
    try:
        job = get_refetch_job(job_id)
        if job is None:
            return error_response("Refetch job not found.", status=404)
        return JsonResponse(job)
    except Exception:
        return error_response("Unable to load refetch progress.", status=500)


@csrf_exempt
def apprenticeship_agreement_comparison_date(request, document_id):
    if request.method != "PATCH":
        return error_response("Method not allowed", status=405)

    data = parse_json(request)
    if not isinstance(data, dict):
        return error_response("Invalid request data.")

    agreement_date = data.get("apprenticeshipAgreementDate")
    try:
        parsed_date = date.fromisoformat(str(agreement_date))
    except (TypeError, ValueError):
        return error_response("Apprenticeship Agreement date must be a valid date.")

    try:
        updated_id = update_apprenticeship_agreement_date(document_id, parsed_date)
        if not updated_id:
            return error_response("Apprenticeship Agreement not found.", status=404)
        return JsonResponse({"message": "Apprenticeship Agreement date updated."})
    except Exception:
        return error_response("Unable to update Apprenticeship Agreement date.", status=500)


@csrf_exempt
def documents_collection(request):
    if request.method == "GET":
        try:
            result = list_documents(
                page=request.GET.get("page", "1"),
                search=request.GET.get("search", ""),
                learner_scope=request.GET.get("learnerScope", "ilr"),
                program_status=request.GET.get("programStatus", "all"),
            )
            return JsonResponse(result)
        except (TypeError, ValueError):
            return error_response("Invalid page number.")
        except Exception:
            return error_response(
                "Unable to load documents from the database.", status=500
            )

    if request.method == "POST":
        data = parse_json(request)
        validation_error = validate_document(data, creating=True)
        if validation_error:
            return error_response(validation_error)
        try:
            document_id = create_document(data)
            return JsonResponse(
                {
                    "id": document_id,
                    "message": "Document added successfully.",
                },
                status=201,
            )
        except Exception:
            return error_response("Unable to add the document.", status=500)

    return error_response("Method not allowed", status=405)


@csrf_exempt
def document_detail(request, document_id):
    if request.method == "PATCH":
        data = parse_json(request)
        validation_error = validate_document(data)
        if validation_error:
            return error_response(validation_error)
        try:
            updated_id = update_document(document_id, data)
            if not updated_id:
                return error_response("Document not found.", status=404)
            return JsonResponse({"message": "Changes saved successfully."})
        except Exception:
            return error_response("Unable to save changes.", status=500)

    if request.method == "DELETE":
        try:
            deleted_id = delete_document(document_id)
            if not deleted_id:
                return error_response("Document not found.", status=404)
            return JsonResponse({"message": "Document deleted."})
        except Exception:
            return error_response("Unable to delete the document.", status=500)

    return error_response("Method not allowed", status=405)
