"""Aptem client: log in and fetch evidence over the OData API.

Ported from the Google Apps Script `loginToAptem` + evidence fetch logic:
  GET the LogOn page -> read the __RequestVerificationToken (CSRF) ->
  POST credentials -> the session picks up the AUTHTOKEN cookie ->
  call OData with X-API-Token + Cookie + Authorization: Bearer <AUTHTOKEN>.
"""

import re

import requests
from django.conf import settings


class AptemAuthError(Exception):
    pass


class AptemClient:
    def __init__(self):
        self.base_url = settings.APTEM_BASE_URL.rstrip("/")
        self.email = settings.APTEM_EMAIL
        self.password = settings.APTEM_PASSWORD
        self.api_token = settings.APTEM_API_TOKEN
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
        self.auth_token = None

    # -- auth ---------------------------------------------------------------
    def login(self):
        login_url = f"{self.base_url}/Users/Account/LogOn"

        page = self.session.get(login_url, headers={"Accept": "text/html"}, timeout=30)
        m = re.search(
            r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', page.text
        ) or re.search(
            r'value="([^"]+)"[^>]*name="__RequestVerificationToken"', page.text
        )
        csrf = m.group(1) if m else ""

        self.session.post(
            login_url,
            data={
                "userNameOrEmail": self.email,
                "password": self.password,
                "__RequestVerificationToken": csrf,
            },
            headers={"Referer": login_url, "Origin": self.base_url},
            allow_redirects=True,
            timeout=30,
        )

        self.auth_token = self.session.cookies.get("AUTHTOKEN")
        if not self.auth_token:
            raise AptemAuthError(
                "Login failed: no AUTHTOKEN cookie returned. "
                "Check APTEM_EMAIL / APTEM_PASSWORD in .env."
            )
        return self.auth_token

    def _api_headers(self):
        return {
            "X-API-Token": self.api_token,
            "Authorization": f"Bearer {self.auth_token}",
            "Accept": "application/json",
        }

    # -- data ---------------------------------------------------------------
    def fetch_evidence(self, learner_id):
        """Return the list of ALL evidence items for a learner (no filter)."""
        url = f"{self.base_url}/odata/1.0/LearningPlanEvidences"
        params = {"$filter": f"LearnerId eq {learner_id}"}
        resp = self.session.get(
            url, params=params, headers=self._api_headers(), timeout=60
        )
        if resp.status_code == 401:
            raise AptemAuthError(f"401 Unauthorized fetching evidence for {learner_id}")
        resp.raise_for_status()
        return resp.json().get("value", [])

    def document_url(self, evidence_id):
        """The raw Aptem document link stored in the `file` column."""
        return (
            f"{self.base_url}/MWS.LearningProgrammes/"
            f"LearningItemEvidence/Document/{evidence_id}"
        )
