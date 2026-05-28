# Sources — Breathe ESG Ingestion Platform

## SAP — Fuel & Procurement

**What I researched**: SAP MB51 (Material Document List), MB52 (Warehouse Stocks), ME2M (Purchase Orders by Material). SAP exports are available as ALV grid exports to CSV/XLS, IDoc flat files (for EDI integrations), OData via SAP Gateway, and BAPI calls for programmatic access.

**What I learned**: 
- SAP column headers vary by system language configuration — German headers (`Werk`, `Menge`, `Bew.Art`) are common in European deployments
- Units of measure use SAP internal codes: `L` = liters, `KG` = kilograms, `M3` = cubic meters, `ST` = pieces
- Date format is typically DD.MM.YYYY in European systems, MM/DD/YYYY in US
- Movement types encode the nature of the transaction: 201 = goods issue to cost center (fuel consumption), 261 = goods issue to production order, 101 = goods receipt
- Plant codes are arbitrary 4-character codes meaningful only with a client's plant master lookup

**What my sample data looks like**: MB51 export with columns: Posting Date, Plant, Material, Material Description, Movement Type, Quantity, Unit, Storage Location, Cost Center. Plants are DE01 (Frankfurt), DE02 (Munich), UK01 (London). Materials include DIESEL, NATGAS, HFO. Movement types are 201 and 261.

**Why it looks this way**: A manufacturing company with 2-3 European plants using SAP ECC 6.0 is the modal enterprise client for an ESG platform. Fuel consumption via goods issues to cost centers is the standard SAP pattern for tracking stationary combustion.

**What would break in production**:
- Client plants using custom movement types (e.g. Z201) not in our mapping table
- Materials with non-obvious names (internal codes like "MAT-00441" with no description)
- Negative quantities from reversal documents that need to be matched and netted
- Fiscal year variants — some SAP clients have fiscal years that don't start in January, so "period 1" ≠ January
- SAP S/4HANA vs ECC differences in field names and available exports

---

## Utility Data — Electricity

**What I researched**: Green Button (NAESB REQ.21 standard), used by ~60% of US utilities including PG&E, ConEd, Xcel. EU equivalent is the ESPI standard. Typical portal exports include: account number, service address, billing period, usage (kWh), demand (kW), rate schedule, total charges. Some utilities offer 15-minute interval data; most offer monthly billing summaries.

**What I learned**:
- Billing periods do not align with calendar months — a bill might run Feb 17 to Mar 18
- Large commercial accounts often have demand charges ($/kW) separate from energy charges ($/kWh) — the kWh figure is what matters for emissions, not total spend
- Some tariffs include power factor correction, reactive power charges — these are cost items not energy items and should be stripped
- Meter IDs are the stable identifier — account numbers can change when a facility is re-metered
- Green Button CSV has a specific column order that differs from portal-to-portal "download to Excel" exports

**What my sample data looks like**: 12 months of monthly billing data for two UK meters (industrial electricity). Columns: account_number, meter_id, service_address, billing_start, billing_end, usage_kwh, peak_demand_kw, rate_schedule, total_charges_gbp. Usage ranges 8,000–45,000 kWh/month reflecting seasonal variation.

**Why it looks this way**: UK industrial electricity accounts are realistic for a mid-size manufacturing client. Seasonal variation (higher in winter for heating/lighting) is realistic and tests whether the normalization handles non-uniform monthly patterns.

**What would break in production**:
- Multi-fuel utility accounts (gas + electricity on same bill) requiring split parsing
- Time-of-use tariffs where a single bill has multiple usage bands (peak/off-peak/shoulder) that need to be summed
- Estimated readings flagged by the utility (meter not accessible) — these need a flag in normalized_records
- Solar generation offset — some accounts have on-site generation that nets against consumption on the bill; the gross consumption figure matters for Scope 2 reporting, not the net
- PDF bills from utilities that don't offer CSV export

---

## Corporate Travel — Flights, Hotels, Ground

**What I researched**: Concur Travel (SAP Concur) expense and itinerary export, Navan (formerly TripActions) data export, American Express GBT reporting. Concur offers a standard CSV expense report export and a separate itinerary export. The itinerary export contains segment-level data; the expense report contains cost-level data. For emissions purposes, itinerary data is better — it has origin/destination and sometimes distance.

**What I learned**:
- Concur itinerary exports include: trip ID, traveler, segment type (Air/Hotel/Car/Rail), dates, origin, destination, vendor, amount
- Distance is not always provided for flights — you get IATA airport codes (e.g. LHR, FRA) and must compute distance yourself
- Hotel stays give you city and hotel name but not a meaningful distance — emissions are calculated per-night with a city-tier factor
- Car rental gives you pickup/dropoff location and duration but not distance — requires imputation from rental duration × assumed daily mileage
- Radiative forcing: DEFRA 2023 recommends a multiplier of 1.9x on CO2 for aviation's high-altitude non-CO2 effects. This is contested and some auditors want CO2-only. The choice should be documented.
- Navan and Concur use different segment type codes — Concur uses AIR/HOTEL/CAR, Navan uses flight/accommodation/ground_transport

**What my sample data looks like**: 30 trip records for 8 travelers over Q1 2024. Mix of domestic UK flights (LHR-EDI), European flights (LHR-FRA, LHR-AMS), long-haul (LHR-JFK), hotel stays in London/Frankfurt/New York, and UK car rentals. Business class and economy class coded separately (business class has a higher emission factor per the DEFRA methodology).

**Why it looks this way**: A UK-headquartered company with European operations and occasional US travel is realistic. Business class on long-haul routes is common for senior staff and materially affects emissions (business class factor is ~3x economy per DEFRA due to seat pitch/space allocation).

**What would break in production**:
- Airport codes not in our lookup table (regional airports, private terminals)
- Rail travel — Eurostar, domestic rail — which has different emission factors and no IATA codes
- Ride-hailing (Uber, Lyft) booked outside corporate travel — often not in Concur at all
- Mileage claims (employees driving personal vehicles) — these appear as expense line items, not travel segments, and need a separate parsing path
- Multi-leg itineraries where a London–Singapore trip goes LHR-DXB-SIN — two segments, one trip, needs to be attributed to one business purpose
