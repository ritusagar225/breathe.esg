# Decisions — Breathe ESG Ingestion Platform

## SAP Source Format

**Decision**: MB51 flat-file CSV export (material document list), not IDoc or OData.

**Why**: IDoc is the right answer for a production SAP integration — it's event-driven, structured, and handles change documents natively. But IDoc requires an ALE/EDI setup that a client's Basis team has to configure, and that takes weeks. OData (via SAP Gateway) is cleaner to consume but requires the client to have Gateway installed and exposed, which many older S/4 systems don't. MB51 is what a sustainability analyst can actually get from SAP today by running a standard transaction and pressing "Export to spreadsheet." It's the realistic path for an onboarding client in the short term.

**What I handle**: Plant code, material number, movement type (201/261 for fuel consumption), quantity, unit of measure, posting date. I map movement types 201 and 261 as fuel consumption events. All others are ignored.

**What I ignore**: Goods receipts, reversals (movement type 102/262), inter-plant transfers. In production, reversals would need to be matched and netted.

**German headers**: SAP exports in the system language. I handle both German (`Werk`, `Menge`, `Buchungsdatum`) and English (`Plant`, `Quantity`, `Posting Date`) column names via a normalization map.

**Units**: SAP uses internal UoM codes (L for liters, KG for kilograms, M3 for cubic meters). I maintain a lookup table mapping these to canonical units.

**What I'd ask the PM**: "Which plants are in scope? Do you have a plant-to-country mapping? What movement types does the client use for fuel consumption — 201 or 261 or both?"

---

## Utility Data Format

**Decision**: Portal CSV export, not PDF or API.

**Why**: Most utility portal APIs (Green Button, Xcel, PG&E) exist but require OAuth flows, utility account linking, and often a 2-3 week approval process to access programmatic data. PDF parsing is brittle — utility bill layouts vary by provider, by year, sometimes by tariff class. CSV export from a portal is what a facilities manager can produce in 5 minutes and email to us. It's the realistic day-1 ingestion path.

**Format I handle**: Green Button-style CSV with columns: account_number, service_address, billing_period_start, billing_period_end, meter_id, usage_kwh, demand_kw, rate_schedule, total_charges, currency. This format is used by ~60% of US utilities and has EU equivalents.

**Billing period misalignment**: Utility bills don't align with calendar months (a bill might run Feb 17 – Mar 18). I store period_start and period_end on NormalizedRecord exactly as given, and prorate to calendar months only at reporting time, not at ingestion time. Ingesting prorated data would destroy auditability.

**What I'd ask the PM**: "Is this US or EU client? Which utility providers? Are they on time-of-use tariffs where we'd want interval data rather than monthly totals?"

---

## Travel Data Format

**Decision**: CSV export from Concur, not API.

**Why**: Concur's API requires OAuth 2.0 setup, client credentials provisioned by the company's Concur admin, and IP allowlisting in some corporate configurations. A CSV expense report export is available to any user with reporting access. For onboarding, CSV is the practical answer. Production integration would use the Concur Travel Itinerary API.

**Columns I handle**: traveler_id, trip_id, segment_type (AIR/HOTEL/CAR/RAIL), departure_date, origin, destination, distance_km, distance_miles, duration_nights, vendor, amount, currency.

**Distance gap**: Concur doesn't always provide distance. For flights, I compute great-circle distance from IATA airport codes using the Haversine formula with a lookup table of ~500 major airports. For ground transport, if distance is missing, I flag the record as requiring manual review rather than imputing.

**Emission factors per segment**: Flights use a radiative forcing multiplier (RF factor of 1.9x CO2-only) per DEFRA 2023. Hotels use a per-night per-city factor. Ground uses a per-km factor by vehicle class.

**What I'd ask the PM**: "Does the client use Concur or a different platform? Do they capture rail travel? Do they have a preferred emission factor methodology — DEFRA, GHG Protocol, or their auditor's own?"

---

## Review Workflow

**Decision**: Simple three-state status (PENDING → APPROVED / REJECTED), not a multi-stage workflow.

**Why**: The assignment asks for analysts to review and sign off before audit. A multi-stage workflow (analyst review → manager approval → auditor lock) is the right production answer but adds significant UI and API complexity. For a prototype, one approval step demonstrates the concept. The data model supports adding stages without schema changes (review_status is an enum, extendable).

---

## Deployment

**Decision**: Railway with PostgreSQL, not Render or Fly.

**Why**: Railway gives you a Postgres database provisioned in one click, environment variables auto-injected, and a public URL in ~3 minutes. Render has a 15-minute spin-down on free tier which breaks demos. Fly requires CLI setup and Dockerfile tuning. For a time-constrained submission, Railway is the fastest path to a live URL.

---

## Authentication

**Decision**: Hardcoded demo credentials, no real auth.

**Why**: JWT auth, session management, and multi-tenant row-level security are production requirements but would consume 4+ hours of implementation time. The data model has users and tenant_id foreign keys on every table — the architecture supports real auth. For the prototype, a demo login with hardcoded credentials demonstrates the UX without the implementation overhead.

What I'd build next: Django's built-in auth + SimpleJWT + per-tenant middleware that injects tenant_id on every queryset.
