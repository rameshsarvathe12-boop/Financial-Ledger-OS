from decimal import Decimal
from typing import Any, Dict, List, Optional, Set


def compare_records(
    a_records: Dict[str, Dict[str, Any]],
    b_entries: List[Dict[str, Any]],
    location_org_map: Dict[str, str],
    tenant_org: Optional[str] = None,
    all_system_a_ids: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Pure Python reconciliation engine comparing System A records with System B entries.
    
    Arguments:
        a_records: dict of record_id -> record details for current tenant
        b_entries: list of entry dicts for current tenant
        location_org_map: dict of location_id -> org_id
        tenant_org: optional tenant string ('ORG-A' | 'ORG-B')
        all_system_a_ids: set of all record_ids existing in System A globally across tenants.
                          Used to distinguish true orphans from cross-tenant misallocations.

    Returns:
        List of disagreement dicts.
    """
    if all_system_a_ids is None:
        all_system_a_ids = set(a_records.keys())

    # Group System B entries by cleaned record_ref
    by_ref: Dict[str, List[Dict[str, Any]]] = {}
    for entry in b_entries:
        ref = entry.get("record_ref")
        if ref:
            by_ref.setdefault(ref, []).append(entry)

    disagreements: List[Dict[str, Any]] = []

    # 1. ORPHAN_IN_B: B entries referencing record_ids not present anywhere in System A
    for ref, entries in by_ref.items():
        if ref not in all_system_a_ids:
            for e in entries:
                e_loc = e["location_id"]
                e_org = location_org_map.get(e_loc, "UNKNOWN")
                
                # Tenant isolation filter: true orphans belong to the tenant owning B's location
                if tenant_org and e_org != tenant_org:
                    continue

                b_val = e.get("value")
                disagreements.append({
                    "reason": "ORPHAN_IN_B",
                    "record_id": ref,
                    "entry_id": e["entry_id"],
                    "location_id": e_loc,
                    "a_location": None,
                    "b_location": e_loc,
                    "a_value": None,
                    "b_value": b_val,
                    "difference": None,
                    "a_date": None,
                    "b_date": str(e["recorded_on"]),
                    "org_id": e_org,
                    "details": f"System B entry {e['entry_id']} references non-existent record {ref} in System A",
                })

    # 2. Walk through all System A records for this tenant
    for rid, a in a_records.items():
        a_loc = a["location_id"]
        a_org = location_org_map.get(a_loc, "UNKNOWN")

        # Tenant isolation check for primary record owner
        if tenant_org and a_org != tenant_org:
            continue

        entries = by_ref.get(rid, [])
        a_total = a["total_value"]

        # Reason: MISSING_IN_B
        if not entries:
            disagreements.append({
                "reason": "MISSING_IN_B",
                "record_id": rid,
                "entry_id": None,
                "location_id": a_loc,
                "a_location": a_loc,
                "b_location": None,
                "a_value": a_total,
                "b_value": None,
                "difference": -a_total if a_total is not None else None,
                "a_date": str(a["event_date"]),
                "b_date": None,
                "org_id": a_org,
                "details": f"System A record {rid} has no matching entry in System B",
            })
            continue

        # Reason: VOIDED_RECORD_HAS_ENTRY
        # If A record is VOIDED, having active B entries represents a ledger discrepancy
        if a.get("state") == "VOIDED":
            valid_vals = [e["value"] for e in entries if e.get("value") is not None]
            b_total_sum = sum(valid_vals) if valid_vals else None
            disagreements.append({
                "reason": "VOIDED_RECORD_HAS_ENTRY",
                "record_id": rid,
                "entry_id": ", ".join(e["entry_id"] for e in entries),
                "location_id": a_loc,
                "a_location": a_loc,
                "b_location": entries[0]["location_id"],
                "a_value": a_total,
                "b_value": b_total_sum,
                "difference": b_total_sum,
                "a_date": str(a["event_date"]),
                "b_date": str(entries[0]["recorded_on"]),
                "org_id": a_org,
                "details": f"Record {rid} is VOIDED in System A, but System B holds active entry",
            })

        # Check for multiple B entries: DUPLICATE_IN_B vs Valid Split
        if len(entries) > 1:
            vals = [e.get("value") for e in entries]
            # If any value is None or sum does not match A's total_value exactly
            if any(v is None for v in vals) or sum(vals) != a_total:
                b_sum = sum(v for v in vals if v is not None)
                diff = (b_sum - a_total) if b_sum is not None else None
                disagreements.append({
                    "reason": "DUPLICATE_IN_B",
                    "record_id": rid,
                    "entry_id": ", ".join(e["entry_id"] for e in entries),
                    "location_id": a_loc,
                    "a_location": a_loc,
                    "b_location": entries[0]["location_id"],
                    "a_value": a_total,
                    "b_value": b_sum,
                    "difference": diff,
                    "a_date": str(a["event_date"]),
                    "b_date": str(entries[0]["recorded_on"]),
                    "org_id": a_org,
                    "details": f"Multiple System B entries for {rid} do not sum to total {a_total}",
                })
                continue
            else:
                # Valid split that adds up cleanly to A's total_value: not a duplicate
                pass

        # Check single entry value mismatch
        if len(entries) == 1:
            e = entries[0]
            b_val = e.get("value")
            if b_val is None or b_val != a_total:
                diff = (b_val - a_total) if b_val is not None else None
                disagreements.append({
                    "reason": "VALUE_MISMATCH",
                    "record_id": rid,
                    "entry_id": e["entry_id"],
                    "location_id": a_loc,
                    "a_location": a_loc,
                    "b_location": e["location_id"],
                    "a_value": a_total,
                    "b_value": b_val,
                    "difference": diff,
                    "a_date": str(a["event_date"]),
                    "b_date": str(e["recorded_on"]),
                    "org_id": a_org,
                    "details": "Value is blank" if b_val is None else f"System A total ({a_total}) != System B value ({b_val})",
                })

        # Check for location and date differences across all entries
        for e in entries:
            e_loc = e["location_id"]
            e_org = location_org_map.get(e_loc, "UNKNOWN")

            # LOCATION_MISMATCH
            if e_loc != a_loc:
                # Cross-Tenant Trap Row Protection:
                # If e_loc belongs to a different org, mask e_loc so tenant_org does NOT see the other tenant's location ID!
                b_location_display = e_loc
                if e_org != a_org:
                    b_location_display = "[EXTERNAL_LOCATION]"

                disagreements.append({
                    "reason": "LOCATION_MISMATCH",
                    "record_id": rid,
                    "entry_id": e["entry_id"],
                    "location_id": a_loc,
                    "a_location": a_loc,
                    "b_location": b_location_display,
                    "a_value": a_total,
                    "b_value": e.get("value"),
                    "difference": (e["value"] - a_total) if e.get("value") is not None else None,
                    "a_date": str(a["event_date"]),
                    "b_date": str(e["recorded_on"]),
                    "org_id": a_org,
                    "details": f"Location mismatch: System A has {a_loc}, System B has {b_location_display}",
                })

            # DATE_MISMATCH
            if str(e["recorded_on"]) != str(a["event_date"]):
                disagreements.append({
                    "reason": "DATE_MISMATCH",
                    "record_id": rid,
                    "entry_id": e["entry_id"],
                    "location_id": a_loc,
                    "a_location": a_loc,
                    "b_location": e_loc,
                    "a_value": a_total,
                    "b_value": e.get("value"),
                    "difference": (e["value"] - a_total) if e.get("value") is not None else None,
                    "a_date": str(a["event_date"]),
                    "b_date": str(e["recorded_on"]),
                    "org_id": a_org,
                    "details": f"Date mismatch: System A date ({a['event_date']}) != System B date ({e['recorded_on']})",
                })

    return disagreements
