from django.db import models


class AptemEvidence(models.Model):
    """One row per Aptem evidence item, tagged with the learner's programme.

    Created and managed by this app (table: aptem_evidence). The `raw` column
    keeps the full, unmodified evidence object from Aptem so no field is lost.
    """

    # From Aptem (LearningPlanEvidences)
    evidence_id = models.BigIntegerField(unique=True)          # ev.Id
    component_id = models.BigIntegerField(null=True, blank=True)
    evidence_name = models.TextField(blank=True, default="")
    evidence_kind = models.TextField(blank=True, default="")
    latest_status = models.TextField(blank=True, default="")
    created_date = models.DateTimeField(null=True, blank=True)

    # The "file" link (raw Aptem document URL)
    file = models.TextField(blank=True, default="")

    # Categorisation (from LMS.Aptem_users)
    learner_id = models.BigIntegerField(db_index=True)
    full_name = models.TextField(blank=True, default="")
    program_name = models.TextField(null=True, blank=True, db_index=True)

    # Everything Aptem returned, untouched
    raw = models.JSONField(default=dict)

    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False  # table is created/owned manually (see CREATE SQL)
        # Schema-qualified: Django quotes this to "fetching_evidence"."aptem_evidence"
        db_table = 'fetching_evidence"."aptem_evidence'
        verbose_name = "Aptem evidence"
        verbose_name_plural = "Aptem evidence"

    def __str__(self):
        return f"{self.evidence_id} - {self.evidence_name} ({self.program_name})"
