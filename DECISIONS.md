# Architectural & Technical Decisions (DECISIONS.md)

## Decision: compare B's value with A's total_value
-Rejected: compare with base_value
-Why: System B records reflect the full transaction amount (base_value + adjustment); manual inspection of rows like REC-1001 and REC-1002 shows B's value matches A's total_value on nearly every clean row.

## Decision: parse blank/whitespace amounts as null (None) rather than 0.00
-Rejected: default missing values to Decimal('0.00')
-Why: An empty value indicates an unrecorded or missing figure rather than a transaction with zero monetary consideration; defaulting to 0 would distort financial difference calculations and disguise missing input.

## Decision: normalize reference formats using regex extraction of numeric IDs
-Rejected: strict exact string matching or manual case-by-case mapping
-Why: System B contains prefixes with varying case ('rec1034'), whitespace padding (' REC - 1070 '), and missing prefixes ('1112'); extracting digits into canonical 'REC-{digits}' format safely unifies them without corrupting legitimate identifiers.

## Decision: accept split entries summing exactly to A's total as valid reconciliation matches
-Rejected: flag any A record with multiple B entries as DUPLICATE_IN_B
-Why: Row REC-1055 has two entries (71950.93 and 107926.39 labeled 'Entry part 2 of 2') which sum precisely to A's total_value (179877.32); this is legitimate multi-part transaction batching rather than an erroneous duplication.

## Decision: treat active B entries on VOIDED System A records as distinct ledger discrepancies
-Rejected: ignore B entries for voided A records or treat them as valid matches
-Why: In financial ledger systems, a voided event should not carry active monetary claims; flagging VOIDED_RECORD_HAS_ENTRY alerts operations that a canceled transaction has an unaccounted active ledger posting in System B.

## Decision: isolate cross-tenant discrepancies by masking foreign branch identifiers
-Rejected: display raw other-tenant location codes across boundaries or completely drop the discrepancy
-Why: When System A is owned by ORG-A (e.g. REC-1077 at LOC-102) but System B erroneously records it at LOC-201 (ORG-B), revealing 'LOC-201' to ORG-A leaks proprietary branch structure, while hiding it conceals a real discrepancy; showing it to ORG-A with B's location redacted to '[EXTERNAL_LOCATION]' preserves both reconciliation visibility and strict tenant confidentiality.

## Decision: utilize Python Decimal and Django DecimalField for monetary columns
-Rejected: native binary floating-point (float) or integer cents
-Why: Floating-point arithmetic produces precision errors (e.g., 0.1 + 0.2 != 0.3) fatal to financial reconciliation; Decimal guarantees exact base-10 arithmetic matching accounting standards.

## Decision: enforce tenant isolation inside SQL queries rather than frontend filtering
-Rejected: fetching all disagreements and filtering by organization in React
-Why: Client-side filtering leaves unfiltered cross-tenant payload data exposed in browser developer tools (Network tab); querying strictly with `location__org_id` at the database level guarantees zero data leakage across organizational boundaries.
