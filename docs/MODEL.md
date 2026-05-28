# Data Model — Breathe ESG Ingestion Platform

## Core Design Philosophy

The model is built around three invariants:
1. **Every row knows where it came from** — source, file, timestamp, raw hash
2. **Nothing is silently mutated** — edits create audit records, not overwrites
3. **Scope categorization is explicit, not inferred at query time**

---

## Entity Overview

```
Tenant
  └── DataSource (SAP / Utility / Travel)
        └── IngestionBatch
              └── RawRecord (immutable)
                    └── NormalizedRecord (mutable via EditLog)
                          └── AuditApproval
```

---

## Tables

### `tenants`
Multi-tenancy anchor. Every other table foreign-keys here.

| column | type | notes |
|--------|------|-------|
| id | UUID PK | |
| name | varchar | e.g. "Acme Corp" |
| slug | varchar unique | used in API paths |
| created_at | timestamptz | |

**Why UUID over serial int?** Tenants will eventually be exposed in URLs and API responses. Auto-increment integers leak record counts and are trivially enumerable.

---

### `data_sources`
One row per configured feed per tenant.

| column | type | notes |
|--------|------|-------|
| id | UUID PK | |
| tenant_id | FK → tenants | |
| source_type | enum | SAP_FUEL, SAP_PROCUREMENT, UTILITY_ELECTRICITY, TRAVEL_FLIGHT, TRAVEL_HOTEL, TRAVEL_GROUND |
| scope | enum | SCOPE_1, SCOPE_2, SCOPE_3 |
| label | varchar | human name, e.g. "Plant DE01 SAP Export" |
| config | jsonb | source-specific config (delimiter, encoding, unit system) |
| created_at | timestamptz | |

**Scope assignment lives here, not on NormalizedRecord**, because scope is a property of the source type, not the individual row. Fuel combustion is always Scope 1. Purchased electricity is always Scope 2. Business travel is always Scope 3.

---

### `ingestion_batches`
One row per upload/pull event.

| column | type | notes |
|--------|------|-------|
| id | UUID PK | |
| data_source_id | FK → data_sources | |
| ingested_at | timestamptz | |
| ingested_by | FK → users | |
| file_name | varchar | original filename |
| file_hash | varchar | SHA-256 of raw file — deduplication guard |
| row_count | int | total rows parsed |
| error_count | int | rows that failed validation |
| status | enum | PENDING, PROCESSING, COMPLETE, FAILED |

**file_hash** prevents the same file being uploaded twice — common when facilities teams re-export the same month repeatedly.

---

### `raw_records`
Immutable. Written once at ingestion, never updated.

| column | type | notes |
|--------|------|-------|
| id | UUID PK | |
| batch_id | FK → ingestion_batches | |
| row_index | int | position in source file |
| raw_data | jsonb | original row as parsed, zero transformation |
| parse_error | text | null if clean, error message if failed |
| created_at | timestamptz | |

**Why JSONB for raw_data?** Each source has a completely different shape. A SAP MB51 export looks nothing like a Concur itinerary CSV. Normalizing at raw ingestion would require upfront knowledge of every possible source format. Raw is raw — we preserve origin, normalization is a separate auditable step.

---

### `normalized_records`
One-to-one with raw_records (null if raw had a parse error).

| column | type | notes |
|--------|------|-------|
| id | UUID PK | |
| raw_record_id | FK → raw_records UNIQUE | |
| data_source_id | FK → data_sources | denormalized for query perf |
| tenant_id | FK → tenants | denormalized |
| activity_date | date | normalized to period start |
| period_start | date | |
| period_end | date | |
| quantity | numeric(14,4) | normalized canonical quantity |
| unit | enum | KWH, GJ, LITERS, KG, KM, NIGHTS |
| quantity_co2e_kg | numeric(14,4) | computed CO2e, nullable |
| emission_factor_source | varchar | e.g. "DEFRA 2023" |
| description | text | human-readable activity |
| location | varchar | plant code, meter ID, airport pair, city |
| currency | char(3) | ISO 4217 |
| amount_local | numeric(14,2) | spend in local currency |
| flags | jsonb | warnings e.g. {"unit_estimated": true} |
| review_status | enum | PENDING, FLAGGED, APPROVED, REJECTED |
| reviewed_by | FK → users | nullable |
| reviewed_at | timestamptz | nullable |
| locked_at | timestamptz | set when sent to auditors |
| created_at | timestamptz | |
| updated_at | timestamptz | |

**locked_at**: enforced at API layer, not DB constraint, because auditors occasionally request corrections post-lock (which requires admin override + mandatory reason).

---

### `edit_logs`
Append-only. Every mutation to normalized_records produces a row here.

| column | type | notes |
|--------|------|-------|
| id | UUID PK | |
| normalized_record_id | FK → normalized_records | |
| edited_by | FK → users | |
| edited_at | timestamptz | |
| field_name | varchar | which field changed |
| old_value | text | serialized previous value |
| new_value | text | serialized new value |
| reason | text | required — analyst must state why |

**Why require a reason?** Auditors ask. "Changed 1200 to 120 on 14 March" is not sufficient. "Typo confirmed with facilities team via email 14 Mar" is.

---

### `users`

| column | type | notes |
|--------|------|-------|
| id | UUID PK | |
| tenant_id | FK → tenants | |
| email | varchar unique | |
| role | enum | ANALYST, ADMIN |
| created_at | timestamptz | |

---

## Scope 1/2/3 Mapping

| Source Type | Scope | GHG Protocol Category |
|-------------|-------|----------------------|
| SAP_FUEL | Scope 1 | Stationary combustion |
| SAP_PROCUREMENT | Scope 3 | Cat 1 — Purchased goods & services |
| UTILITY_ELECTRICITY | Scope 2 | Purchased electricity (location-based) |
| TRAVEL_FLIGHT | Scope 3 | Cat 6 — Business travel |
| TRAVEL_HOTEL | Scope 3 | Cat 6 — Business travel |
| TRAVEL_GROUND | Scope 3 | Cat 6 — Business travel |

---

## What This Model Does Not Handle (see TRADEOFFS.md)

- Market-based Scope 2 (RECs, PPAs)
- Versioned emission factor tables
- Multi-currency FX consolidation
- Supplier-level Scope 3 Cat 1 attribution
