# ☁️ TerraScan: Technical Executive Summary & Competition Kit
**Date:** May 16, 2026
**Project:** TerraScan Geospatial Portal
**Competition:** 13th National Geomatics/Geoinformatics Students Innovation Competition (NGGSIC)

---

## 🏗️ 1. Technical Architecture Overview

TerraScan is a cloud-native geospatial analysis portal designed to decode planetary surface evolution over time. It leverages a modern "Three-Pillar" engine architecture.

### A. The Spectral Analysis Engine (Landsat 8/9)
*   **Logic:** Converts raw multispectral bands into environmental indices (NDVI, LST, NDWI, etc.) using normalized difference algorithms.
*   **Performance:** Uses "Spatial Reducers" (Median/Mean) to perform complex statistical analysis on millions of pixels in real-time via the Google Earth Engine (GEE) API.

### B. The 3D Terrain Engine (SRTM 30m)
*   **Logic:** Decimates raw 30-meter SRTM elevation data into a optimized grid for web rendering.
*   **Visualization:** Uses Plotly's 3D Surface engine with adjustable vertical exaggeration and custom spectral palettes to highlight subtle topographic changes.

### C. The Temporal Engine (10-Year Timelapse)
*   **Logic:** Annual Median Compositing. It filters 10 years of satellite passes and selects the median pixel for each year to create a "Cloud-Free" historical sequence.
*   **Optimization:** Uses Base64-encoded frames and a custom JavaScript "Scrubber" for lag-free time-series navigation.

---

## 📚 2. Key Technical Concepts (The "Glossary")

*   **API (Application Programming Interface):** The "bridge" that connects our app to Google's supercomputers. We send code (requests) and receive processed data (results).
*   **Base64 Encoding:** A method of converting images into text strings. This allows the app to store logos and icons directly inside the code for instant loading without external file dependencies.
*   **Decimation:** The process of reducing the density of a 3D grid. By sampling every 6th pixel instead of every pixel, we reduce browser memory load by ~80% while maintaining topographic accuracy.
*   **SPA (Single Page Application):** The app structure where different "pages" are swapped dynamically within the same window, preventing slow browser refreshes.

---

## ⚖️ 3. Judges' Q&A: Anticipated Questions

### **Q1: What is the primary innovation of TerraScan?**
**Answer:** TerraScan's innovation lies in its "Accessibility." We have moved high-end GIS processing from expensive desktop workstations to a lightweight, browser-based cloud portal. By combining GEE-cloud processing with our custom Interactive Scrubber and 3D Terrain Engine, we've made 10-year surface analysis instantaneous for the user.

### **Q2: How accurate is your Land Surface Temperature (LST)?**
**Answer:** Our LST module uses the thermal infrared bands (B10/B11) from Landsat 8/9. We apply a mathematical conversion from raw radiance to degrees Celsius, ensuring that the relative temperature differences in urban heat islands are accurately visualized.

### **Q3: How do you handle cloud cover in the timelapse?**
**Answer:** We use a "Median Reducer." Since clouds are temporary, taking the median value of all passes in a single year effectively "erases" the clouds, as the ground surface is the most persistent spectral value over time.

### **Q4: Can this system scale to larger regions?**
**Answer:** Yes. Because we use GEE’s distributed computing, the complexity of the calculation happens on Google's servers. Our local code only handles the visualization of the results, making it highly scalable for different regional extents.

---

## 🎨 4. Presentation & Branding Strategy

*   **White Minimalist Theme:** Designed to mirror professional geospatial tools like Mapbox or ArcGIS Online, moving away from "amateur" dark themes.
*   **Logo Integration:** Local branding (UiTM and NGGSIC) is hard-coded via Base64 to ensure the platform looks "official" and "ready-for-market" the moment it loads.
*   **Interactive Demo:** The "Click-to-Inspect" feature is the key "WOW" factor. Use it to show live data extraction from the map to a chart.

---

## 🛠️ 5. Development Workspace Summary
*   **Root Directory:** `app.py` (Main Logic), `requirements.txt` (Dependencies), `.gitignore` (Cleanliness).
*   **Assets:** `assets/` (Branding), `data/` (Mountain Catalog).
*   **Outputs:** `exports/` (TIMELAPSE.mp4, DEM.tif).

---
**Good luck at the 13th NGGSIC 2026!**
