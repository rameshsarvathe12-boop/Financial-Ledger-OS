from decimal import Decimal
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from reconcile.models import Location, SystemARecord, SystemBEntry
from reconcile.compare import compare_records


class DisagreementListView(APIView):
    """
    GET /api/disagreements/?org=ORG-A&reason=VALUE_MISMATCH&sort=-value
    
    Returns ledger reconciliation discrepancies between System A and System B
    with strict tenant isolation enforced at the database level.
    """

    def get(self, request):
        org = request.query_params.get("org", "").strip()
        if not org:
            return Response(
                {"error": "The 'org' query parameter is required (e.g. ?org=ORG-A) to enforce tenant isolation."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if org exists
        valid_orgs = list(Location.objects.values_list("org_id", flat=True).distinct())
        if org not in valid_orgs:
            return Response(
                {"error": f"Invalid org '{org}'. Valid tenant organizations are: {valid_orgs}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 1. Authoritative location-to-org map
        loc_org_map = dict(Location.objects.values_list("location_id", "org_id"))

        # Global set of all System A record IDs to detect true orphans vs other-tenant records
        all_system_a_ids = set(SystemARecord.objects.values_list("record_id", flat=True))

        # 2. Strict tenant-scoped database query:
        # Fetch System A records owned by this tenant's locations
        a_qs = SystemARecord.objects.filter(location__org_id=org).select_related("location")
        tenant_a_record_ids = set(a_qs.values_list("record_id", flat=True))

        a_records = {
            r.record_id: {
                "record_id": r.record_id,
                "location_id": r.location_id,
                "event_date": str(r.event_date),
                "total_value": r.total_value,
                "state": r.state,
                "category_code": r.category_code,
                "actor_id": r.actor_id,
            }
            for r in a_qs
        }

        # Fetch System B entries that:
        # (a) Point to this tenant's System A records (e.g. normal matches, splits, or cross-tenant trap rows owned by this tenant), OR
        # (b) Belong to this tenant's locations AND are true orphans (pointing to records non-existent in System A globally).
        # We explicitly EXCLUDE entries at this tenant's locations that point to ANOTHER tenant's System A records.
        b_qs = SystemBEntry.objects.filter(
            Q(record_ref__in=tenant_a_record_ids) |
            (Q(location__org_id=org) & ~Q(record_ref__in=all_system_a_ids))
        ).select_related("location")

        b_entries = [
            {
                "entry_id": b.entry_id,
                "record_ref": b.record_ref,
                "record_ref_raw": b.record_ref_raw,
                "location_id": b.location_id,
                "recorded_on": str(b.recorded_on),
                "value": b.value,
                "value_raw": b.value_raw,
                "label": b.label,
            }
            for b in b_qs
        ]

        # 3. Execute comparison with tenant protection
        disagreements = compare_records(
            a_records=a_records,
            b_entries=b_entries,
            location_org_map=loc_org_map,
            tenant_org=org,
            all_system_a_ids=all_system_a_ids,
        )

        # 4. Reason filter
        reason_filter = request.query_params.get("reason", "").strip()
        if reason_filter:
            disagreements = [d for d in disagreements if d["reason"].upper() == reason_filter.upper()]

        # 5. Sorting
        sort_param = request.query_params.get("sort", "-value").strip()
        reverse = sort_param.startswith("-")
        sort_key = sort_param.lstrip("-")

        def extract_sort_val(d):
            if sort_key == "value":
                val = d.get("b_value") or d.get("a_value") or Decimal(0)
                return abs(val)
            elif sort_key == "difference":
                diff = d.get("difference")
                return abs(diff) if diff is not None else Decimal(-1)
            elif sort_key == "record_id":
                return d.get("record_id") or ""
            elif sort_key == "reason":
                return d.get("reason") or ""
            elif sort_key == "location":
                return d.get("location_id") or ""
            return d.get("record_id") or ""

        disagreements.sort(key=extract_sort_val, reverse=reverse)

        # 6. Build summary of all reasons for this tenant
        all_tenant_disagreements = compare_records(
            a_records=a_records,
            b_entries=b_entries,
            location_org_map=loc_org_map,
            tenant_org=org,
            all_system_a_ids=all_system_a_ids,
        )
        reason_counts = {}
        for d in all_tenant_disagreements:
            r = d["reason"]
            reason_counts[r] = reason_counts.get(r, 0) + 1

        return Response({
            "org": org,
            "total_count": len(disagreements),
            "reason_summary": reason_counts,
            "results": disagreements,
        })


class TenantListView(APIView):
    """
    GET /api/orgs/
    Returns list of available tenant organizations and their associated locations.
    """
    def get(self, request):
        locations = Location.objects.all().order_by("org_id", "location_id")
        orgs_map = {}
        for loc in locations:
            orgs_map.setdefault(loc.org_id, []).append({
                "location_id": loc.location_id,
                "name": loc.name,
            })
        return Response({
            "orgs": [{"org_id": org, "locations": locs} for org, locs in orgs_map.items()]
        })
