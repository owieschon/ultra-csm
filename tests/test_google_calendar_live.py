from __future__ import annotations

import json

from ultra_csm.data_plane.contracts import CRMAccount, CRMContact
from ultra_csm.data_plane.fixtures import (
    DEFAULT_TENANT,
    FixtureCRMDataConnector,
    FixtureCustomerData,
)
from ultra_csm.data_plane.google_calendar_live import (
    HttpResponse,
    LiveGoogleCalendarEventsProvider,
)


class _FakeHttp:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def get(self, url: str, headers):
        self.urls.append(url)
        assert headers["Authorization"] == "Bearer token-1"
        return HttpResponse(
            200,
            json.dumps({
                "items": [{
                    "id": "cal-1",
                    "summary": "Kickoff",
                    "start": {"dateTime": "2026-07-08T12:00:00Z"},
                    "status": "confirmed",
                    "attendees": [{"email": "buyer@example-customer.com"}],
                }]
            }).encode("utf-8"),
        )


def test_live_google_calendar_provider_queries_salesforce_contact_domain():
    account = CRMAccount("acct-1", "Example Customer", "owner-1", "software")
    data = FixtureCustomerData(
        accounts=(account,),
        companies=(),
        contacts=(
            CRMContact("contact-1", "acct-1", "admin@example-customer.com", "Admin", "admin", None, True),
        ),
        cases=(),
        opportunities=(),
        health_scores=(),
        ctas=(),
        success_plans=(),
        adoption_summaries=(),
        entitlements=(),
        usage_signals=(),
        milestones=(),
        tenant_accounts={DEFAULT_TENANT: ("acct-1",)},
    )
    http = _FakeHttp()

    provider = LiveGoogleCalendarEventsProvider.from_env_for_account(
        crm=FixtureCRMDataConnector(tenant=DEFAULT_TENANT, data=data),
        account_id="acct-1",
        env={
            "ULTRA_CSM_GOOGLE_CALENDAR_ACCESS_TOKEN": "token-1",
            "ULTRA_CSM_GOOGLE_CALENDAR_ID": "primary",
        },
        http_client=http,
    )

    assert provider is not None
    events = provider.list_events("acct-1", opportunity_id="opp-1", until="2026-07-08")

    assert events["items"][0]["id"] == "cal-1"
    assert "example-customer.com" in http.urls[0]
    assert "timeMin=2026-03-11T00%3A00%3A00Z" in http.urls[0]
