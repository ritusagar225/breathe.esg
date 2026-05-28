"""
Normalizers for each data source type.
Each normalizer takes a dict (raw CSV row) and returns a dict of normalized fields,
or raises ValueError with a descriptive message.
"""
import re
from datetime import date, datetime
from decimal import Decimal

# SAP UoM code → canonical unit
SAP_UOM_MAP = {
    'L': 'LITERS', 'LT': 'LITERS', 'GAL': 'LITERS',  # GAL converted below
    'KG': 'KG', 'G': 'KG',
    'M3': 'LITERS',  # cubic meters → liters (* 1000)
    'KWH': 'KWH', 'MWH': 'KWH',
    'GJ': 'GJ', 'MJ': 'GJ',
}

SAP_COLUMN_MAP = {
    # German → English
    'Werk': 'Plant', 'Menge': 'Quantity', 'Bew.Art': 'Movement Type',
    'Buchungsdatum': 'Posting Date', 'Material': 'Material',
    'Materialbeschreibung': 'Material Description', 'Mengeneinheit': 'Unit',
}

# DEFRA 2023 emission factors (kg CO2e per unit)
EMISSION_FACTORS = {
    'DIESEL_LITERS': Decimal('2.6808'),
    'NATGAS_KWH': Decimal('0.18293'),
    'ELECTRICITY_KWH_UK': Decimal('0.20707'),
    'FLIGHT_KM_ECONOMY': Decimal('0.15573'),   # with RF 1.9x
    'FLIGHT_KM_BUSINESS': Decimal('0.42870'),
    'HOTEL_NIGHT_UK': Decimal('20.8'),
    'CAR_KM': Decimal('0.16844'),
}

# IATA great-circle distances (km) for common routes
AIRPORT_DISTANCES = {
    frozenset(['LHR', 'EDI']): 534,
    frozenset(['LHR', 'FRA']): 651,
    frozenset(['LHR', 'AMS']): 370,
    frozenset(['LHR', 'JFK']): 5539,
    frozenset(['LHR', 'DXB']): 5484,
    frozenset(['DXB', 'SIN']): 5841,
    frozenset(['LHR', 'CDG']): 341,
    frozenset(['FRA', 'JFK']): 6197,
    frozenset(['MUC', 'LHR']): 920,
}


