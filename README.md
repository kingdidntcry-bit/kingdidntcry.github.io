# ?? TerraScan: Geospatial Intelligence for Heritage & Conservation

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge.svg)](https://terrascan.streamlit.app/)
[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live-green)](https://kingdidntcry-bit.github.io/)
[![Google Earth Engine](https://img.shields.io/badge/Google%20Earth%20Engine-Active-blue)](https://earthengine.google.com/)

**TerraScan** is a professional-grade geospatial dashboard designed for environmental analysts and UNESCO heritage site monitoring. Powered by **Google Earth Engine**, it provides real-time satellite imagery processing for change detection, vegetation health monitoring, and historical transformations.

---

## ?? Access the Platform
*   **Live App (Streamlit Cloud):** [terrascan.streamlit.app](https://terrascan.streamlit.app/)
*   **Project Homepage:** [kingdidntcry-bit.github.io](https://kingdidntcry-bit.github.io/)

---

## ? Key Features

### ?? Multi-Spectral Indices Analysis
*   **NDVI (Vegetation):** Monitor forest density and agricultural health.
*   **LST (Temperature):** Analyze urban heat islands and surface temperature trends.
*   **NDBI (Built-up):** Track urban expansion and infrastructure growth.
*   **Water Indices:** Detect surface water using NDWI and MNDWI.
*   **Advanced Logic:** Supports both **Landsat (30m)** and **Sentinel-2 (10m)** datasets.

### ?? Satellite Timelapse Viewer (1984–Present)
*   **Historical Archive:** Explore decades of surface change dynamically.
*   **Interactive Scrubber:** Play, pause, and manually scrub through frames.
*   **Custom Bands:** Support for True Color, Color Infrared, and SWIR.

### ??? UNESCO Heritage Integration
*   Built-in global catalog of UNESCO World Heritage sites.
*   Automated region-of-interest (ROI) definition for heritage site monitoring.

---

## ??? Tech Stack
*   **Compute Engine:** Google Earth Engine (GEE)
*   **Interface:** Streamlit (Python-based SPA)
*   **Mapping:** Leafmap, Folium, Geemap
*   **Authentication:** Service Account (Headless) & OAuth2 (Local)

---

## ?? Deployment Guide (Streamlit Cloud)

TerraScan is ready for one-click deployment.

### Earth Engine Secrets Setup
1.  Go to your **Streamlit Dashboard ?? Settings ?? Secrets**.
2.  Add your Google Cloud Service Account JSON as EARTHENGINE_SERVICE_ACCOUNT.
3.  Use the **TOML Table** format for reliability:

\\\	oml
[EARTHENGINE_SERVICE_ACCOUNT]
type = "service_account"
project_id = "your-project-id"
private_key = \"\"\"-----BEGIN PRIVATE KEY-----
...
-----END PRIVATE KEY-----
\"\"\"
... (other fields)
\\\

---

## ?? Repository Organization
*   pp.py: Main application entry point.
*   equirements.txt: Python dependencies.
*   data/: Pre-cached metadata (UNESCO Site Catalog).
*   index.html: Landing page for GitHub Pages.
*   start_terrascan.bat: Local one-click launcher.

---
*Developed for **NGGSIC 2026**. Transforming satellite data into actionable heritage intelligence.*
