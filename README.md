# ?? TerraScan: Geospatial Intelligence for Heritage & Conservation

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge.svg)](https://terrascan.streamlit.app/)
[![Google Earth Engine](https://img.shields.io/badge/Google%20Earth%20Engine-Active-blue)](https://earthengine.google.com/)

**TerraScan** is a professional-grade geospatial dashboard designed for environmental analysts and UNESCO heritage site monitoring. By leveraging the power of **Google Earth Engine**, TerraScan provides real-time processing of satellite imagery (Landsat & Sentinel) to detect environmental changes, monitor vegetation health, and visualize historical transformations.

---

## ? Key Features

### ?? Multi-Spectral Indices Analysis
Compare two time periods side-by-side using a synchronized split-map interface.
*   **NDVI (Vegetation):** Monitor forest density and agricultural health.
*   **LST (Temperature):** Analyze urban heat islands and surface temperature trends.
*   **NDBI (Built-up):** Track urban expansion and infrastructure growth.
*   **Water Indices:** Detect surface water using NDWI and MNDWI.
*   **Soil & Atmospheric Correction:** Advanced indices like EVI and SAVI.

### ?? Satellite Timelapse Viewer
Generate and explore dynamic historical timelapses (1984–Present).
*   **Custom Bands:** Choose between True Color, Color Infrared, or Shortwave Infrared.
*   **Interactive Scrubber:** Play, pause, and manually scrub through decades of Earth's history.
*   **High-Resolution:** Powered by the Landsat global archive.

### ??? UNESCO Heritage Integration
*   Built-in global catalog of UNESCO World Heritage sites.
*   One-click navigation to monitor specific cultural and natural landmarks.

---

## ??? Tech Stack
*   **Engine:** Google Earth Engine (GEE)
*   **Framework:** Streamlit (SPA Architecture)
*   **Mapping:** Leafmap, Folium, Geemap
*   **Data Processing:** Pandas, NumPy, ThreadPoolExecutor
*   **Visualization:** Plotly, PIL (Advanced GIF processing)

---

## ?? Deployment to Streamlit Cloud

TerraScan is optimized for **Streamlit Cloud** with headless authentication support.

### 1. Repository Setup
Ensure your repository contains:
*   \pp.py\ (Main entry point)
*   \equirements.txt\ (Dependencies)
*   \data/heritage_sites.json\ (Pre-cached data)

### 2. Earth Engine Authentication (Service Account)
Since Streamlit Cloud is a server-side environment, you must use a **GCP Service Account**.

1.  Go to the [GCP Console](https://console.cloud.google.com/).
2.  Create a **Service Account** and grant it the **Earth Engine Resource Viewer** role (or similar).
3.  Generate a **JSON Key** for the service account and download it.
4.  In your Streamlit Cloud dashboard:
    *   Go to **Settings** ?? **Secrets**.
    *   Paste the content of your JSON key into a secret named \EARTHENGINE_SERVICE_ACCOUNT\:

\\\	oml
EARTHENGINE_SERVICE_ACCOUNT = {
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "...",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "..."
}
\\\

---

## ?? Local Development

### Prerequisites
*   Python 3.10+
*   Google Earth Engine Access

### Setup
1. Clone the repository:
   \\\ash
   git clone https://github.com/kingdidntcry-bit/TerraScan.git
   cd TerraScan
   \\\
2. Install dependencies:
   \\\ash
   pip install -r requirements.txt
   \\\
3. Authenticate Earth Engine:
   \\\ash
   earthengine authenticate
   \\\
4. Run the app:
   \\\ash
   streamlit run app.py
   \\\

---

## ?? Project Structure
\\\	ext
TerraScan/
+-- app.py                # Main Application Logic
+-- requirements.txt      # Python Dependencies
+-- data/
¦   +-- heritage_sites.json # UNESCO Site Cache
+-- terrascan/            # Project Assets & Utilities
+-- .gitignore            # Git exclusion rules
\\\

---

## ?? License
This project is developed for the **NGGSIC 2026** competition. All rights reserved.

---
*Developed with ?? for Geospatial Innovation.*
