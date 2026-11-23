import pytest
from rest_framework.test import APIClient
from reconcile.importer import import_all_data
from reconcile.models import Location


@pytest.fixture(autouse=True)
def load_db(db):
    import_all_data()


@pytest.mark.django_db
def test_tenant_org_a_never_sees_org_b_data():
    """
    Tenant isolation check:
    Assert that no returned row in ORG-A contains an ORG-B location or data.
    """
    client = APIClient()
    response = client.get("/api/disagreements/?org=ORG-A")
    assert response.status_code == 200

    org_b_locations = set(Location.objects.filter(org_id="ORG-B").values_list("location_id", flat=True))
    assert len(org_b_locations) > 0  # e.g. LOC-201, LOC-202

    results = response.data["results"]
    for item in results:
        # location_id must belong to ORG-A
        assert item["location_id"] not in org_b_locations
        assert item.get("a_location") not in org_b_locations
        # If there is a b_location, it must never leak an ORG-B location identifier
        if item.get("b_location"):
            assert item["b_location"] not in org_b_locations


@pytest.mark.django_db
def test_tenant_org_b_never_sees_org_a_data():
    """
    Tenant isolation check:
    Assert that no returned row in ORG-B contains an ORG-A location or data.
    """
    client = APIClient()
    response = client.get("/api/disagreements/?org=ORG-B")
    assert response.status_code == 200

    org_a_locations = set(Location.objects.filter(org_id="ORG-A").values_list("location_id", flat=True))
    assert len(org_a_locations) > 0  # e.g. LOC-101, LOC-102, LOC-103

    results = response.data["results"]
    for item in results:
        assert item["location_id"] not in org_a_locations
        assert item.get("a_location") not in org_a_locations
        if item.get("b_location"):
            assert item["b_location"] not in org_a_locations


@pytest.mark.django_db
def test_cross_tenant_trap_row_airtight_isolation():
    """
    Tests the cross-tenant trap row (REC-1077):
    - In System A, REC-1077 is recorded under LOC-102 (ORG-A).
    - In System B, ENT/2026/4077 is recorded under LOC-201 (ORG-B).
    
    Checks:
    1. For ORG-A: The disagreement is reported as LOCATION_MISMATCH,
       its location is LOC-102, and b_location is redacted to [EXTERNAL_LOCATION].
       Under NO circumstances is 'LOC-201' exposed in the response payload!
    2. For ORG-B: REC-1077 is completely excluded from the result set.
    """
    client = APIClient()

    # Query as ORG-A
    resp_a = client.get("/api/disagreements/?org=ORG-A")
    trap_items_a = [item for item in resp_a.data["results"] if item["record_id"] == "REC-1077"]
    assert len(trap_items_a) == 1
    trap_item = trap_items_a[0]
    assert trap_item["reason"] == "LOCATION_MISMATCH"
    assert trap_item["location_id"] == "LOC-102"
    assert trap_item["b_location"] == "[EXTERNAL_LOCATION]"
    assert "LOC-201" not in str(trap_item)

    # Query as ORG-B
    resp_b = client.get("/api/disagreements/?org=ORG-B")
    trap_items_b = [item for item in resp_b.data["results"] if item["record_id"] == "REC-1077"]
    assert len(trap_items_b) == 0  # Must be 0!
