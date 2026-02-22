# Phase 1 Implementation Plan (Map-First, Local-First)

## 1) Purpose

This document captures the decisions made in this session and provides a
self-contained implementation plan for **Phase 1**.

Phase 1 goal:
- Deliver an end-to-end app where a user picks a point on a map (lat/lon)
- Backend returns cloud and lightning metrics for that point
- Frontend visualizes metrics in day/month/year views
- Data is fetched and processed locally first

This plan is detailed for junior engineers and can be implemented directly.

---

## 2) Decisions Made (Session Record)

1. **No GRIB processing in v1**.
2. Historical scope is:
   - **2021–2025 full years**
   - **2026 YTD (current year partial)**
3. Work **local-first**:
   - Download raw data locally
   - Explore and aggregate locally
   - No cloud upload required in Phase 1
4. Use **H3 resolution 7** for lightning spatial indexing.
5. For geocoding/address UX:
   - **Phase 1 uses map point selection only** (Option A)
   - Address lookup is deferred to future work (Option B)
6. Firestore is not the primary store for large raw geodata in Phase 1.
7. No Parquet requirement for this assignment in v1 (raw JSON/CSV + Python is fine).

---

## 3) Why Option A (Map-first)

- Fastest path to working product
- Avoids complex address indexing early
- Matches SMHI MESAN demo pattern (`demo_get_point`) where user selects a map point
- Gives exact lat/lon needed for metrics pipeline immediately

---

## 4) Scope

### In scope (Phase 1)
- Download and store raw weather datasets locally
- Build local aggregation pipeline for cloud + lightning
- Expose backend API for point metrics
- Build frontend map click interaction + charts (day/month/year)

### Out of scope (Phase 1)
- Address search/autocomplete
- Full cloud deployment of data artifacts
- Forecast ML model
- CI/CD for data refresh jobs

---

## 5) Data Sources (Confirmed)

## 5.1 Lightning archive (SMHI)
- Base: `https://opendata-download-lightning.smhi.se/api/version/latest.json`
- Drill-down:
  - `/year/{year}.json`
  - `/year/{year}/month/{month}.json`
  - `/year/{year}/month/{month}/day/{day}/data.csv`

Notes:
- Years available include 2012–2026; we filter to 2021+.
- CSV is smaller than JSON and preferred for local processing.

## 5.2 Cloud cover observations (SMHI metobs)
- Parameter 16 = **Total molnmängd** (total cloud amount, percent)
- Parameter endpoint:
  - `https://opendata-download-metobs.smhi.se/api/version/latest/parameter/16.json`
- Station data path:
  - `/parameter/16/station/{stationId}/period/corrected-archive/data.csv`

Notes:
- `corrected-archive` gives long historical data (CSV only).
- We extract rows from 2021 onward.

---

## 6) High-Level Architecture (Phase 1)

1. **Ingestion scripts** (Python, local)
   - Fetch raw lightning daily CSV files
   - Fetch cloud station list + station historical CSV files

2. **Aggregation scripts** (Python, local)
   - Lightning -> H3 r7 day/month/year aggregates
   - Cloud -> station day/month/year aggregates

3. **Backend API (FastAPI)**
   - Input: lat/lon, selected year/month
   - Resolve nearest cloud station
   - Resolve H3 cell
   - Return chart-ready payloads

4. **Frontend (React)**
   - Leaflet map click to choose point
   - Marker + selected coordinates
   - Day / month / year chart tabs

---

## 7) File/Folder Structure

Create and use this structure:

```text
backend/
  data/
    raw/
      lightning/
        2021/...
        ...
      cloud/
        parameter-16-stations.json
        station/{station_id}.csv
    processed/
      station_index.json
      lightning_h3_r7_daily.jsonl
      lightning_h3_r7_monthly.json
      lightning_h3_r7_yearly.json
      cloud_station_daily.jsonl
      cloud_station_monthly.json
      cloud_station_yearly.json
  scripts/
    fetch_lightning_raw.py
    fetch_cloud_raw.py
    build_lightning_aggregates.py
    build_cloud_aggregates.py
    build_station_index.py
    run_pipeline.py
```

