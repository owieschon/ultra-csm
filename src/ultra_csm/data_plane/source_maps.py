"""Vendor source maps for the Ultra CSM data plane.

The application uses Pythonic snake_case fields internally, while vendor-backed
fields map back to a documented object or endpoint. Custom, derived, and
internal-only fields are explicitly marked so they are never confused with
vendor-standard fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


PiiClass = Literal["none", "contact", "customer_content", "secret"]


@dataclass(frozen=True)
class SourceField:
    api_name: str
    standard: bool
    note: str = ""
    required: bool = True
    pii: PiiClass = "none"
    llm_allowed: bool = True


@dataclass(frozen=True)
class SourceObjectMap:
    vendor: str
    object_name: str
    docs_url: str
    fields: dict[str, SourceField]


SALESFORCE_SOURCE_MAPS: dict[str, SourceObjectMap] = {
    "CRMAccount": SourceObjectMap(
        vendor="Salesforce",
        object_name="Account",
        docs_url=(
            "https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/"
            "object_reference/sforce_api_objects_account.htm"
        ),
        fields={
            "account_id": SourceField("Id", True),
            "name": SourceField("Name", True),
            "owner_id": SourceField("OwnerId", True),
            "industry": SourceField("Industry", True),
        },
    ),
    "CRMContact": SourceObjectMap(
        vendor="Salesforce",
        object_name="Contact",
        docs_url=(
            "https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/"
            "object_reference/sforce_api_objects_contact.htm"
        ),
        fields={
            "contact_id": SourceField("Id", True),
            "account_id": SourceField("AccountId", True),
            "email": SourceField("Email", True, pii="contact", llm_allowed=False),
            "name": SourceField("Name", True, pii="contact"),
            "title": SourceField("Title", True),
            "role": SourceField("Role__c", False, "customer role extension"),
            "consent_to_contact": SourceField(
                "Consent_To_Contact__c",
                False,
                "communication-policy extension",
            ),
            "org_level": SourceField(
                "Org_Level__c",
                False,
                "optional org-chart hierarchy extension",
            ),
        },
    ),
    "CRMCase": SourceObjectMap(
        vendor="Salesforce",
        object_name="Case",
        docs_url=(
            "https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/"
            "object_reference/sforce_api_objects_case.htm"
        ),
        fields={
            "case_id": SourceField("Id", True),
            "account_id": SourceField("AccountId", True),
            "status": SourceField("Status", True),
            "priority": SourceField("Priority", True),
            "origin": SourceField("Origin", True),
            "subject": SourceField("Subject", True, pii="customer_content"),
            "created_at": SourceField("CreatedDate", True),
            "closed_at": SourceField("ClosedDate", True),
        },
    ),
    "CRMOpportunity": SourceObjectMap(
        vendor="Salesforce",
        object_name="Opportunity",
        docs_url=(
            "https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/"
            "object_reference/sforce_api_objects_opportunity.htm"
        ),
        fields={
            "opportunity_id": SourceField("Id", True),
            "account_id": SourceField("AccountId", True),
            "stage_name": SourceField("StageName", True),
            "amount_cents": SourceField("Amount", True, "stored internally as cents"),
            "close_date": SourceField("CloseDate", True),
            "opportunity_type": SourceField("Type", True),
        },
    ),
    "CRMActivity": SourceObjectMap(
        vendor="Salesforce",
        object_name="Task/Event activity adapter",
        docs_url=(
            "https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/"
            "api_rest/intro_rest.htm"
        ),
        fields={
            "activity_id": SourceField("Id", True),
            "account_id": SourceField(
                "WhatId",
                True,
                "account-related activity target",
            ),
            "channel": SourceField("Channel__c", False),
            "direction": SourceField("Direction__c", False),
            "summary": SourceField("Description", True, pii="customer_content"),
            "occurred_at": SourceField("ActivityDate", True),
            "idempotency_key": SourceField("Idempotency_Key__c", False),
        },
    ),
}


GAINSIGHT_SOURCE_MAPS: dict[str, SourceObjectMap] = {
    "CSCompany": SourceObjectMap(
        vendor="Gainsight",
        object_name="Company",
        docs_url=(
            "https://support.gainsight.com/gainsight_nxt/API_and_Developer_Docs/"
            "Company_and_Relationship_API/Company_API_Documentation"
        ),
        fields={
            "company_id": SourceField("Company Id", True),
            "name": SourceField("Name", True),
            "industry": SourceField("Industry", True),
            "arr_cents": SourceField("ARR", True, "stored internally as cents"),
            "lifecycle_stage": SourceField("Stage", True),
            "status": SourceField("Status", True),
            "original_contract_date": SourceField("OriginalContractDate", True),
            "renewal_date": SourceField("RenewalDate", True),
            "csm_owner_id": SourceField("CSM", True),
            "current_score": SourceField("Current Score", True),
        },
    ),
    "HealthScore": SourceObjectMap(
        vendor="Gainsight",
        object_name="Company Current Score / Scorecard objects",
        docs_url=(
            "https://support.gainsight.com/gainsight_nxt/Gainsight_Object_Glossary/"
            "CS_Object_Glossary/Gainsight_Standard_Objects"
        ),
        fields={
            "account_id": SourceField("Company Id", True),
            "score": SourceField("Current Score", True),
            "band": SourceField("Scorecard scheme definition label/color", True),
            "drivers": SourceField("Scorecard Measure drivers", True),
            "measured_at": SourceField("Modified Date", True),
        },
    ),
    "CTA": SourceObjectMap(
        vendor="Gainsight",
        object_name="CTA",
        docs_url=(
            "https://support.gainsight.com/gainsight_nxt/API_and_Developer_Docs/"
            "Cockpit_API/Call_To_Action_%28CTA%29_API_Documentation"
        ),
        fields={
            "cta_id": SourceField("CTA ID", True),
            "account_id": SourceField("Company ID", True),
            "reason": SourceField("CTA Name", True),
            "priority": SourceField("Priority", True),
            "status": SourceField("Status", True),
            "due_date": SourceField("Due Date", True),
            "owner_id": SourceField("OwnerID", True),
        },
    ),
    "SuccessPlan": SourceObjectMap(
        vendor="Gainsight",
        object_name="Success Plan",
        docs_url=(
            "https://support.gainsight.com/gainsight_nxt/API_and_Developer_Docs/"
            "Success_Plan_APIs/Success_Plan_APIs"
        ),
        fields={
            "plan_id": SourceField("Success Plan ID", True),
            "account_id": SourceField("Company ID", True),
            "status": SourceField("Status", True),
            "objectives": SourceField("Objective CTAs", True),
            "target_date": SourceField("Due Date", True),
        },
    ),
    "AdoptionSummary": SourceObjectMap(
        vendor="Gainsight",
        object_name="Adoption Explorer usage/adoption rollup",
        docs_url=(
            "https://support.gainsight.com/gainsight_nxt/Adoption_Explorer/"
            "Adoption_Explorer_API_Documentation/Adoption_Explorer_APIs"
        ),
        fields={
            "account_id": SourceField("Company", True),
            "active_users": SourceField("Person-level usage derived field", True),
            "licensed_users": SourceField("Company/Person entitlement field", False),
            "active_assets": SourceField("Company-level usage derived field", True),
            "entitled_assets": SourceField("Company entitlement field", False),
            "adoption_rate": SourceField("Derived Field", True),
            "underused_capabilities": SourceField("Derived Field", True),
            "measured_at": SourceField("Project Log / job timestamp", True),
        },
    ),
}


PRODUCT_TELEMETRY_SOURCE_MAPS: dict[str, SourceObjectMap] = {
    "UsageSignal": SourceObjectMap(
        vendor="Product telemetry",
        object_name="Fleet telemetry / IoT usage endpoints",
        docs_url="https://opentelemetry.io/docs/specs/semconv/",
        fields={
            "signal_id": SourceField("event/stat id", True),
            "account_id": SourceField("external customer/account join key", False),
            "grain": SourceField("company/person/asset normalization", False),
            "subject_id": SourceField(
                "vehicle/driver/asset/person id",
                True,
                pii="contact",
                llm_allowed=False,
            ),
            "metric_name": SourceField("stat/event type", True),
            "value": SourceField("stat/event value", True),
            "unit": SourceField("metric unit", True),
            "observed_at": SourceField("time", True),
            "source_ref": SourceField("endpoint/resource reference", True),
        },
    ),
    "Entitlement": SourceObjectMap(
        vendor="Internal entitlement adapter",
        object_name="Contracted capabilities",
        docs_url="internal://commercial-entitlement-adapter",
        fields={
            "account_id": SourceField("account/customer id", False),
            "capability": SourceField("product/capability code", False),
            "entitled_quantity": SourceField("contracted quantity", False),
            "unit": SourceField("unit", False),
            "starts_at": SourceField("contract start", False),
            "ends_at": SourceField("contract end", False),
        },
    ),
}


ALL_SOURCE_MAPS: dict[str, SourceObjectMap] = {
    **SALESFORCE_SOURCE_MAPS,
    **GAINSIGHT_SOURCE_MAPS,
    **PRODUCT_TELEMETRY_SOURCE_MAPS,
}
