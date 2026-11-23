import csv
import logging
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from django.db import transaction
from reconcile.models import Location, SystemARecord, SystemBEntry

logger = logging.getLogger(__name__)


def normalize_ref(raw: str) -> str | None:
    """
    Normalizes messy references like 'rec1034', ' REC - 1070 ', '1112' -> 'REC-1034'.
    Returns None if no digits found.
    """
    if not raw:
        return None
    m = re.search(r"\d+", raw)
    return f"REC-{m.group()}" if m else None


def parse_amount(raw: str) -> Decimal | None:
    """
    Parses currency strings into Decimal, handling comma styles (e.g. '1,25,400.00' -> Decimal('125400.00')).
    Empty string or junk returns None. Never converts to 0!
    """
    if raw is None:
        return None
    s = str(raw).strip().replace(",", "")
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        logger.warning(f"Invalid monetary value: '{raw}' cannot be parsed as Decimal")
        return None


def import_locations(file_path: Path):
    """Imports locations from CSV (idempotent)."""
    saved = 0
    with open(file_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            loc_id = row.get("location_id", "").strip()
            org_id = row.get("org_id", "").strip()
            # support both 'location_name' and 'name' header
            name = (row.get("location_name") or row.get("name") or "").strip()
            Location.objects.update_or_create(
                location_id=loc_id,
                defaults={"org_id": org_id, "name": name}
            )
            saved += 1
    return saved


def import_system_a(file_path: Path):
    """
    Imports System A records from CSV (idempotent).
    Keeps all rows; empty actor_id is stored as None.
    """
    read_count = 0
    saved_count = 0
    blank_actors = 0

    with open(file_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            read_count += 1
            clean_row = {k: (v.strip() if v else "") for k, v in row.items()}
            rec_id = clean_row.get("record_id")
            loc_id = clean_row.get("location_id")
            event_date = clean_row.get("event_date")
            cat = clean_row.get("category_code")
            actor = clean_row.get("actor_id") or None
            if not actor:
                blank_actors += 1

            base_val = parse_amount(clean_row.get("base_value"))
            adj = parse_amount(clean_row.get("adjustment"))
            tot = parse_amount(clean_row.get("total_value"))
            state = clean_row.get("state", "CONFIRMED")

            loc = Location.objects.get(location_id=loc_id)

            SystemARecord.objects.update_or_create(
                record_id=rec_id,
                defaults={
                    "location": loc,
                    "event_date": event_date,
                    "category_code": cat,
                    "actor_id": actor,
                    "base_value": base_val,
                    "adjustment": adj,
                    "total_value": tot,
                    "state": state,
                }
            )
            saved_count += 1

    return read_count, saved_count, blank_actors


def import_system_b(file_path: Path):
    """
    Imports System B entries from CSV (idempotent).
    Handles dirty references and values; bad values stored as None.
    """
    read_count = 0
    saved_count = 0
    empty_values = 0
    cleaned_refs_count = 0

    with open(file_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            read_count += 1
            clean_row = {k: (v.strip() if v else "") for k, v in row.items()}
            entry_id = clean_row.get("entry_id")
            raw_ref = clean_row.get("record_ref", "")
            cleaned_ref = normalize_ref(raw_ref)
            if raw_ref != cleaned_ref:
                cleaned_refs_count += 1

            loc_id = clean_row.get("location_id")
            rec_on = clean_row.get("recorded_on")
            raw_val = clean_row.get("value", "")
            parsed_val = parse_amount(raw_val)
            if parsed_val is None:
                empty_values += 1

            lbl = clean_row.get("label", "")
            loc = Location.objects.get(location_id=loc_id)

            SystemBEntry.objects.update_or_create(
                entry_id=entry_id,
                defaults={
                    "record_ref_raw": raw_ref,
                    "record_ref": cleaned_ref,
                    "location": loc,
                    "recorded_on": rec_on,
                    "value_raw": raw_val,
                    "value": parsed_val,
                    "label": lbl,
                }
            )
            saved_count += 1

    return read_count, saved_count, empty_values, cleaned_refs_count


def import_all_data(data_dir: Path | str | None = None):
    """
    Imports locations, System A records, and System B entries from data_dir.
    Returns summary metrics dict.
    """
    if data_dir is None:
        data_dir = Path(__file__).resolve().parent.parent / "data"
    else:
        data_dir = Path(data_dir)

    loc_file = data_dir / "locations.csv"
    a_file = data_dir / "system_a.csv"
    b_file = data_dir / "system_b.csv"

    if not (loc_file.exists() and a_file.exists() and b_file.exists()):
        raise FileNotFoundError(f"One or more required CSV files missing in {data_dir}")

    with transaction.atomic():
        loc_saved = import_locations(loc_file)
        a_read, a_saved, a_blank_actors = import_system_a(a_file)
        b_read, b_saved, b_empty_vals, b_cleaned_refs = import_system_b(b_file)

    summary = {
        "locations_saved": loc_saved,
        "a_read": a_read,
        "a_saved": a_saved,
        "a_blank_actors": a_blank_actors,
        "b_read": b_read,
        "b_saved": b_saved,
        "b_empty_values": b_empty_vals,
        "b_cleaned_refs": b_cleaned_refs,
    }
    return summary