Add `backend/data/raw` and large processed artifacts to `.gitignore`.

---

## 8) Dependencies

## Backend dependencies to add
- `requests`
- `h3`

Optional but useful:
- `python-dateutil`

## Frontend dependencies to add
- `leaflet`
- `react-leaflet`
- `recharts`

---

## 9) Step-by-Step Implementation

## Step 0: Baseline setup

From repo root:

```bash
cd backend
uv sync --dev

cd ../frontend
npm ci
```

---

## Step 1: Raw data download scripts

## 1A. `fetch_lightning_raw.py`

Behavior:
- Iterate years 2021..2026
- For each year -> months -> days via SMHI hierarchy
- Download daily `data.csv` files
- Save as:
  - `backend/data/raw/lightning/{year}/{month}/{day}.csv`

Implementation rules:
- Skip download if file already exists
- Retry 3 times with backoff for transient errors
- Write a small `manifest.json` with counts and timestamps

## 1B. `fetch_cloud_raw.py`

Behavior:
- Download stations list from parameter 16 endpoint
- Save stations metadata JSON
- For each station, fetch `corrected-archive/data.csv`
- Save:
  - `backend/data/raw/cloud/station/{station_id}.csv`

Implementation rules:
- Skip station file if already exists
- Retry on network errors
- Record failed station IDs in a report file

---

## Step 2: Build station index

## `build_station_index.py`

Input:
- `parameter-16-stations.json`

Output:
- `backend/data/processed/station_index.json`

Each station entry:

```json
{
  "station_id": "188790",
  "name": "Abisko Aut",
  "lat": 68.3538,
  "lon": 18.8164,
  "active": true,
  "from_ts": 536457600000,
  "to_ts": 1771743600000
}
```

---

## Step 3: Lightning aggregates (H3 r7)

## `build_lightning_aggregates.py`

For each lightning CSV row:
- Read `year/month/day/hours/minutes/seconds/lat/lon`
- Convert `(lat,lon)` -> `h3_r7`
- Aggregate:
  - daily strike count per cell
  - monthly strike count per cell
  - yearly strike count per cell
  - monthly `days_with_strike` per cell

Outputs:
- `lightning_h3_r7_daily.jsonl`
- `lightning_h3_r7_monthly.json`
- `lightning_h3_r7_yearly.json`

Daily record example:

```json
{"h3":"871f...","date":"2025-07-15","strike_count":123}
```

Monthly record example:

```json
{
  "h3": "871f...",
  "year": 2025,
  "month": 7,
  "strike_count": 3450,
  "days_with_strike": 14,
  "days_in_month": 31,
  "strike_probability": 0.4516
}
```

---

## Step 4: Cloud aggregates (station-based)

## `build_cloud_aggregates.py`

Parse each station CSV:
- Find header row starting with `Datum;Tid (UTC);...`
- Parse rows with numeric cloud value
- Keep rows with quality `G` or `Y`
- Filter date >= 2021-01-01

Aggregate per station:
- daily mean cloud %
- monthly mean cloud %
- yearly mean cloud %

Outputs:
- `cloud_station_daily.jsonl`
- `cloud_station_monthly.json`
- `cloud_station_yearly.json`

Monthly record example:

```json
{
  "station_id": "188790",
  "year": 2025,
  "month": 7,
  "cloud_mean_pct": 61.2,
  "n_samples": 744
}
```

---

## Step 5: Orchestration script

## `run_pipeline.py`

Runs in order:
1. fetch_lightning_raw
2. fetch_cloud_raw
3. build_station_index
4. build_lightning_aggregates
5. build_cloud_aggregates

Command:

```bash
cd backend
uv run python scripts/run_pipeline.py
```

---

## Step 6: Backend metrics API

Create endpoint:
- `POST /api/metrics/point`

