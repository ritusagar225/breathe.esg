# Tradeoffs — Breathe ESG Ingestion Platform

## 1. No real authentication or multi-tenant row isolation

**What I built**: Hardcoded demo credentials. All API endpoints return data for a single demo tenant. The data model has tenant_id on every table and users with role-based access, but the enforcement isn't wired up.

**What production requires**: JWT or session auth, per-request tenant resolution (subdomain or header), row-level security so tenant A cannot query tenant B's records under any circumstances, and role-based endpoint guards (analysts can approve, not delete; admins can unlock, not approve on behalf of).

**Why I skipped it**: Auth plumbing is ~6 hours of work that doesn't demonstrate the core problem — ingesting, normalizing, and reviewing ESG data. The architecture supports it. I chose to show the data model and workflow clearly rather than hide them behind auth scaffolding.

**Risk of skipping**: In production, skipping this would be a critical security vulnerability. Data leakage between tenants is not a recoverable PR event for an ESG platform whose clients are sharing pre-audit emissions data.

---

## 2. No emission factor versioning

**What I built**: A string field (`emission_factor_source`) recording which factor source was used (e.g. "DEFRA 2023 v1.0"). Emission factors are hardcoded constants in the normalization layer.

**What production requires**: A versioned emission factor table with effective date ranges, factor values by activity category and geography, and the ability to recompute historical records when a new factor version is released (common — DEFRA releases updates annually, IEA grid factors update quarterly). Recomputation needs to be auditable: "this record was recalculated on 15 Jan 2025 using DEFRA 2024 v2.1, previous value was X."

**Why I skipped it**: The factor table schema alone — covering Scope 1 fuel types by country, Scope 2 grid factors by country/region/year, Scope 3 travel factors by mode and radiative forcing assumption — is a significant data engineering project. It's important but it's a data problem, not an application architecture problem. The current string field preserves traceability without building the full factor management system.

**Risk of skipping**: If a client asks "what emission factor did you use for DE grid electricity in Q2 2023" and the answer is "it's hardcoded somewhere in the Python," that's not audit-defensible.

---

## 3. No async ingestion pipeline

**What I built**: Synchronous file processing — the API endpoint parses and normalizes the uploaded file in the request/response cycle and returns results immediately.

**What production requires**: For files with 10,000+ rows (realistic for a full-year SAP export from a large plant), synchronous processing will time out. Production needs a task queue (Celery + Redis, or Django Q), with the upload endpoint returning a batch ID immediately and the client polling for completion status. Large files also need chunked upload (multipart) for reliability.

**Why I skipped it**: Async task infrastructure (Celery worker, Redis broker, result backend, polling endpoint) is ~4 hours of setup on top of the core app. For a prototype with realistic sample data (50-200 rows), synchronous processing works fine and lets the demo flow without job polling UI.

**Risk of skipping**: A real client uploading an annual SAP export (potentially 50,000+ line items) would get a 30-second timeout and no feedback. This would need to be the first infrastructure addition before any real client onboarding.
