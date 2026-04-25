# TerraScan (NGGSIC 2026)

TerraScan is a Streamlit-based geospatial analysis app for comparing satellite-derived environmental indicators across time windows.  
It uses Google Earth Engine (GEE) to process Landsat and Sentinel data, then renders interactive split-map visualization and index legends in a single dashboard.

## What this repository contains

This repo currently has two Streamlit app entry points:

1. `app.py` (root): Main, feature-rich app with landing page, module switching, split-map comparison, and index calculations.
2. `TerraScan-WebApp/app.py`: Minimal scaffold/prototype that demonstrates basic GEE auth and rendering a sample DEM layer.

Use the root `app.py` as the primary application.

## Core features (root `app.py`)

- Single-page app style flow:
  - Landing page
  - Dashboard view
- Sidebar configuration:
  - Basemap selection
  - Satellite source switch (`Landsat (30m)` or `Sentinel (10m)`)
  - Baseline year and comparison year
  - Layer selection (`True Color`, `NDVI`, `NDBI`, and `LST` for Landsat)
- Interactive map behavior:
  - Click to select a point
  - Automatic 10 km buffered region of interest (ROI)
  - Split-map comparison between baseline and comparison year
- Earth observation processing:
  - Cloud/shadow masking
  - Band scaling
  - NDVI and NDBI computation
  - LST computation for Landsat (manual mono-window style workflow)
- UX states:
  - Map lock/unlock mode after point selection
  - Inline info panels and legends
- Placeholder module:
  - `Machine Learning Land Classification` appears in the UI but is intentionally marked under development.

## Tech stack

- Python
- Streamlit
- Google Earth Engine Python API (`earthengine-api`)
- Leafmap + Folium integration
- `streamlit-folium`
- Plotly / Pandas (present for analytics extension)

## Project structure

```text
NGGSIC 2026/
|-- app.py                          # Main TerraScan app
|-- requirements.txt                # Main app dependencies
|-- TerraScan-WebApp/
|   |-- app.py                      # Prototype/minimal app
|   `-- requirements.txt            # Prototype dependencies
`-- terrascan/
    `-- frontend/
        `-- assets/
            |-- hero_graphic.png
            `-- dashboard_mockup.png
```

## Prerequisites

1. Python 3.10+ recommended
2. A Google Cloud project with Earth Engine enabled
3. Earth Engine account access for your Google user

## Setup and run (main app)

From repo root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run:

```powershell
streamlit run app.py
```

## Earth Engine authentication

The app initializes Earth Engine with this project id in code:

- `geomatic-competition-2026`

If local auth is not already available, the app attempts interactive auth (`ee.Authenticate()`).  
If authentication fails, Streamlit shows an error and stops execution.

If needed, you can also pre-authenticate manually:

```powershell
earthengine authenticate
```

## How the main analysis flow works

1. Choose satellite source and years in the sidebar.
2. Select an index/layer to display.
3. Click on the map to define center point.
4. App builds a 10 km buffered ROI around that point.
5. It computes annual median composites for baseline and comparison years.
6. It renders both years in a split map for direct visual comparison.
7. The right panel provides interpretation hints and module status text.

## Notes and current limitations

- `Machine Learning Land Classification` is UI-only for now (not implemented).
- Root app includes some imported libraries not fully used yet (`plotly`, `pandas`), likely for planned analytics enhancements.
- There are minor text encoding artifacts in parts of UI strings; functionality is unaffected, but cleaning these strings will improve presentation.
- The prototype app under `TerraScan-WebApp/` is separate and simpler; avoid confusing it with the full app.

## Quick troubleshooting

- Earth Engine auth errors:
  - Confirm account has Earth Engine access.
  - Confirm GCP project id exists and Earth Engine API is enabled.
  - Re-run `earthengine authenticate`.
- Blank/failed map layers:
  - Try different year ranges.
  - Switch data source (Landsat/Sentinel).
  - Re-select a map point and unlock/lock the map again.
- Dependency issues:
  - Recreate virtual env and reinstall from `requirements.txt`.

## Suggested next cleanup tasks

1. Promote one official app path (keep root app, archive prototype).
2. Normalize dependency files to a single `requirements.txt`.
3. Fix UI text encoding artifacts in `app.py`.
4. Implement the ML classification module or hide it until ready.

