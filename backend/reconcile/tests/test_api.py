import pytest
from rest_framework.test import APIClient
from reconcile.importer import import_all_data


@pytest.fixture(autouse=True)
def load_sample_dataset(db):
    """Load the dataset into the database for API integration tests."""
    import_all_data()


@pytest.mark.django_db
def test_disagreements_requires_org_param():
    """Calling /api/disagreements/ without 'org' returns 400 Bad Request to prevent tenant leaks."""
    client = APIClient()
    response = client.get("/api/disagreements/")
    assert response.status_code == 400
    assert "org" in response.data["error"].lower()


@pytest.mark.django_db
def test_disagreements_invalid_org():
    """Calling /api/disagreements/ with unknown org returns 404."""
    client = APIClient()
    response = client.get("/api/disagreements/?org=NON_EXISTENT")
    assert response.status_code == 404


@pytest.mark.django_db
def test_disagreements_org_a_returns_expected_structure():
    """Calling /api/disagreements/?org=ORG-A returns results with reason summary and valid fields."""
    client = APIClient()
    response = client.get("/api/disagreements/?org=ORG-A")
    assert response.status_code == 200
    data = response.data
    assert data["org"] == "ORG-A"
    assert "reason_summary" in data
    assert "results" in data
    assert isinstance(data["results"], list)

    for item in data["results"]:
        assert "reason" in item
        assert "record_id" in item
        assert "location_id" in item
        assert "a_value" in item
        assert "b_value" in item
        assert "details" in item


@pytest.mark.django_db
def test_filter_by_reason():
    """Filtering by reason returns only matching discrepancy types."""
    client = APIClient()
    response = client.get("/api/disagreements/?org=ORG-A&reason=VALUE_MISMATCH")
    assert response.status_code == 200
    for item in response.data["results"]:
        assert item["reason"] == "VALUE_MISMATCH"


@pytest.mark.django_db
def test_sort_by_value():
    """Sorting by value orders items by monetary value."""
    client = APIClient()
    response = client.get("/api/disagreements/?org=ORG-A&sort=-value")
    assert response.status_code == 200
    results = response.data["results"]
    if len(results) >= 2:
        val0 = abs(results[0]["b_value"] or results[0]["a_value"] or 0)
        val1 = abs(results[1]["b_value"] or results[1]["a_value"] or 0)
        assert val0 >= val1


@pytest.mark.django_db
def test_tenant_list_api():
    """GET /api/orgs/ returns all tenant organizations and their branches."""
    client = APIClient()
    response = client.get("/api/orgs/")
    assert response.status_code == 200
    org_ids = [o["org_id"] for o in response.data["orgs"]]
    assert "ORG-A" in org_ids
    assert "ORG-B" in org_ids
