# Breathe ESG — Ingestion Platform

A Django REST + React prototype for ingesting, normalizing, and reviewing ESG activity data from SAP, utility portals, and corporate travel platforms.

## Live Demo

- **Frontend**: [https://genuine-zabaione-809c05.netlify.app](https://genuine-zabaione-809c05.netlify.app)
- **API**: [https://breatheesg-production-3ecf.up.railway.app/api/](https://breatheesg-production-3ecf.up.railway.app/api/)

## Demo Login

- Email: analyst@demo.com
- Password: demo1234

## Sample Data Files

Located in `sample_data/`:

- `sap_fuel_mb51.csv` — SAP MB51 format, 12 fuel consumption records
- `utility_electricity.csv` — Green Button-style utility export, 10 billing records
- `concur_travel.csv` — Concur itinerary format, 17 travel segments

## Local Development

**Backend:**
```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

**Frontend:**
```bash
cd frontend
npm install
REACT_APP_API_URL=http://localhost:8000 npm start
```

## Key Documents

- [MODEL.md](docs/MODEL.md) — Data model design and rationale
- [DECISIONS.md](docs/DECISIONS.md) — Every ambiguity resolved
- [TRADEOFFS.md](docs/TRADEOFFS.md) — What was deliberately not built
- [SOURCES.md](docs/SOURCES.md) — Real-world source format research

## Architecture

```
backend/
  breathe/         Django project (settings, urls, wsgi)
  ingestion/       Core app
    models.py      Tenant, DataSource, IngestionBatch, RawRecord, NormalizedRecord, EditLog
    normalizers.py Per-source normalization logic (SAP, Utility, Travel)
    views.py       REST API endpoints
frontend/
  src/
    App.js         Single-page dashboard (upload, review, batches, stats)
sample_data/       Realistic sample CSVs for all three sources
docs/              MODEL.md, DECISIONS.md, TRADEOFFS.md, SOURCES.md
```

## Deployment

- **Frontend**: Netlify (auto-deploys from `frontend/` on push to main)
- **Backend**: Railway (auto-deploys from `backend/` on push to main)
- **Database**: PostgreSQL on Railway
