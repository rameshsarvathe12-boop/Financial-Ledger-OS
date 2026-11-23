from decimal import Decimal
import pytest
from reconcile.compare import compare_records
from reconcile.importer import normalize_ref, parse_amount


LOC_ORG_MAP = {
    "LOC-101": "ORG-A",
    "LOC-102": "ORG-A",
    "LOC-103": "ORG-A",
    "LOC-201": "ORG-B",
    "LOC-202": "ORG-B",
}


def make_a_record(
    record_id="REC-1001",
    location_id="LOC-101",
    event_date="2026-03-01",
    total_value="1000.00",
    state="CONFIRMED",
    category_code="CAT-01",
    actor_id="ACT-01",
):
    return {
        "record_id": record_id,
        "location_id": location_id,
        "event_date": event_date,
        "total_value": Decimal(total_value),
        "state": state,
        "category_code": category_code,
        "actor_id": actor_id,
    }


def make_b_entry(
    entry_id="ENT/2026/001",
    record_ref="REC-1001",
    location_id="LOC-101",
    recorded_on="2026-03-01",
    value="1000.00",
    label="Entry",
):
    parsed_val = Decimal(value) if value is not None and value != "" else None
    return {
        "entry_id": entry_id,
        "record_ref": normalize_ref(record_ref),
        "record_ref_raw": record_ref,
        "location_id": location_id,
        "recorded_on": recorded_on,
        "value": parsed_val,
        "value_raw": value or "",
        "label": label,
    }


def test_clean_row_produces_no_disagreement():
    """A clean matching pair between System A and System B produces no disagreements."""
    a = {"REC-1001": make_a_record("REC-1001", total_value="1500.00")}
    b = [make_b_entry("ENT-1", "REC-1001", value="1500.00")]
    result = compare_records(a, b, LOC_ORG_MAP)
    assert result == []


def test_missing_in_b_flagged():
    """An A record that has no matching B entry is flagged as MISSING_IN_B."""
    a = {"REC-1001": make_a_record("REC-1001", total_value="1200.00")}
    b = []
    result = compare_records(a, b, LOC_ORG_MAP)
    assert len(result) == 1
    assert result[0]["reason"] == "MISSING_IN_B"
    assert result[0]["record_id"] == "REC-1001"
    assert result[0]["a_value"] == Decimal("1200.00")
    assert result[0]["b_value"] is None


def test_orphan_in_b_flagged():
    """A B entry that references a non-existent A record is flagged as ORPHAN_IN_B."""
    a = {}
    b = [make_b_entry("ENT-99", "REC-9999", location_id="LOC-101", value="450.00")]
    result = compare_records(a, b, LOC_ORG_MAP)
    assert len(result) == 1
    assert result[0]["reason"] == "ORPHAN_IN_B"
    assert result[0]["record_id"] == "REC-9999"
    assert result[0]["entry_id"] == "ENT-99"
    assert result[0]["b_value"] == Decimal("450.00")
    assert result[0]["a_value"] is None


def test_duplicate_in_b_flagged():
    """Two entries in B that do not sum to A's total are flagged as DUPLICATE_IN_B."""
    a = {"REC-1001": make_a_record("REC-1001", total_value="1000.00")}
    b = [
        make_b_entry("ENT-1", "REC-1001", value="1000.00"),
        make_b_entry("ENT-2", "REC-1001", value="1000.00"),
    ]
    result = compare_records(a, b, LOC_ORG_MAP)
    assert len(result) == 1
    assert result[0]["reason"] == "DUPLICATE_IN_B"
    assert result[0]["record_id"] == "REC-1001"
    assert result[0]["b_value"] == Decimal("2000.00")


def test_split_entries_that_sum_are_not_flagged():
    """Two entries in B that sum exactly to A's total represent a valid split and are NOT flagged."""
    a = {"REC-1001": make_a_record("REC-1001", total_value="2000.00")}
    b = [
        make_b_entry("ENT-1", "REC-1001", value="1200.00", label="part 1 of 2"),
        make_b_entry("ENT-2", "REC-1001", value="800.00", label="part 2 of 2"),
    ]
    result = compare_records(a, b, LOC_ORG_MAP)
    assert result == []


def test_value_mismatch_flagged():
    """Different amounts between A's total and B's value are flagged as VALUE_MISMATCH."""
    a = {"REC-1001": make_a_record("REC-1001", total_value="5000.00")}
    b = [make_b_entry("ENT-1", "REC-1001", value="4800.00")]
    result = compare_records(a, b, LOC_ORG_MAP)
    assert len(result) == 1
    assert result[0]["reason"] == "VALUE_MISMATCH"
    assert result[0]["a_value"] == Decimal("5000.00")
    assert result[0]["b_value"] == Decimal("4800.00")
    assert result[0]["difference"] == Decimal("-200.00")


