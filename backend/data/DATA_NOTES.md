# Dataset Analysis & Discrepancy Findings

Notes on raw dataset inspection (`locations.csv`, `system_a.csv`, `system_b.csv`):

## 1. File Summary
| File | Header Row Count | Data Rows | Key Columns | Notes |
|------|------------------|-----------|-------------|-------|
| `locations.csv` | 1 | 5 | `location_id`, `org_id`, `location_name` | LOC-101..103 belong to ORG-A; LOC-201..202 belong to ORG-B. The only authoritative mapping of locations to tenants. |
| `system_a.csv` | 1 | 120 | `record_id`, `location_id`, `event_date`, `category_code`, `actor_id`, `base_value`, `adjustment`, `total_value`, `state` | 1 row per event in System A. `total_value` = `base_value` + `adjustment`. |
| `system_b.csv` | 1 | 121 | `entry_id`, `record_ref`, `location_id`, `recorded_on`, `value`, `label` | Entries in System B pointing to System A via `record_ref`. 121 rows due to duplicates, split, and orphan. |

---

## 2. Identified Dirty Data & Anomalies

### A. Formatting & Reference Inconsistencies (System B)
- `rec1034`: Lowercase prefix, missing hyphen. Cleans to `REC-1034`.
- ` REC - 1070 `: Surrounding and internal whitespace. Cleans to `REC-1070`.
- `1112`: Digits only without prefix. Cleans to `REC-1112`.

### B. Missing or Malformed Values
- **Empty actor_id (System A)**: `REC-1050` has empty `actor_id`. Must be stored as `null`, not crashed or dropped.
- **Empty value (System B)**: `ENT/2026/4050` (`REC-1050`) has an empty string for `value`. Must be stored as `null` (never `0.00`) and flagged as a value mismatch.
- **Indian-style Commas (System B)**: `ENT/2026/4064` (`REC-1064`) has value `'1,25,400.00'`. Must be cleaned to `Decimal('125400.00')`.

### C. Structural Discrepancies
- **Missing Entries in B**: `REC-1015` and `REC-1061` exist in System A but have 0 entries in System B. Flagged as `MISSING_IN_B`.
- **Orphan Entry in B**: `ENT/2026/4901` references `REC-1999`, which does not exist in System A. Location is `LOC-102` (ORG-A). Flagged as `ORPHAN_IN_B`.
- **Real Duplicate in B**: `REC-1042` has two entries (`ENT/2026/4042` and `ENT/2026/4902`), each with value `112837.06`. Sum = `225674.12`, which does not equal A's total (`112837.06`). Flagged as `DUPLICATE_IN_B`.
- **Valid Split Entry in B**: `REC-1055` has two entries (`ENT/2026/4055` for `71950.93` and `ENT/2026/4903` for `107926.39` labeled 'Entry part 2 of 2'). Their sum is `179877.32`, matching System A's `total_value` (`179877.32`) exactly. This is valid ledger splitting and NOT a duplicate.

### D. Value Discrepancies
- Single entry comparisons where B's value != A's `total_value`:
  - `REC-1003`: A=`121388.01`, B=`94834.38` (diff `-26553.63`)
  - `REC-1027`: A=`79259.03`, B=`61921.12` (diff `-17337.91`)
  - `REC-1050`: A=`160405.85`, B=null
  - `REC-1064`: A=`183244.16`, B=`125400.00` (after parsing `1,25,400.00`)
  - `REC-1088`: A=`138948.30`, B=`108553.36` (diff `-30394.94`)

### E. Date Discrepancy
- `REC-1009` (`ENT/2026/4009`): Event date in A is `2026-03-31`, recorded on in B is `2026-04-02`. Flagged as `DATE_MISMATCH`.

### F. Voided Record
- `REC-1019`: Marked as `state = VOIDED` in System A, yet System B has active entry `ENT/2026/4019` with value `57092.35`. Flagged/handled per decision rules.

### G. Cross-Tenant Location Trap Row
- `REC-1077` (`ENT/2026/4077`): System A records location as `LOC-102` (belonging to `ORG-A`), while System B records location as `LOC-201` (belonging to `ORG-B`).
- **Isolation Rule**: When ORG-A queries, it must never see `LOC-201` or any ORG-B identifier.