def _parse_date(s):
    for fmt in ('%d.%m.%Y', '%m/%d/%Y', '%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(str(s).strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s!r}")


def normalize_sap_row(row):
    """Normalize a SAP MB51 export row."""
    # Remap German headers
    row = {SAP_COLUMN_MAP.get(k, k): v for k, v in row.items()}

    plant = str(row.get('Plant', '')).strip()
    material = str(row.get('Material Description', row.get('Material', ''))).strip()
    movement_type = str(row.get('Movement Type', '')).strip()
    qty_raw = str(row.get('Quantity', '')).replace(',', '.').strip()
    uom = str(row.get('Unit', '')).strip().upper()
    date_raw = str(row.get('Posting Date', '')).strip()

    if not plant:
        raise ValueError("Missing Plant")
    if movement_type not in ('201', '261', 'Z201', 'Z261'):
        raise ValueError(f"Movement type {movement_type!r} not a fuel consumption event")

    try:
        qty = Decimal(qty_raw)
    except Exception:
        raise ValueError(f"Cannot parse quantity: {qty_raw!r}")
    if qty <= 0:
        raise ValueError(f"Non-positive quantity: {qty}")

    canonical_unit = SAP_UOM_MAP.get(uom)
    if not canonical_unit:
        raise ValueError(f"Unknown SAP UoM: {uom!r}")

    # Unit conversions
    if uom == 'GAL':
        qty = qty * Decimal('3.78541')
    elif uom == 'M3':
        qty = qty * Decimal('1000')
    elif uom == 'G':
        qty = qty / Decimal('1000')
    elif uom == 'MWH':
        qty = qty * Decimal('1000')
        canonical_unit = 'KWH'
    elif uom == 'MJ':
        qty = qty / Decimal('1000')
        canonical_unit = 'GJ'

    posting_date = _parse_date(date_raw)

    # Emission factor
    co2e = None
    ef_source = ''
    mat_upper = material.upper()
    if 'DIESEL' in mat_upper or 'GASOIL' in mat_upper:
        co2e = qty * EMISSION_FACTORS['DIESEL_LITERS']
        ef_source = 'DEFRA 2023 - Diesel'
    elif 'GAS' in mat_upper or 'LNG' in mat_upper:
        co2e = qty * EMISSION_FACTORS['NATGAS_KWH']
        ef_source = 'DEFRA 2023 - Natural Gas'

    flags = {}
    if co2e is None:
        flags['no_emission_factor'] = True

    return {
        'activity_date': posting_date,
        'period_start': posting_date,
        'period_end': posting_date,
        'quantity': qty,
        'unit': canonical_unit,
        'quantity_co2e_kg': co2e,
        'emission_factor_source': ef_source,
        'description': f"{material} — Movement {movement_type}",
        'location': plant,
        'flags': flags,
    }


def normalize_utility_row(row):
    """Normalize a utility portal CSV row (Green Button style)."""
    meter_id = str(row.get('meter_id', row.get('Meter ID', ''))).strip()
    usage_raw = str(row.get('usage_kwh', row.get('Usage (kWh)', ''))).replace(',', '').strip()
    start_raw = str(row.get('billing_start', row.get('Billing Start', ''))).strip()
    end_raw = str(row.get('billing_end', row.get('Billing End', ''))).strip()
    address = str(row.get('service_address', row.get('Service Address', ''))).strip()
    charges_raw = str(row.get('total_charges_gbp', row.get('total_charges', ''))).replace(',', '').strip()

    if not meter_id:
        raise ValueError("Missing meter_id")
    try:
        usage = Decimal(usage_raw)
    except Exception:
        raise ValueError(f"Cannot parse usage_kwh: {usage_raw!r}")
    if usage < 0:
        raise ValueError("Negative usage — possible credit note, review manually")

    period_start = _parse_date(start_raw)
    period_end = _parse_date(end_raw)
    if period_end <= period_start:
        raise ValueError("period_end must be after period_start")

    co2e = usage * EMISSION_FACTORS['ELECTRICITY_KWH_UK']
    charges = None
    try:
        charges = Decimal(charges_raw) if charges_raw else None
    except Exception:
        pass

    flags = {}
    if (period_end - period_start).days > 45:
        flags['long_billing_period'] = True

    return {
        'activity_date': period_start,
        'period_start': period_start,
        'period_end': period_end,
        'quantity': usage,
        'unit': 'KWH',
        'quantity_co2e_kg': co2e,
        'emission_factor_source': 'DEFRA 2023 - UK Grid (location-based)',
        'description': f"Electricity — Meter {meter_id}",
        'location': address or meter_id,
        'currency': 'GBP',
        'amount_local': charges,
        'flags': flags,
    }


def normalize_travel_row(row):
    """Normalize a Concur travel itinerary row."""
    segment = str(row.get('segment_type', row.get('Segment Type', ''))).strip().upper()
    dep_raw = str(row.get('departure_date', row.get('Departure Date', ''))).strip()
    origin = str(row.get('origin', row.get('Origin', ''))).strip().upper()
    dest = str(row.get('destination', row.get('Destination', ''))).strip().upper()
    cabin = str(row.get('cabin_class', row.get('Cabin Class', 'ECONOMY'))).strip().upper()
    nights_raw = str(row.get('duration_nights', row.get('Duration Nights', ''))).strip()
    dist_raw = str(row.get('distance_km', row.get('Distance (km)', ''))).strip()
    traveler = str(row.get('traveler_id', row.get('Traveler', ''))).strip()
    amount_raw = str(row.get('amount', row.get('Amount', ''))).replace(',', '').strip()
    currency = str(row.get('currency', row.get('Currency', 'GBP'))).strip().upper()

    dep_date = _parse_date(dep_raw)
    flags = {}

    if segment in ('AIR', 'FLIGHT'):
        # Try explicit distance first
        if dist_raw:
            try:
                dist = Decimal(dist_raw)
            except Exception:
                dist = None
        else:
            dist = None

        if dist is None:
            # Compute from airport codes
            pair = frozenset([origin, dest])
            dist_int = AIRPORT_DISTANCES.get(pair)
            if dist_int:
                dist = Decimal(str(dist_int))
                flags['distance_computed'] = True
            else:
                raise ValueError(f"No distance for {origin}-{dest} and not in lookup table")

        ef_key = 'FLIGHT_KM_BUSINESS' if 'BUSINESS' in cabin or 'FIRST' in cabin else 'FLIGHT_KM_ECONOMY'
        co2e = dist * EMISSION_FACTORS[ef_key]
        unit = 'KM'
        qty = dist
        desc = f"Flight {origin}→{dest} ({cabin.title()})"
        loc = f"{origin}-{dest}"
        period_end = dep_date

    elif segment in ('HOTEL', 'ACCOMMODATION'):
        try:
            nights = Decimal(nights_raw)
        except Exception:
            raise ValueError(f"Cannot parse duration_nights: {nights_raw!r}")
        co2e = nights * EMISSION_FACTORS['HOTEL_NIGHT_UK']
        unit = 'NIGHTS'
        qty = nights
        desc = f"Hotel stay — {dest or origin}"
        loc = dest or origin
        period_end = date.fromordinal(dep_date.toordinal() + int(nights))

    elif segment in ('CAR', 'GROUND', 'RAIL'):
        if dist_raw:
            try:
                dist = Decimal(dist_raw)
            except Exception:
                dist = None
                flags['distance_missing'] = True
        else:
            dist = None
            flags['distance_missing'] = True

        if dist is None:
            # Flag for manual review rather than impute
            co2e = None
            flags['needs_manual_review'] = True
            unit = 'KM'
            qty = Decimal('0')
        else:
            co2e = dist * EMISSION_FACTORS['CAR_KM']
            unit = 'KM'
            qty = dist
        desc = f"Ground transport — {origin} to {dest}"
        loc = f"{origin}-{dest}"
        period_end = dep_date

    else:
        raise ValueError(f"Unknown segment type: {segment!r}")

    amount = None
    try:
        amount = Decimal(amount_raw) if amount_raw else None
    except Exception:
        pass

    return {
        'activity_date': dep_date,
        'period_start': dep_date,
        'period_end': period_end,
        'quantity': qty,
        'unit': unit,
        'quantity_co2e_kg': co2e,
        'emission_factor_source': 'DEFRA 2023',
        'description': desc,
        'location': loc,
        'currency': currency,
        'amount_local': amount,
        'flags': flags,
    }


NORMALIZER_MAP = {
    'SAP_FUEL': normalize_sap_row,
    'SAP_PROCUREMENT': normalize_sap_row,
    'UTILITY_ELECTRICITY': normalize_utility_row,
    'TRAVEL_FLIGHT': normalize_travel_row,
    'TRAVEL_HOTEL': normalize_travel_row,
    'TRAVEL_GROUND': normalize_travel_row,
}