Request:

```json
{
  "lat": 59.3293,
  "lon": 18.0686,
  "year": 2025,
  "month": 7
}
```

Processing:
1. Validate point in Sweden bounds
2. Compute `h3_r7` for point
3. Find nearest cloud station (Haversine against `station_index.json`)
4. Read precomputed aggregates and return:
   - daily view (selected year+month)
   - monthly view (selected year)
   - yearly view (2021..2026)

Response:

```json
{
  "point": {"lat": 59.3293, "lon": 18.0686, "h3_r7": "871f..."},
  "cloud_station": {"station_id": "98210", "name": "Stockholm A", "distance_km": 3.2},
  "daily": {
    "days": [
      {"date": "2025-07-01", "cloud_mean_pct": 62.1, "lightning_count": 0},
      {"date": "2025-07-02", "cloud_mean_pct": 70.5, "lightning_count": 4}
    ]
  },
  "monthly": {
    "months": [
      {"month": 1, "cloud_mean_pct": 84.3, "lightning_probability": 0.00, "lightning_count": 0}
    ]
  },
  "yearly": {
    "years": [
      {"year": 2021, "cloud_mean_pct": 69.5, "lightning_probability": 0.12, "lightning_count": 842}
    ]
  }
}
```

---

## Step 7: Frontend map + charts

1. Add map component using React Leaflet
2. Center map on Sweden
3. On click:
   - place marker
   - show selected lat/lon
   - call `POST /api/metrics/point`
4. Add tabs: `Day`, `Month`, `Year`
5. Render charts with Recharts:
   - Day: line/bar by date
   - Month: 12-month bars/lines
   - Year: multi-year summary

UI controls:
- Year selector (2021..2026)
- Month selector (for day view)

---

## Step 8: Validation and test checklist

## Backend tests
- Unit test Haversine nearest-station function
- Unit test H3 conversion function
- Unit test cloud CSV parser with sample malformed rows
- Unit test lightning CSV parser
- API test for `/api/metrics/point`

## Frontend tests/manual checks
- Clicking map updates marker and coordinate label
- API errors are shown to user
- Day/month/year charts switch correctly
- 2026 future months with no data handled gracefully

---

## 10) Performance & Cost Notes

- Phase 1 is local-first, so cloud costs are minimal.
- Keep aggregate files local and loaded once in memory at API startup for fast reads.
- Do not commit raw files to git.

---

## 11) Definition of Done (Phase 1)

Phase 1 is done when all are true:
1. Pipeline downloads raw data for 2021..2026 YTD.
2. Aggregates are generated for lightning (H3 r7) and cloud (station-based).
3. Backend point endpoint returns chart-ready day/month/year payload.
4. Frontend supports map click and displays all three visualizations.
5. Basic tests pass locally.

---

## 12) Future Work (#future-work) — Option B (Address Support)

Goal: add address input without relying on live API for every request.

### B.1 Strategy
- Build local address index offline (Sweden-focused)
- Store in **SQLite or DuckDB file** as read-only lookup DB
- Package DB file inside Docker image
- Runtime flow:
  1. query local address DB
  2. if miss/low-confidence, call external geocoder fallback
  3. cache fallback result

### B.2 Why this instead of Firestore for full address corpus
- Firestore document/index limits and write/index costs make huge address corpora suboptimal.
- Read-only local DB in container is very fast for exact/prefix matches.

### B.3 Future implementation tasks
1. Define address normalization rules
2. Build offline extractor/indexer job
3. Add `/api/geocode/search` endpoint
4. Add frontend address search + candidate selection
5. Add fallback provider and cache policy
6. Add update/rebuild process for address DB snapshot

---

## 13) References

- SMHI lightning archive docs/demo and endpoints
- SMHI metobs API (parameter 16 total cloud amount)
- SMHI MESAN demo_get_point (map-click interaction pattern)
- Cloud Run filesystem behavior (ephemeral in-memory writable FS)
- Firestore quotas and index limits
