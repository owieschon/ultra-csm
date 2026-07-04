"""Universe v2 WS-Perturbation-Drift: perturbation library unit tests, on a
toy book (not any real tenant fixture) -- these prove the five D7-axis
functions are deterministic and invariant-preserving in isolation."""

from __future__ import annotations

from eval.perturbation.perturb import (
    arr_shift,
    hygiene_drop,
    latency_scale,
    latency_scale_recent_window,
    schema_rename,
    volume_scale,
)
from ultra_csm.data_plane.contracts import CommunicationSignal, CRMContact, CSCompany


def _toy_signals() -> tuple[CommunicationSignal, ...]:
    return (
        CommunicationSignal(
            signal_id="sig-1", account_id="acct-1", contact_id="c-1", channel="email",
            direction="outbound", timestamp="2026-01-01T00:00:00Z",
        ),
        CommunicationSignal(
            signal_id="sig-2", account_id="acct-1", contact_id="c-1", channel="email",
            direction="inbound", timestamp="2026-01-02T00:00:00Z", response_time_hours=10.0,
        ),
        CommunicationSignal(
            signal_id="sig-3", account_id="acct-1", contact_id="c-1", channel="email",
            direction="inbound", timestamp="2026-02-01T00:00:00Z", response_time_hours=20.0,
        ),
    )


def test_latency_scale_scales_only_inbound_response_time():
    scaled = latency_scale(_toy_signals(), 3.0)
    assert scaled[0].response_time_hours is None  # outbound untouched
    assert scaled[1].response_time_hours == 30.0
    assert scaled[2].response_time_hours == 60.0


def test_latency_scale_preserves_timestamps_and_order():
    original = _toy_signals()
    scaled = latency_scale(original, 2.0)
    assert [s.timestamp for s in scaled] == [s.timestamp for s in original]
    assert [s.signal_id for s in scaled] == [s.signal_id for s in original]


def test_latency_scale_is_deterministic():
    a = latency_scale(_toy_signals(), 1.5)
    b = latency_scale(_toy_signals(), 1.5)
    assert a == b


def test_latency_scale_does_not_mutate_input():
    original = _toy_signals()
    latency_scale(original, 5.0)
    assert original[1].response_time_hours == 10.0


def test_latency_scale_recent_window_only_scales_after_cutoff():
    signals = _toy_signals()
    # now_days chosen so sig-3 (Feb 1) is "recent" (within 10 days of now)
    # and sig-2 (Jan 2) is not.
    from datetime import date

    now_days = (date(2026, 2, 5) - date(1970, 1, 1)).days
    scaled = latency_scale_recent_window(signals, 3.0, as_of_days_ago_cutoff=10, now_days=now_days)
    assert scaled[1].response_time_hours == 10.0  # untouched, outside window
    assert scaled[2].response_time_hours == 60.0  # scaled, inside window


def test_volume_scale_up_adds_fillers_without_removing_real_signals():
    original = _toy_signals()
    scaled = volume_scale(original, 2.0, account_id="acct-1")
    assert len(scaled) > len(original)
    for s in original:
        assert s.signal_id in {x.signal_id for x in scaled}


def test_volume_scale_down_never_drops_protected_signals():
    original = _toy_signals()
    scaled = volume_scale(original, 0.1, protected_signal_ids=frozenset({"sig-2", "sig-3"}), account_id="acct-1")
    kept_ids = {s.signal_id for s in scaled}
    assert "sig-2" in kept_ids
    assert "sig-3" in kept_ids


def test_volume_scale_is_deterministic():
    a = volume_scale(_toy_signals(), 0.5, account_id="acct-1")
    b = volume_scale(_toy_signals(), 0.5, account_id="acct-1")
    assert a == b


def test_hygiene_drop_never_nulls_required_fields():
    contacts = (
        CRMContact("c-1", "a-1", "a@x.example", "Alice", "ops", "Manager", True, 3),
        CRMContact("c-2", "a-1", "b@x.example", "Bob", "it", "Lead", True, 4),
        CRMContact("c-3", "a-1", "c@x.example", "Carol", "ops", "Director", False, 2),
        CRMContact("c-4", "a-1", "d@x.example", "Dave", "it", "IC", True, 5),
    )
    dropped = hygiene_drop(contacts, 0.5)
    for original, after in zip(contacts, dropped):
        assert after.contact_id == original.contact_id
        assert after.account_id == original.account_id
        assert after.email == original.email
        assert after.name == original.name
        assert after.consent_to_contact == original.consent_to_contact
    nulled = [c for c in dropped if c.title is None and c.role is None and c.org_level is None]
    assert len(nulled) == 2


def test_hygiene_drop_is_deterministic():
    contacts = (CRMContact("c-1", "a-1", "a@x.example", "Alice", "ops", "Manager", True),)
    assert hygiene_drop(contacts, 1.0) == hygiene_drop(contacts, 1.0)


def test_schema_rename_renames_only_mapped_keys():
    records = [{"Id": "1", "Industry": "logistics", "Name": "Acme"}]
    renamed = schema_rename(records, {"Industry": "Vertical"})
    assert renamed == [{"Id": "1", "Vertical": "logistics", "Name": "Acme"}]


def test_schema_rename_does_not_mutate_input():
    records = [{"Industry": "logistics"}]
    schema_rename(records, {"Industry": "Vertical"})
    assert records == [{"Industry": "logistics"}]


def test_arr_shift_scales_and_rounds():
    companies = (CSCompany("co-1", "Acme", "logistics", 10_000_000, "steady_state", "Active", "2025-01-01", "2027-01-01", "csm-1", 80.0),)
    shifted = arr_shift(companies, -0.6)
    assert shifted[0].arr_cents == 4_000_000


def test_arr_shift_is_deterministic():
    companies = (CSCompany("co-1", "Acme", "logistics", 10_000_000, "steady_state", "Active", "2025-01-01", "2027-01-01", "csm-1", 80.0),)
    assert arr_shift(companies, 0.1) == arr_shift(companies, 0.1)
