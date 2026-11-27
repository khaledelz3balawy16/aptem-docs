from django.urls import path

from . import views


urlpatterns = [
    path("health/", views.health, name="health"),
    path(
        "start-date-comparisons/",
        views.start_date_comparisons,
        name="start-date-comparisons",
    ),
    path(
        "planned-hours-comparisons/",
        views.planned_hours_comparisons,
        name="planned-hours-comparisons",
    ),
    path(
        "funding-comparisons/",
        views.funding_comparisons,
        name="funding-comparisons",
    ),
    path("prior-learning/", views.prior_learning, name="prior-learning"),
    path(
        "written-agreement-refetch/",
        views.written_agreement_refetch,
        name="written-agreement-refetch",
    ),
    path(
        "written-agreement-refetch/<uuid:job_id>/",
        views.written_agreement_refetch_status,
        name="written-agreement-refetch-status",
    ),
    path(
        "endpoint-assessments/",
        views.endpoint_assessments,
        name="endpoint-assessments",
    ),
    path("monthly-hours/", views.monthly_hours, name="monthly-hours"),
    path("skills-radar/", views.skills_radar_audit, name="skills-radar"),
    path(
        "start-date-comparisons/apprenticeship-agreement/<int:document_id>/",
        views.apprenticeship_agreement_comparison_date,
        name="apprenticeship-agreement-comparison-date",
    ),
    path("documents/", views.documents_collection, name="documents-collection"),
    path("documents/<int:document_id>/", views.document_detail, name="document-detail"),
]