def test_blank_value_is_flagged_and_not_treated_as_zero():
    """A blank value in B is flagged as VALUE_MISMATCH and preserved as None, never 0."""
    a = {"REC-1001": make_a_record("REC-1001", total_value="350.00")}
    b = [make_b_entry("ENT-1", "REC-1001", value="")]
    result = compare_records(a, b, LOC_ORG_MAP)
    assert len(result) == 1
    assert result[0]["reason"] == "VALUE_MISMATCH"
    assert result[0]["b_value"] is None
    assert result[0]["b_value"] != Decimal("0.00")


def test_messy_references_normalized():
    """Messy references like 'rec1034', ' REC - 1070 ', and '1112' match correctly and do not produce errors."""
    assert normalize_ref("rec1034") == "REC-1034"
    assert normalize_ref(" REC - 1070 ") == "REC-1070"
    assert normalize_ref("1112") == "REC-1112"

    a = {
        "REC-1034": make_a_record("REC-1034", total_value="100.00"),
        "REC-1070": make_a_record("REC-1070", total_value="200.00"),
        "REC-1112": make_a_record("REC-1112", total_value="300.00"),
    }
    b = [
        make_b_entry("E1", "rec1034", value="100.00"),
        make_b_entry("E2", " REC - 1070 ", value="200.00"),
        make_b_entry("E3", "1112", value="300.00"),
    ]
    result = compare_records(a, b, LOC_ORG_MAP)
    assert result == []


def test_date_mismatch_flagged():
    """Discrepancy between System A's event_date and System B's recorded_on is flagged."""
    a = {"REC-1001": make_a_record("REC-1001", event_date="2026-03-01", total_value="100.00")}
    b = [make_b_entry("E1", "REC-1001", recorded_on="2026-03-05", value="100.00")]
    result = compare_records(a, b, LOC_ORG_MAP)
    assert len(result) == 1
    assert result[0]["reason"] == "DATE_MISMATCH"
    assert result[0]["a_date"] == "2026-03-01"
    assert result[0]["b_date"] == "2026-03-05"


def test_location_mismatch_same_tenant_flagged():
    """Location mismatch within the same tenant displays both locations."""
    a = {"REC-1001": make_a_record("REC-1001", location_id="LOC-101", total_value="100.00")}
    b = [make_b_entry("E1", "REC-1001", location_id="LOC-102", value="100.00")]
    result = compare_records(a, b, LOC_ORG_MAP, tenant_org="ORG-A")
    assert len(result) == 1
    assert result[0]["reason"] == "LOCATION_MISMATCH"
    assert result[0]["a_location"] == "LOC-101"
    assert result[0]["b_location"] == "LOC-102"


def test_cross_tenant_trap_row_masks_other_org_location():
    """
    Trap Row: System A has LOC-102 (ORG-A), but System B has LOC-201 (ORG-B).
    When ORG-A queries, it MUST NOT see 'LOC-201' (which would leak ORG-B information).
    It must see [EXTERNAL_LOCATION] or masked location.
    When ORG-B queries, it must not see ORG-A's transaction at all.
    """
    a = {"REC-1077": make_a_record("REC-1077", location_id="LOC-102", total_value="500.00")}
    b = [make_b_entry("E-Trap", "REC-1077", location_id="LOC-201", value="500.00")]

    # Query as ORG-A
    res_a = compare_records(a, b, LOC_ORG_MAP, tenant_org="ORG-A")
    assert len(res_a) == 1
    assert res_a[0]["reason"] == "LOCATION_MISMATCH"
    assert res_a[0]["a_location"] == "LOC-102"
    assert res_a[0]["b_location"] == "[EXTERNAL_LOCATION]"  # Masked! Never leaks LOC-201
    assert "LOC-201" not in str(res_a[0])

    # Query as ORG-B
    res_b = compare_records(a, b, LOC_ORG_MAP, tenant_org="ORG-B")
    assert res_b == []  # ORG-B has zero visibility into ORG-A records


def test_voided_record_with_active_entry():
    """A VOIDED record in System A that has active B entries is flagged."""
    a = {"REC-1019": make_a_record("REC-1019", state="VOIDED", total_value="300.00")}
    b = [make_b_entry("E1", "REC-1019", value="300.00")]
    result = compare_records(a, b, LOC_ORG_MAP)
    assert any(r["reason"] == "VOIDED_RECORD_HAS_ENTRY" for r in result)


def test_parse_amount_variations():
    """Validates robust parsing of amounts including commas and empty strings."""
    assert parse_amount("1,25,400.00") == Decimal("125400.00")
    assert parse_amount(" 500.50 ") == Decimal("500.50")
    assert parse_amount("") is None
    assert parse_amount(None) is None
    assert parse_amount("invalid_text") is None
