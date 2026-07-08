"""Read-only Google Calendar events.list provider.

The provider is intentionally narrow: it reads Calendar events for account
handoff evidence and never writes, mutates, or sends invitations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import os
from typing import Any, Mapping, Protocol
from urllib import parse, request

from ultra_csm.data_plane.contracts import CRMDataConnector

_TOKEN_ENV = "ULTRA_CSM_GOOGLE_CALENDAR_ACCESS_TOKEN"
_CALENDAR_ID_ENV = "ULTRA_CSM_GOOGLE_CALENDAR_ID"


class GoogleCalendarReadError(RuntimeError):
    """A read-only Google Calendar request failed."""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes


class HttpClient(Protocol):
    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse: ...


class UrllibHttpClient:
    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        req = request.Request(url, headers=dict(headers), method="GET")
        with request.urlopen(req, timeout=20) as resp:  # nosec B310 - configured Google API endpoint only.
            return HttpResponse(status=int(resp.status), body=resp.read())


class LiveGoogleCalendarEventsProvider:
    """Google Calendar ``events.list`` implementation scoped to one account."""

    def __init__(
        self,
        *,
        access_token: str,
        calendar_id: str = "primary",
        query_domains: tuple[str, ...] = (),
        http_client: HttpClient | None = None,
    ) -> None:
        self._access_token = access_token
        self._calendar_id = calendar_id
        self._query_domains = tuple(sorted(set(query_domains)))
        self._http = http_client or UrllibHttpClient()

    @classmethod
    def from_env_for_account(
        cls,
        *,
        crm: CRMDataConnector,
        account_id: str,
        env: Mapping[str, str] | None = None,
        http_client: HttpClient | None = None,
    ) -> "LiveGoogleCalendarEventsProvider | None":
        source = env or os.environ
        token = source.get(_TOKEN_ENV)
        if not token:
            return None
        return cls(
            access_token=token,
            calendar_id=source.get(_CALENDAR_ID_ENV, "primary"),
            query_domains=_account_contact_domains(crm, account_id),
            http_client=http_client,
        )

    def list_events(
        self,
        account_id: str,
        *,
        opportunity_id: str | None = None,
        until: str | None = None,
    ) -> dict:
        merged: dict[str, dict[str, Any]] = {}
        queries = self._query_domains or (opportunity_id or account_id,)
        for query in queries:
            payload = self._events_list(query=query, until=until)
            for item in payload.get("items") or ():
                if isinstance(item, dict):
                    event_id = str(item.get("id") or "")
                    if event_id:
                        merged[event_id] = item
        return {"items": list(merged.values())}

    def _events_list(self, *, query: str, until: str | None) -> dict:
        params = {
            "singleEvents": "true",
            "orderBy": "startTime",
            "q": query,
        }
        if until:
            end = _parse_day(until) + timedelta(days=1)
            start = end - timedelta(days=120)
            params["timeMin"] = start.strftime("%Y-%m-%dT00:00:00Z")
            params["timeMax"] = end.strftime("%Y-%m-%dT00:00:00Z")
        url = (
            "https://www.googleapis.com/calendar/v3/calendars/"
            + parse.quote(self._calendar_id, safe="")
            + "/events?"
            + parse.urlencode(params)
        )
        resp = self._http.get(url, headers={"Authorization": f"Bearer {self._access_token}"})
        if resp.status < 200 or resp.status >= 300:
            raise GoogleCalendarReadError(f"Google Calendar events.list failed with HTTP {resp.status}")
        decoded = json.loads(resp.body.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise GoogleCalendarReadError("Google Calendar events.list returned a non-object payload")
        return decoded


def _account_contact_domains(crm: CRMDataConnector, account_id: str) -> tuple[str, ...]:
    domains = []
    for contact in crm.list_contacts(account_id):
        parts = contact.email.lower().rsplit("@", 1)
        if len(parts) == 2 and "." in parts[1]:
            domains.append(parts[1])
    return tuple(sorted(set(domains)))


def _parse_day(value: str) -> datetime:
    return datetime.strptime(value[:10], "%Y-%m-%d")
