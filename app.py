import base64
import datetime
import io
import json
import os
from concurrent.futures import ThreadPoolExecutor

import ee
import folium
import folium.plugins
import geemap
import leafmap.foliumap as foliumap
import numpy as np
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageFont, ImageSequence
from streamlit_folium import st_folium

@st.cache_data(show_spinner=False)
def get_location_name(lat, lon):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=10&addressdetails=1"
        headers = {'User-Agent': 'TerraScan-App/1.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if 'address' in data:
                addr = data['address']
                city = addr.get('city', addr.get('town', addr.get('village', addr.get('county', 'Unknown Place'))))
                country = addr.get('country', 'Unknown Country')
                if city == 'Unknown Place' and 'state' in addr:
                    city = addr['state']
                return f"{city}, {country}"
    except: pass
    return f"Lat: {round(lat, 2)}, Lon: {round(lon, 2)}"


@st.cache_data(ttl=86400, show_spinner=False)
def load_britannica_mountains():
    try:
        with open(BRITANNICA_MOUNTAINS_FILE, "r", encoding="utf-8") as f:
            records = json.load(f)
        if isinstance(records, list):
            return sorted(records, key=lambda r: (r.get("country", ""), r.get("mountain", "")))
    except Exception:
        return []
    return []


# --- Setup & Initialize ---
st.set_page_config(layout="wide", page_title="TerraScan")

DEFAULT_CENTER = [2.9264, 101.6964]
DEFAULT_ZOOM = 12
EE_PROJECT = "geomatic-competition-2026"
DEFAULT_BASEMAP = "CartoDB.Positron"
MAP_HEIGHT = 460
UNESCO_WHC_API_URL = "https://data.unesco.org/api/explore/v2.0/catalog/datasets/whc001/records"
BRITANNICA_MOUNTAINS_FILE = "data/brit_mountains.json"
SRTM_ASSET_ID = "USGS/SRTMGL1_003"
TERRAIN_PALETTES = {
    "Terrain": ["#0B3D0B", "#2E8B57", "#86B65B", "#C8B77D", "#8F6E4B", "#F2F2F2"],
    "Turbo": ["#30123B", "#4146B6", "#3EA3F9", "#6CCE5A", "#F9F871", "#F78B2D", "#C61B1F"],
    "Viridis": ["#440154", "#3B528B", "#21918C", "#5EC962", "#FDE725"],
    "Magma": ["#000004", "#3B0F70", "#8C2981", "#DE4968", "#FE9F6D", "#FCFDBF"],
    "Cividis": ["#00204C", "#2E4A7D", "#576D8C", "#8A8F78", "#BDAE58", "#FFE945"],
    "Earth Relief": ["#163A1F", "#2D6A2D", "#6DA34D", "#C2B280", "#8D6E63", "#F5F5F5"],
    "Ice": ["#0B1F3A", "#1D4E89", "#4DA8DA", "#A9D6E5", "#EAF6FF"],
    "Sunset": ["#2B0B3F", "#6A1B9A", "#C2185B", "#F57C00", "#FFD54F"],
}
INDEX_VIS_PARAMS = {
    "NDVI": {"bands": ["NDVI"], "min": -1.0, "max": 1.0, "palette": ["red", "yellow", "green"]},
    "NDBI": {"bands": ["NDBI"], "min": -1.0, "max": 1.0, "palette": ["green", "yellow", "red"]},
    "NDMI": {"bands": ["NDMI"], "min": -1.0, "max": 1.0, "palette": ["brown", "yellow", "blue"]},
    "NDWI": {"bands": ["NDWI"], "min": -1.0, "max": 1.0, "palette": ["brown", "white", "blue"]},
    "MNDWI": {"bands": ["MNDWI"], "min": -1.0, "max": 1.0, "palette": ["brown", "white", "cyan"]},
    "EVI": {"bands": ["EVI"], "min": -1.0, "max": 1.0, "palette": ["red", "yellow", "green"]},
    "SAVI": {"bands": ["SAVI"], "min": -1.0, "max": 1.0, "palette": ["red", "yellow", "green"]},
    "LST": {"bands": ["LST"], "min": 20.0, "max": 45.0, "palette": ["blue", "yellow", "red"]},
}

SESSION_DEFAULTS = {
    "persistent_click": None,
    "map_locked": False,
    "persistent_zoom": DEFAULT_ZOOM,
    "persistent_center": DEFAULT_CENTER,
    "selected_unesco_site_id": None,
    "terrain_center": DEFAULT_CENTER,
    "terrain_zoom": DEFAULT_ZOOM,
    "terrain_click": None,
    "terrain_inspector": None,
    "terrain_mountain_id": None,
    "terrain_extent_km": 15,
    "terrain_z_exag": 3.0,
    "terrain_sampling_scale": 180,
    "terrain_inspector_enabled": False,
}
for key, value in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- SPA Routing Core (Basewell Logic) ---
if "page" not in st.session_state:
    st.session_state.page = "landing"

# --- Global Header ---
st.markdown("""
    <style>
        [data-testid="stHeader"] {
            background: transparent !important;
            pointer-events: none;
        }
        [data-testid="stToolbar"] {
            pointer-events: auto;
        }
    </style>
    <div style='position: fixed; top: 0; left: 0; width: 100%; height: 60px; background-color: #ffffff; box-shadow: 0 2px 4px rgba(0,0,0,0.08); display: flex; align-items: center; padding-left: 75px; gap: 16px; z-index: 999980; pointer-events: none;'>
        <div style='font-size: 1.4rem; font-weight: 700; color: #111827; display: flex; align-items: center; gap: 8px; pointer-events: auto;'>
            ☁ TerraScan
        </div>
        <div style='height: 32px; width: 2px; background-color: #D1D5DB; pointer-events: auto;'></div>
        <img src='https://fab.uitm.edu.my/images/Icon%20and%20Logo/FAB.png' style='height: 40px; object-fit: contain; pointer-events: auto;'>
    </div>
""", unsafe_allow_html=True)

if st.session_state.page == "landing":
    st.markdown("""
        <style>
        /* Allow scroll on landing page and set base white background */
        html, body, [data-testid="stAppViewContainer"], .stApp, .main {
            height: auto !important;
            overflow-y: auto !important;
            background: #ffffff !important;
            scroll-behavior: smooth;
        }
        .main .block-container {
            max-width: 100%;
            margin: 0 auto;
            padding-top: 0px !important;
            padding-left: 5% !important;
            padding-right: 5% !important;
            padding-bottom: 0px !important;
            display: block;
        }
        [data-testid="stSidebar"] {display: none !important;}
        [data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"] {display: none !important;}
        
        .banner {
            display: inline-block;
            background-color: #3B82F6;
            color: white;
            padding: 6px 16px;
            border-radius: 6px;
            font-weight: 500;
            text-align: center;
            font-size: 0.95rem;
            margin-bottom: 1.5rem;
        }
        .hero-title {
            text-align: center;
            font-size: clamp(2rem, 4.8vw, 4rem);
            font-weight: 600;
            color: #111827;
            margin: 0;
            line-height: 1.1;
            letter-spacing: -0.02em;
            text-transform: capitalize;
        }
        .hero-human { color: #3B82F6; font-weight: 500; text-decoration: underline; text-decoration-color: #BFDBFE; text-decoration-thickness: 4px; text-underline-offset: 4px;}
        .hero-agent { color: #3B82F6; font-weight: 500; text-decoration: underline; text-decoration-color: #BFDBFE; text-decoration-thickness: 4px; text-underline-offset: 4px;}
        
        .hero-subtitle {
            text-align: center;
            font-size: clamp(1rem, 1.5vw, 1.2rem);
            color: #4B5563;
            max-width: 700px;
            margin: 1.5rem auto 3rem auto;
            line-height: 1.6;
        }
        
        .doc-card {
            background-color: #ffffff;
            border: 1px solid #E5E7EB;
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            height: 100%;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            position: relative;
            z-index: 1;
        }
        .doc-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            border-color: #3B82F6;
        }
        .doc-card h3 {
            margin-top: 0;
            color: #111827;
            font-size: 1.5rem;
            margin-bottom: 1rem;
        }
        .doc-card p {
            color: #4B5563;
            font-size: 1.05rem;
            line-height: 1.6;
            margin-bottom: 1.5rem;
        }
        
        .footer-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            color: #4B5563;
            font-size: 0.95rem;
            line-height: 1.8;
            max-width: 1000px;
            margin: 0 auto;
        }
        .footer-logo {
            height: 70px;
            object-fit: contain;
            margin-bottom: 1.5rem;
        }
        .footer-title {
            font-weight: 700;
            color: #111827;
            margin-bottom: 1rem;
            font-size: 1.1rem;
        }
        .footer-info {
            margin: 0.3rem 0;
        }
        .footer-email {
            color: #3B82F6;
            text-decoration: none;
            font-weight: 500;
        }
        
        /* General buttons style */
        div.stButton > button {
            position: relative !important;
            z-index: 1 !important;
            background-color: #111827 !important;
            color: white !important;
            border-radius: 8px !important;
            padding: 0.6rem 1.5rem !important;
            font-size: 1.05rem !important;
            font-weight: 600 !important;
            border: none !important;
            width: 100% !important;
        }
        div.stButton > button:hover {
            background-color: #374151 !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # 1. Spacer to push down
    st.markdown("<div style='height: 20vh;'></div>", unsafe_allow_html=True)
    
    # Force scroll to top using Streamlit components (since st.markdown strips scripts)
    components.html(
        """
        <script>
            const main = window.parent.document.querySelector('.main') || window.parent.document.documentElement;
            if (main) {
                main.scrollTop = 0;
                setTimeout(() => { main.scrollTop = 0; }, 100);
            }
        </script>
        """,
        height=0,
        width=0,
    )
    
    # 2. Hero Content perfectly stacked
    st.markdown("""
        <div style='display: flex; flex-direction: column; align-items: center; margin-bottom: 2rem;'>
            <div class='banner'>TerraScan Is Live →</div>
            <div class='hero-title'>
                Satellite Processing Systems<br>
                For <span class='hero-human'>Conservation</span> And <span class='hero-agent'>UNESCO Heritage</span>
            </div>
            <div class='hero-subtitle' style='text-transform: capitalize;'>
                Keep Environmental Analysts And Preservation Models Aligned With TerraScan's Scalable Cloud Platform.
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # 3. Native Explore button centered via columns
    btn_col1, btn_col2, btn_col3 = st.columns([1.5, 1, 1.5])
    with btn_col2:
        if st.button("Explore your way 🚀", use_container_width=True, key="explore_hero"):
            # Point back directly to dashboard as user originally had
            st.session_state.page = "dashboard"
            st.rerun()
            
    # 4. Spacer to complete the exact 100vh split for the navy blue gradient
    st.markdown("<div style='height: 35vh;'></div>", unsafe_allow_html=True)
    
    # --- SECOND PAGE (NAVY BLUE CARDS SECTION) ---
    st.markdown("""
        <!-- Physical Navy Blue Background Block -->
        <div style="position: absolute; left: -50vw; width: 200vw; height: 1500px; background-color: #1E3A8A; z-index: 0; pointer-events: none; margin-top: -6rem;"></div>
        <!-- Title -->
        <h2 style='text-align: center; color: white; margin-bottom: 3rem; position: relative; z-index: 1;'>Select an Analysis Module</h2>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        st.markdown("""
            <div class='doc-card'>
                <h3>📊 Indices Analysis</h3>
                <p>Explore multi-spectral index processing capabilities. Compute indices like NDVI, NDBI, NDMI, and LST natively over any selected global UNESCO World Heritage site.</p>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Learn More / Open Tool", key="btn_indices"):
            st.session_state.page = "dashboard"
            st.rerun()

    with col2:
        st.markdown("""
            <div class='doc-card'>
                <h3>⏳ Timelapse Viewer</h3>
                <p>Observe temporal surface dynamics dynamically through Landsat 8/9 historical archives. Generate custom MP4 animations to track environmental evolution.</p>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Learn More / Open Tool", key="btn_timelapse"):
            st.session_state.page = "dashboard"
            st.rerun()

    with col3:
        st.markdown("""
            <div class='doc-card'>
                <h3>🏔️ Terrain Engine: 3D Elevation</h3>
                <p>Visualize and quantify global mountain topography from SRTM 30m data. Explore elevation, slope, and interactive 3D terrain surfaces.</p>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Learn More / Open Tool", key="btn_terrain"):
            st.session_state.page = "dashboard"
            st.rerun()
            
    # --- THIRD SECTION (WHITE FULL-WIDTH FOOTER) ---
    st.markdown("""
        <div style="position: relative; z-index: 1; width: 100vw; margin-left: calc(50% - 50vw); background-color: #ffffff; padding: 4rem 0 2rem 0; margin-top: 6rem; margin-bottom: -10rem;">
            <div class='footer-container'>
                <img class='footer-logo' src='https://lh3.googleusercontent.com/sitesv/AA5AbUComDqxzCfk5ju9if-jaRZgmBxYYFtKB0FH3wWmiq_2_cm-f1M5q6S7yq9nobNInl3hSiYZk2NedJo4hAAf2c4asIs_ezWj8TYvbOpSbz7kw0k9_jBErfnhLU4MkqYs6D9t6fuf8D8w8IUn81qFFDo53Dffa1rJGGa0yNf_YMZ6smDANmB4TAOcEIY=w16383'>
                <div class='footer-title'>TERRASCAN: AN INTEGRATED SYSTEM FOR DECODING A DECADE OF SURFACE EVOLUTION.</div>
                <p class='footer-info'><b>Team Members:</b> Raja Haziq Bin Raja Idzhar, Nurul Fatin Amira Binti Mohd Nasarrudin, and Eizra Akmal Binti Ellemy Iskandar.</p>
                <p class='footer-info'><b>Supervisor:</b> Sr Dr Lau Chong Luh</p>
                <p class='footer-info'><b>Institution:</b> Universiti Teknologi MARA (UiTM), Shah Alam</p>
                <p class='footer-info'><b>Competition:</b> 13th NGGSIC 2026 - National Geomatics/Geoinformatics Students Innovation Competition (System and Innovation/Gadget)</p>
                <p class='footer-info' style='margin-top: 1rem;'><b>Contact:</b> <a class='footer-email' href='mailto:rajahaziq987@gmail.com'>rajahaziq987@gmail.com</a></p>
            </div>
        </div>
    """, unsafe_allow_html=True)
            
    st.stop()

# Fullscreen dashboard layout (no page scroll)
st.markdown("""
    <style>
    html, body, [data-testid="stAppViewContainer"] {
        height: 100%;
        overflow: hidden;
    }
    [data-testid="stHeader"] {
        background: transparent !important;
        pointer-events: none; /* Let clicks pass through to the map if not clicking a button */
    }
    [data-testid="stToolbar"] {
        display: flex !important;
        pointer-events: auto;
    }
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        z-index: 999999 !important;
        background-color: white !important;
        border-radius: 6px !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.2) !important;
        padding: 4px !important;
        color: black !important;
        pointer-events: auto !important;
    }
    
    [data-testid="stSidebar"] {
        top: 60px !important;
        height: calc(100vh - 60px) !important;
    }
    [data-testid="stSidebarCollapsedControl"] svg,
    [data-testid="collapsedControl"] svg {
        fill: black !important;
        color: black !important;
    }
    .main .block-container {
        max-width: 100%;
        height: 100vh;
        padding-top: 0.25rem;
        padding-bottom: 0.25rem;
        overflow: hidden;
    }
    [data-testid="stVerticalBlock"] {
        gap: 0.3rem;
    }
    </style>
""", unsafe_allow_html=True)

# --- Sidebar Controls ---
if st.sidebar.button("← Return to Home", use_container_width=True):
    st.session_state.page = "landing"
    st.rerun()

st.sidebar.title("TerraScan Catalog")

catalog_mode = st.sidebar.radio(
    "Processing Modules",
    ["Indices Analysis", "Timelapse Viewer", "Terrain Engine: 3D Elevation"],
)

# --- Main App Dashboard ---
st.sidebar.markdown("---")

try:
    # 1. Try Service Account from Secrets (Streamlit Cloud best practice)
    if "EARTHENGINE_SERVICE_ACCOUNT" in st.secrets:
        sa_info = st.secrets["EARTHENGINE_SERVICE_ACCOUNT"]
        
        # Robust handling for string vs dict secrets
        if isinstance(sa_info, str):
            try:
                # Try parsing as JSON first
                sa_info = json.loads(sa_info)
            except Exception:
                # If it's a string but not JSON, it might be the raw private key? 
                # (Unlikely, but we'll try to convert it if it looks like one)
                pass
        
        # Convert SecretSubDict to regular dict if needed
        if hasattr(sa_info, "to_dict"):
            sa_info = sa_info.to_dict()
        elif not isinstance(sa_info, dict) and hasattr(sa_info, "items"):
            sa_info = dict(sa_info.items())

        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_info(sa_info)
        ee.Initialize(credentials=credentials, project=EE_PROJECT)
    else:
        # 2. Fallback to local user auth
        ee.Initialize(project=EE_PROJECT)
except Exception as e:
    try:
        # 3. Interactive fallback (Local only)
        ee.Authenticate()
        ee.Initialize(project=EE_PROJECT)
    except Exception:
        st.error(f"### ⚠️ Earth Engine Authentication Failed")
        st.info(f"**Error Details:** {e}")
        st.markdown("""
        To run this app on the web, you need to provide a Google Cloud Service Account key in the Streamlit Secrets.
        
        **Action Required:**
        1. Go to your Streamlit Dashboard.
        2. Open **Settings -> Secrets**.
        3. Paste the TOML table format I provided.
        
        Current Error: `{e}`
        """)
        st.stop()

with st.sidebar.expander("⚙️ Configuration & Settings", expanded=False):
            
    current_y = datetime.date.today().year

    if catalog_mode == "Indices Analysis":
        st.subheader("General Parameters")
        roi_radius = st.selectbox("Analysis Radius", ["5 km", "10 km"])
        st.subheader("Data Source")
        data_source = st.radio("Select Satellite Interface", ["Landsat (30m)", "Sentinel (10m)"])
    
        st.subheader("Temporal Windows (Annual Median)")
        baseline_year = st.selectbox("Baseline Year", range(2015, current_y + 1), index=max(0, current_y - 2015 - 2))
        comparison_year = st.selectbox("Comparison Year", range(2015, current_y + 1), index=current_y - 2015)
    
        st.subheader("Mapping Indices")
        available_indices = ["True Color", "NDVI", "NDBI", "NDMI", "NDWI", "MNDWI", "EVI", "SAVI"]
        if data_source == "Landsat (30m)":
            available_indices.append("LST")
        layer_selection = st.selectbox("Select Layer to Display", available_indices)
    elif catalog_mode == "Timelapse Viewer":
        st.subheader("General Parameters")
        roi_radius = st.selectbox("Analysis Radius", ["5 km", "10 km"])

        st.subheader("Timelapse Settings")
        tl_start_year = st.selectbox("Start Year", range(1984, current_y), index=0)
        tl_end_year = st.selectbox("End Year", range(1984, current_y + 1), index=current_y - 1984)
        tl_fps = st.slider("Frames Per Second", 1, 10, 5)
        tl_bands = st.selectbox("Band Combination", ["True Color (Red, Green, Blue)", "Color Infrared (NIR, Red, Green)", "SWIR (SWIR2, SWIR1, Red)"])
        run_tl = st.button("Generate Timelapse", use_container_width=True)
    else:
        mountains = load_britannica_mountains()
        if not mountains:
            st.warning("Mountain catalog could not be loaded from data/brit_mountains.json.")

        st.subheader("Mountain Selector")
        countries = sorted({m["country"] for m in mountains}) if mountains else []
        terrain_country = st.selectbox("Country", countries, key="terrain_country_picker") if countries else None

        filtered = [m for m in mountains if m["country"] == terrain_country] if terrain_country else []
        terrain_labels = [f"{m['mountain']} ({m.get('elevation_m', 'n/a')} m)" for m in filtered]
        selected_mountain_label = st.selectbox("Mountain Name", terrain_labels, key="terrain_mountain_picker") if terrain_labels else None
        if selected_mountain_label:
            selected_mountain = next(
                (m for m in filtered if f"{m['mountain']} ({m.get('elevation_m', 'n/a')} m)" == selected_mountain_label),
                None,
            )
            if selected_mountain and st.session_state.get("terrain_mountain_id") != selected_mountain["id"]:
                st.session_state["terrain_mountain_id"] = selected_mountain["id"]
                st.session_state["terrain_center"] = [selected_mountain["lat"], selected_mountain["lng"]]
                st.session_state["terrain_zoom"] = 11
                st.session_state["terrain_click"] = {"lat": selected_mountain["lat"], "lng": selected_mountain["lng"]}
                st.session_state["terrain_inspector"] = None

        st.subheader("Terrain Region")
        terrain_extent_km = st.slider("Region Radius (km)", 4, 35, 15, key="terrain_extent_km")

        st.subheader("3D Viewer")
        terrain_palette_name = st.selectbox("3D Surface Palette", list(TERRAIN_PALETTES.keys()), index=0, key="terrain_palette")
        terrain_vertical_exaggeration = st.slider("Vertical Scale (Flatten < 1.0, Exaggerate > 1.0)", 0.2, 4.0, 3.0, 0.05, key="terrain_z_exag")
        terrain_sample_scale_m = st.slider("3D Sampling Scale (m)", 90, 360, 180, 30, key="terrain_sampling_scale")

# --- GEE Backend Functions ---
def get_landsat_collection(start_date, end_date):
    def prep_landsat(image):
        qa = image.select('QA_PIXEL')
        # Cloud and shadow masking
        cloud_shadow_bit_mask = 1 << 4
        clouds_bit_mask = 1 << 3
        mask = qa.bitwiseAnd(cloud_shadow_bit_mask).eq(0).And(
            qa.bitwiseAnd(clouds_bit_mask).eq(0)
        )
        # Scale factors
        optical_bands = image.select('SR_B.*').multiply(0.0000275).add(-0.2)
        thermal_bands = image.select('ST_B.*').multiply(0.00341802).add(149.0)
        
        # Spectral indices (Awesome Spectral Indices standard forms).
        ndvi = optical_bands.expression(
            '(NIR - RED) / (NIR + RED + 1e-6)', {
                'NIR': optical_bands.select('SR_B5'),
                'RED': optical_bands.select('SR_B4')
            }).rename('NDVI')
        ndbi = optical_bands.expression(
            '(SWIR - NIR) / (SWIR + NIR + 1e-6)', {
                'SWIR': optical_bands.select('SR_B6'),
                'NIR': optical_bands.select('SR_B5')
            }).rename('NDBI')
        ndmi = optical_bands.expression(
            '(NIR - SWIR) / (NIR + SWIR + 1e-6)', {
                'NIR': optical_bands.select('SR_B5'),
                'SWIR': optical_bands.select('SR_B6')
            }).rename('NDMI')
        ndwi = optical_bands.expression(
            '(GREEN - NIR) / (GREEN + NIR + 1e-6)', {
                'GREEN': optical_bands.select('SR_B3'),
                'NIR': optical_bands.select('SR_B5')
            }).rename('NDWI')
        mndwi = optical_bands.expression(
            '(GREEN - SWIR) / (GREEN + SWIR + 1e-6)', {
                'GREEN': optical_bands.select('SR_B3'),
                'SWIR': optical_bands.select('SR_B6')
            }).rename('MNDWI')
        evi = optical_bands.expression(
            '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1.0))', {
                'NIR': optical_bands.select('SR_B5'),
                'RED': optical_bands.select('SR_B4'),
                'BLUE': optical_bands.select('SR_B2')
            }).rename('EVI')
        savi = optical_bands.expression(
            '1.5 * ((NIR - RED) / (NIR + RED + 0.5))', {
                'NIR': optical_bands.select('SR_B5'),
                'RED': optical_bands.select('SR_B4')
            }).rename('SAVI')
        lst = thermal_bands.select('ST_B10').subtract(273.15).rename('LST')
        
        return image.addBands(optical_bands, None, True).addBands([ndvi, ndbi, ndmi, ndwi, mndwi, evi, savi, lst]).updateMask(mask)

    l8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterDate(start_date, end_date)
    l9 = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2").filterDate(start_date, end_date)
    return l8.merge(l9).map(prep_landsat)

def get_sentinel_collection(start_date, end_date):
    def prep_sentinel(image):
        # Use SCL (Scene Classification Layer) for robust cloud/shadow masking
        # SCL is standard for Sentinel-2 Level-2A (Surface Reflectance)
        scl = image.select('SCL')
        # Masking: 3 (Shadows), 8 (Med Prob Cloud), 9 (High Prob Cloud), 10 (Cirrus)
        mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
        
        optical_bands = image.select(['B2', 'B3', 'B4', 'B8', 'B11', 'B12']).divide(10000)
        
        # Spectral indices (Awesome Spectral Indices standard forms).
        ndvi = optical_bands.expression(
            '(NIR - RED) / (NIR + RED + 1e-6)', {
                'NIR': optical_bands.select('B8'),
                'RED': optical_bands.select('B4')
            }).rename('NDVI')
        ndbi = optical_bands.expression(
            '(SWIR - NIR) / (SWIR + NIR + 1e-6)', {
                'SWIR': optical_bands.select('B11'),
                'NIR': optical_bands.select('B8')
            }).rename('NDBI')
        ndmi = optical_bands.expression(
            '(NIR - SWIR) / (NIR + SWIR + 1e-6)', {
                'NIR': optical_bands.select('B8'),
                'SWIR': optical_bands.select('B11')
            }).rename('NDMI')
        ndwi = optical_bands.expression(
            '(GREEN - NIR) / (GREEN + NIR + 1e-6)', {
                'GREEN': optical_bands.select('B3'),
                'NIR': optical_bands.select('B8')
            }).rename('NDWI')
        mndwi = optical_bands.expression(
            '(GREEN - SWIR) / (GREEN + SWIR + 1e-6)', {
                'GREEN': optical_bands.select('B3'),
                'SWIR': optical_bands.select('B11')
            }).rename('MNDWI')
        evi = optical_bands.expression(
            '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1.0))', {
                'NIR': optical_bands.select('B8'),
                'RED': optical_bands.select('B4'),
                'BLUE': optical_bands.select('B2')
            }).rename('EVI')
        savi = optical_bands.expression(
            '1.5 * ((NIR - RED) / (NIR + RED + 0.5))', {
                'NIR': optical_bands.select('B8'),
                'RED': optical_bands.select('B4')
            }).rename('SAVI')
        
        return image.addBands(optical_bands, None, True).addBands([ndvi, ndbi, ndmi, ndwi, mndwi, evi, savi]).updateMask(mask)
        
    return ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterDate(start_date, end_date).map(prep_sentinel)



@st.cache_data(ttl=3600, show_spinner=False)
def get_map_url(lat, lng, radius_m, year, source, layer, _vis_params):
    pt = ee.Geometry.Point([lng, lat])
    roi = pt.buffer(radius_m).bounds()
    img = get_annual_median(year, source).clip(roi)
    if layer == "LST" and source == "Landsat (30m)":
        img = calculate_manual_lst(img)
    return img.getMapId(_vis_params)['tile_fetcher'].url_format

def get_image_download_url(image, filename, source):
    """Generates a GEE download URL for a TIFF image."""
    scale = 30 if "Landsat" in source else 10
    try:
        url = image.getDownloadURL({
            'name': filename,
            'scale': scale,
            'region': image.geometry().bounds(),
            'format': 'GEO_TIFF'
        })
        return url
    except Exception as e:
        return None


def get_visualization_params(layer_selection, data_source):
    if layer_selection == "True Color":
        if data_source == "Landsat (30m)":
            return {"bands": ["SR_B4", "SR_B3", "SR_B2"], "min": 0.0, "max": 0.3}
        return {"bands": ["B4", "B3", "B2"], "min": 0.0, "max": 0.3}
    return INDEX_VIS_PARAMS.get(layer_selection, {"bands": [layer_selection], "min": -1.0, "max": 1.0})


def get_legend_meta(layer_selection):
    if layer_selection == "True Color":
        return None
    params = INDEX_VIS_PARAMS.get(layer_selection)
    if not params:
        return -1.0, 1.0, "black, white"
    return params["min"], params["max"], ", ".join(params.get("palette", ["black", "white"]))


def render_export_buttons(click_pt, baseline_img, comp_img, layer_selection, baseline_year, comparison_year, data_source):
    if click_pt and baseline_img and comp_img:
        st.markdown("### 📥 Export Region as GeoTIFF")
        dl_col1, dl_col2 = st.columns(2)
        
        # Determine export bands
        if layer_selection == "True Color":
            exp_bands = ['SR_B4', 'SR_B3', 'SR_B2'] if "Landsat" in data_source else ['B4', 'B3', 'B2']
        else:
            exp_bands = [layer_selection]
            
        with dl_col1:
            try:
                base_dl_img = baseline_img.select(exp_bands)
                url = get_image_download_url(base_dl_img, f"terrascan_{layer_selection}_{baseline_year}", data_source)
                if url: st.link_button(f"Download {baseline_year} (Left)", url, use_container_width=True)
                else: st.button(f"Download {baseline_year} (Left)", disabled=True, use_container_width=True)
            except: st.button(f"Download {baseline_year} (Left)", disabled=True, use_container_width=True)
            
        with dl_col2:
            try:
                comp_dl_img = comp_img.select(exp_bands)
                url = get_image_download_url(comp_dl_img, f"terrascan_{layer_selection}_{comparison_year}", data_source)
                if url: st.link_button(f"Download {comparison_year} (Right)", url, use_container_width=True)
                else: st.button(f"Download {comparison_year} (Right)", disabled=True, use_container_width=True)
            except: st.button(f"Download {comparison_year} (Right)", disabled=True, use_container_width=True)

def get_annual_median(target_year, source):
    start = f'{target_year}-01-01'
    end = f'{target_year}-12-31'
    if source == "Landsat (30m)":
        return get_landsat_collection(start, end).median()
    else:
        return get_sentinel_collection(start, end).median()

def calculate_manual_lst(img):
    # 1. BT (Brightness Temperature Proxy from Level 2 ST_B10)
    btk = img.select('ST_B10').multiply(0.00341802).add(149.0)
    
    # 2. NDVI (Use pre-computed robust NDVI to avoid divide-by-zero masking on scaled bands)
    ndvi = img.select('NDVI')
    
    # 3. Proportion of Vegetation Pv
    pv = ndvi.subtract(0.2).divide(0.3).clamp(0, 1).pow(2).rename('Pv')
    
    # 4. Emissivity ε (Mono-Window Thresholds)
    epsMixed = pv.multiply(0.004).add(0.986)
    eps = ee.Image(0.99) \
            .where(ndvi.gt(0.5), 0.990) \
            .where(ndvi.gte(0.2).And(ndvi.lte(0.5)), epsMixed) \
            .rename('EMIS')
    
    # 5. Mono-Window LST Evaluation
    lst_k = img.expression(
        'BTK / (1 + (BTK * 0.00115 / 1.438) * log(EPS))', {
            'BTK': btk, 
            'EPS': eps
        }
    )
    lst_band = lst_k.subtract(273.15).rename('LST')
    return img.addBands(lst_band, overwrite=True)

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_unesco_sites():
    local_file = "data/heritage_sites.json"
    
    # 1. Verification Logic: Check local file first
    if os.path.exists(local_file) and os.path.getsize(local_file) > 0:
        try:
            with open(local_file, "r", encoding="utf-8") as f:
                sites = json.load(f)
                if sites:
                    return sites
        except Exception as e:
            st.warning(f"Failed to load local heritage_sites.json: {e}. Falling back to API.")

    # 2. Call external API if site missing or file empty
    sites = []
    limit = 100
    offset = 0
    select_fields = "id_no,name_en,name_fr,states_names,coordinates"

    try:
        while True:
            response = requests.get(
                UNESCO_WHC_API_URL,
                params={"select": select_fields, "limit": limit, "offset": offset},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            records = payload.get("records", [])
            if not records:
                break

            for item in records:
                fields = item.get("record", {}).get("fields", {})
                site_name = fields.get("name_en") or fields.get("name_fr") or "Unknown Site"
                states_names = fields.get("states_names") or []
                if isinstance(states_names, list):
                    country = ", ".join(states_names)
                else:
                    country = str(states_names) if states_names else "Unknown Country"

                coords = fields.get("coordinates") or {}
                lat = coords.get("lat")
                lng = coords.get("lon")
                if lat is None or lng is None:
                    continue

                site_id = str(fields.get("id_no") or f"{site_name}|{country}|{lat}|{lng}")
                sites.append(
                    {
                        "id": site_id,
                        "site": site_name,
                        "country": country,
                        "lat": float(lat),
                        "lng": float(lng),
                    }
                )

            if len(records) < limit:
                break
            offset += limit

        # Deduplicate and sort
        deduped = {site["id"]: site for site in sites}
        final_sites = sorted(deduped.values(), key=lambda s: (s["country"], s["site"]))
        
        # 3. Data Storage: Save to root directory
        with open(local_file, "w", encoding="utf-8") as f:
            json.dump(final_sites, f, indent=4)
            
        return final_sites
    except Exception as e:
        st.error(f"Failed to fetch UNESCO sites from API: {e}")
        return []


def get_terrain_dem():
    return ee.Image(SRTM_ASSET_ID).select("elevation")


def get_terrain_roi(lat, lng, radius_km):
    return ee.Geometry.Point([lng, lat]).buffer(radius_km * 1000).bounds()


def _safe_float(value, default):
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def get_terrain_layer_url(lat, lng, radius_km, palette_name):
    roi = get_terrain_roi(lat, lng, radius_km)
    dem = get_terrain_dem().clip(roi)

    stats = dem.reduceRegion(
        reducer=ee.Reducer.minMax(),
        geometry=roi,
        scale=30,
        maxPixels=1e9,
        bestEffort=True,
    ).getInfo() or {}
    elev_min = _safe_float(stats.get("elevation_min"), 0.0)
    elev_max = _safe_float(stats.get("elevation_max"), 3000.0)
    if elev_max <= elev_min:
        elev_max = elev_min + 1.0

    palette = TERRAIN_PALETTES.get(palette_name, TERRAIN_PALETTES["Terrain"])
    tile_url = dem.getMapId(
        {"min": elev_min, "max": elev_max, "palette": palette}
    )["tile_fetcher"].url_format

    return tile_url, elev_min, elev_max, roi


def get_terrain_point_metrics(lat, lng):
    point = ee.Geometry.Point([lng, lat])
    dem = get_terrain_dem()
    slope = ee.Terrain.slope(dem).rename("slope")
    values = dem.addBands(slope).reduceRegion(
        reducer=ee.Reducer.first(),
        geometry=point,
        scale=30,
        maxPixels=1e6,
    ).getInfo() or {}
    return {
        "elevation": values.get("elevation"),
        "slope": values.get("slope"),
    }


@st.cache_data(ttl=1200, show_spinner=False)
def fetch_terrain_surface_grid(lat, lng, radius_km, sample_scale_m):
    roi = get_terrain_roi(lat, lng, radius_km)
    radius_m = float(radius_km) * 1000.0
    adaptive_scale = max(float(sample_scale_m), (radius_m * 2.0) / 220.0)

    dem = get_terrain_dem().clip(roi).resample("bilinear").reproject(crs="EPSG:4326", scale=adaptive_scale)
    sample_image = dem.addBands(ee.Image.pixelLonLat())
    payload = sample_image.sampleRectangle(region=roi, defaultValue=-9999).getInfo() or {}
    props = payload.get("properties", {})

    z = np.array(props.get("elevation", []), dtype=float)
    lon = np.array(props.get("longitude", []), dtype=float)
    lat_arr = np.array(props.get("latitude", []), dtype=float)

    if z.size == 0 or z.ndim != 2:
        return None

    z[z <= -9999] = np.nan
    if lon.shape != z.shape or lat_arr.shape != z.shape:
        lon = np.tile(np.linspace(lng - 0.2, lng + 0.2, z.shape[1]), (z.shape[0], 1))
        lat_arr = np.tile(np.linspace(lat + 0.2, lat - 0.2, z.shape[0]).reshape(-1, 1), (1, z.shape[1]))

    return {
        "z": z.tolist(),
        "lon": lon.tolist(),
        "lat": lat_arr.tolist(),
    }


# --- Top App Layout (Map & Classification) ---
if catalog_mode == "Indices Analysis":
    col_map, col_stats = st.columns([2, 1])
    
    with col_map:
        st.subheader("Dual-Pane Interactive Map")
    
        unesco_sites = []
        try:
            unesco_sites = fetch_unesco_sites()
        except Exception:
            st.warning("UNESCO site selector is temporarily unavailable. You can still click directly on the map.")
    
        if unesco_sites:
            selector_col1, selector_col2 = st.columns([1, 2])
            country_options = sorted({site["country"] for site in unesco_sites})
    
            with selector_col1:
                selected_country = st.selectbox(
                    "Country",
                    ["All Countries"] + country_options,
                    key="unesco_country_filter",
                )
    
            filtered_sites = [
                site for site in unesco_sites
                if selected_country == "All Countries" or site["country"] == selected_country
            ]
            site_label_to_record = {
                f"{site['site']} ({site['country']})": site for site in filtered_sites
            }
            site_options = ["Select a UNESCO place..."] + list(site_label_to_record.keys())
            
            # Reset logic to avoid StreamlitAPIException (resets state before widget instantiation)
            if st.session_state.get("unesco_reset_pending"):
                st.session_state["unesco_site_picker"] = "Select a UNESCO place..."
                st.session_state["unesco_reset_pending"] = False
    
            with selector_col2:
                selected_site_label = st.selectbox(
                    "UNESCO Place",
                    site_options,
                    key="unesco_site_picker",
                )
    
            if selected_site_label != "Select a UNESCO place...":
                selected_site = site_label_to_record[selected_site_label]
                if st.session_state["selected_unesco_site_id"] != selected_site["id"]:
                    st.session_state["selected_unesco_site_id"] = selected_site["id"]
                    st.session_state["persistent_click"] = {
                        "lat": selected_site["lat"],
                        "lng": selected_site["lng"],
                    }
                    st.session_state["persistent_center"] = [selected_site["lat"], selected_site["lng"]]
                    st.session_state["persistent_zoom"] = 11
                    st.session_state["map_locked"] = True
                    st.rerun()
    
        if not st.session_state.get("map_locked", False):
            st.markdown("Select a UNESCO place above, or click the map to evaluate a 5km UNESCO Heritage region.")
        else:
            ui_c1, ui_c2 = st.columns(2)
            with ui_c1:
                if st.button("Unlock & Select New Region", use_container_width=True):
                    st.session_state["map_locked"] = False
                    st.session_state["persistent_click"] = None
                    st.session_state["selected_unesco_site_id"] = None
                    st.session_state["unesco_reset_pending"] = True
                    st.rerun()
            with ui_c2:
                st.session_state["inspector_active"] = st.toggle("🔍 Enable Click-to-Inspect", value=st.session_state.get("inspector_active", False))
                
        click_pt = st.session_state["persistent_click"]
        
        # Initialize Map preserving the exact local user viewpoint safely
        m = foliumap.Map(center=st.session_state["persistent_center"], zoom=st.session_state["persistent_zoom"], basemap=DEFAULT_BASEMAP)
            
        folium.plugins.Geocoder().add_to(m)
        try:
            if not click_pt:
                st.info("Awaiting interaction. Maps will load satellite data only after a coordinate is selected.")
            else:
                pt = ee.Geometry.Point([click_pt["lng"], click_pt["lat"]])
                radius_m = 5000 if roi_radius == "5 km" else 10000
                roi = pt.buffer(radius_m).bounds()
                
                baseline_img = get_annual_median(baseline_year, data_source).clip(roi)
                comp_img = get_annual_median(comparison_year, data_source).clip(roi)
            
                vis_params = get_visualization_params(layer_selection, data_source)
                if layer_selection == "LST" and data_source == "Landsat (30m)":
                    baseline_img = calculate_manual_lst(baseline_img)
                    comp_img = calculate_manual_lst(comp_img)
    
                with ThreadPoolExecutor(max_workers=2) as executor:
                    f_base = executor.submit(get_map_url, click_pt["lat"], click_pt["lng"], radius_m, baseline_year, data_source, layer_selection, vis_params)
                    f_comp = executor.submit(get_map_url, click_pt["lat"], click_pt["lng"], radius_m, comparison_year, data_source, layer_selection, vis_params)
                    left_url = f_base.result()
                    right_url = f_comp.result()
    
                m.split_map(left_layer=left_url, right_layer=right_url)
        except Exception as e:
            st.error(f"Error drawing map: {e}")
    
        if not st.session_state.get("map_locked", False):
            # Unlocked map - listening for clicks to set ROI
            map_data = st_folium(m, height=MAP_HEIGHT, use_container_width=True, returned_objects=["last_clicked"], key="main_map")
            if map_data and map_data.get("last_clicked"):
                clicked_pt = map_data["last_clicked"]
                if st.session_state["persistent_click"] != clicked_pt:
                    st.session_state["persistent_click"] = clicked_pt
                    st.session_state["persistent_center"] = [clicked_pt["lat"], clicked_pt["lng"]]
                    st.session_state["map_locked"] = True
                    st.rerun()
        else:
            if st.session_state.get("inspector_active", False):
                
                # Auto-initialize inspector if empty, using the center of the ROI
                if not st.session_state.get("inspector_data") and st.session_state.get("persistent_click"):
                    st.session_state["inspector_click"] = st.session_state["persistent_click"]
                    try:
                        c_lat, c_lng = st.session_state["persistent_click"]["lat"], st.session_state["persistent_click"]["lng"]
                        insp_pt = ee.Geometry.Point([c_lng, c_lat])
                        if layer_selection != "True Color":
                            val_base = baseline_img.select(layer_selection).reduceRegion(ee.Reducer.first(), insp_pt, 30).getInfo()
                            val_comp = comp_img.select(layer_selection).reduceRegion(ee.Reducer.first(), insp_pt, 30).getInfo()
                            b_val = list(val_base.values())[0] if val_base and val_base.values() else None
                            c_val = list(val_comp.values())[0] if val_comp and val_comp.values() else None
                            st.session_state["inspector_data"] = {
                                "lat": c_lat,
                                "lng": c_lng,
                                "baseline": b_val,
                                "comparison": c_val
                            }
                        else:
                            st.session_state["inspector_data"] = {
                                "lat": c_lat,
                                "lng": c_lng,
                                "baseline": "RGB",
                                "comparison": "RGB"
                            }
                    except Exception as e:
                        pass
                
                # Draw the Inspector Marker on the map so the user knows exactly what pixel is being read!
                insp_click = st.session_state.get("inspector_click")
                if insp_click:
                    folium.Marker(
                        location=[insp_click["lat"], insp_click["lng"]],
                        tooltip="Inspector Target",
                        icon=folium.Icon(color="black", icon="crosshairs", prefix="fa")
                    ).add_to(m)

                # Locked map with Inspector Active - listening for clicks to probe pixels
                map_data = st_folium(m, height=MAP_HEIGHT, use_container_width=True, returned_objects=["last_clicked"], key="inspector_map")
                if map_data and map_data.get("last_clicked"):
                    clicked_pt = map_data["last_clicked"]
                    if st.session_state.get("inspector_click") != clicked_pt:
                        st.session_state["inspector_click"] = clicked_pt
                        try:
                            insp_pt = ee.Geometry.Point([clicked_pt["lng"], clicked_pt["lat"]])
                            if layer_selection != "True Color":
                                # Crucial Fix: Select the exact band by name instead of select(0) which returned raw B1/B2
                                val_base = baseline_img.select(layer_selection).reduceRegion(ee.Reducer.first(), insp_pt, 30).getInfo()
                                val_comp = comp_img.select(layer_selection).reduceRegion(ee.Reducer.first(), insp_pt, 30).getInfo()
                                
                                b_val = list(val_base.values())[0] if val_base and val_base.values() else None
                                c_val = list(val_comp.values())[0] if val_comp and val_comp.values() else None
                                
                                st.session_state["inspector_data"] = {
                                    "lat": clicked_pt["lat"],
                                    "lng": clicked_pt["lng"],
                                    "baseline": b_val,
                                    "comparison": c_val
                                }
                            else:
                                st.session_state["inspector_data"] = {
                                    "lat": clicked_pt["lat"],
                                    "lng": clicked_pt["lng"],
                                    "baseline": "RGB",
                                    "comparison": "RGB"
                                }
                            st.rerun()
                        except Exception as e:
                            st.warning(f"Inspector failed: {e}")
            else:
                # Clear inspector data if deactivated so it resets clean next time
                if "inspector_data" in st.session_state:
                    del st.session_state["inspector_data"]
                if "inspector_click" in st.session_state:
                    del st.session_state["inspector_click"]
                
                # Butter smooth static map! No lag on pan/zoom, no accidental clicks!
                m.to_streamlit(height=MAP_HEIGHT)
        
        # Safe call for export buttons
        try:
            render_export_buttons(click_pt, baseline_img, comp_img, layer_selection, baseline_year, comparison_year, data_source)
        except: pass
    
    
    # --- Dynamic Legends Area ---
    with col_stats:
        st.subheader("Interactive Indicator Legends")
        st.markdown("Use the classifications below to interpret the satellite spectral maps mathematically.")
    
        if layer_selection == "True Color":
            st.info("True Color visualizes standard human-visible satellite reflections completely unmodified.")
        else:
            st.markdown(f"#### Processing Output: {layer_selection}")
            
            c_min, c_max, c_pal = get_legend_meta(layer_selection)
    
            is_inspector_on = st.session_state.get("inspector_active", False) and st.session_state.get("map_locked", False)
            
            if is_inspector_on:
                insp = st.session_state.get("inspector_data")
                marker_html_left = ""
                marker_html_right = ""
                
                if insp:
                    val_base = insp.get("baseline")
                    if val_base is not None and isinstance(val_base, (int, float)):
                        pct_b = ((max(c_min, min(c_max, val_base)) - c_min) / (c_max - c_min)) * 100
                        marker_html_left = f"<div style='position: absolute; right: -18px; bottom: {pct_b}%; transform: translateY(50%); font-size: 1rem; color: #4B5563; z-index: 10;'>◀</div>"
                    
                    val_comp = insp.get("comparison")
                    if val_comp is not None and isinstance(val_comp, (int, float)):
                        pct_c = ((max(c_min, min(c_max, val_comp)) - c_min) / (c_max - c_min)) * 100
                        marker_html_right = f"<div style='position: absolute; left: -18px; bottom: {pct_c}%; transform: translateY(50%); font-size: 1rem; color: #1e40af; z-index: 10;'>▶</div>"

                st.markdown(
f"""<div style="display: flex; justify-content: center; gap: 3rem; width: 100%; padding: 1rem 0;">
    <!-- LEFT MAP LEGEND -->
    <div style="display: flex; flex-direction: column; align-items: center;">
        <div style="margin-bottom: 8px; font-size: 0.8rem; font-weight: 700; color: #4B5563; text-transform: uppercase;">Left Map</div>
        <div style="margin-bottom: 5px; font-weight: 600; font-size: 1rem;">{c_max}</div>
        <div style="position: relative; width: 30px; height: 250px; background: linear-gradient(to top, {c_pal}); border-radius: 6px; border: 1px solid #d1d5db; box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.05);">
            {marker_html_left}
        </div>
        <div style="margin-top: 5px; font-weight: 600; font-size: 1rem;">{c_min}</div>
    </div>
    <!-- RIGHT MAP LEGEND -->
    <div style="display: flex; flex-direction: column; align-items: center;">
        <div style="margin-bottom: 8px; font-size: 0.8rem; font-weight: 700; color: #1e40af; text-transform: uppercase;">Right Map</div>
        <div style="margin-bottom: 5px; font-weight: 600; font-size: 1rem;">{c_max}</div>
        <div style="position: relative; width: 30px; height: 250px; background: linear-gradient(to top, {c_pal}); border-radius: 6px; border: 1px solid #d1d5db; box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.05);">
            {marker_html_right}
        </div>
        <div style="margin-top: 5px; font-weight: 600; font-size: 1rem;">{c_min}</div>
    </div>
</div>""", unsafe_allow_html=True)
                
                if insp:
                    b_text = f"{insp['baseline']:.3f}" if isinstance(insp.get("baseline"), (int, float)) else "No Data"
                    c_text = f"{insp['comparison']:.3f}" if isinstance(insp.get("comparison"), (int, float)) else "No Data"
                    st.markdown(f"""
                    <div style='background: #f3f4f6; padding: 1rem; border-radius: 8px; margin-top: 1rem; border-left: 4px solid #3B82F6;'>
                        <h5 style='margin: 0 0 0.5rem 0;'>📍 Inspector Reading</h5>
                        <p style='margin: 0; font-size: 0.8rem; color: #4B5563;'>Lat: {insp['lat']:.4f}, Lng: {insp['lng']:.4f}</p>
                        <p style='margin: 0.5rem 0 0 0; font-weight: 600;'>Left Map: <span style='color: #4B5563;'>{b_text}</span></p>
                        <p style='margin: 0; font-weight: 600; color: #1e40af;'>Right Map: {c_text}</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                # Default single colorbar layout when inspector is off
                st.markdown(
f"""<div style="display: flex; flex-direction: column; align-items: center; width: 100%; padding: 1rem 0;">
    <div style="margin-bottom: 5px; font-weight: 600; font-size: 1.1rem;">{c_max}</div>
    <div style="width: 40px; height: 250px; background: linear-gradient(to top, {c_pal}); border-radius: 6px; border: 1px solid #d1d5db; box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.05);"></div>
    <div style="margin-top: 5px; font-weight: 600; font-size: 1.1rem;">{c_min}</div>
</div>""", unsafe_allow_html=True)
    
    # --- Full Width Footer (Documentation) ---
    st.markdown("---")
    st.subheader("📚 Spectral Indices Documentation")
    st.markdown("""
    This dashboard dynamically extracts and calculates spectral indices from raw satellite data to isolate specific physical phenomena on the Earth's surface.
    
    | Index | Name | Real-World Application & Interpretation |
    | :--- | :--- | :--- |
    | **NDVI** | Normalized Difference Vegetation Index | Measures the density and health of green vegetation. High values (green) indicate dense, healthy forests or crops, while low values (red) indicate barren land or concrete. |
    | **NDBI** | Normalized Difference Built-up Index | Highlights urban infrastructure. High values (red) indicate dense concrete, asphalt, or bare soil, while low values (green) indicate vegetation or water. |
    | **NDMI** | Normalized Difference Moisture Index | Detects moisture levels within vegetation. High values (blue) indicate high canopy water content, while low values (brown) indicate water stress or drought. |
    | **NDWI** | Normalized Difference Water Index | Identifies open water bodies. High values (blue) indicate rivers, lakes, or oceans, while low values (brown) indicate dry land. |
    | **MNDWI** | Modified NDWI | An enhanced version of NDWI that uses the Shortwave Infrared band to better distinguish open water from built-up urban features, suppressing noise inside cities. |
    | **EVI** | Enhanced Vegetation Index | Similar to NDVI but mathematically corrected for atmospheric conditions and canopy background noise. Excellent for mapping extremely dense rainforests where NDVI normally saturates. |
    | **SAVI** | Soil Adjusted Vegetation Index | A vegetation index that incorporates a soil brightness correction factor. Ideal for arid, dry, or sparsely vegetated regions where bare soil interferes with standard NDVI readings. |
    | **LST** | Land Surface Temperature | Estimates the actual temperature of the Earth's surface (in °C) by calculating the thermal infrared emissions captured specifically by Landsat 8/9 satellites. |
    """)
    

elif catalog_mode == "Terrain Engine: 3D Elevation":
    mountains = load_britannica_mountains()
    selected_mountain_id = st.session_state.get("terrain_mountain_id")
    selected_mountain = next((m for m in mountains if m["id"] == selected_mountain_id), None)

    st.subheader("Terrain Engine: 3D Elevation")
    st.markdown("Pick a mountain from the Britannica catalog, inspect its SRTM topography in 2D, then explore the same terrain in 3D.")

    if not selected_mountain:
        st.info("Select a country and mountain in the sidebar to begin terrain analysis.")
    else:
        center_lat = float(selected_mountain["lat"])
        center_lng = float(selected_mountain["lng"])
        if not st.session_state.get("terrain_click"):
            st.session_state["terrain_click"] = {"lat": center_lat, "lng": center_lng}

        map_col, stats_col = st.columns([2, 1])
        with map_col:
            info_col, inspect_col = st.columns([1.2, 1.0])
            with info_col:
                st.markdown(
                    f"**Current Mountain:** {selected_mountain['mountain']} ({selected_mountain['country']})"
                )
                st.caption(
                    f"Catalog elevation: {selected_mountain.get('elevation_m', 'n/a')} m | "
                    f"Center: {center_lat:.4f}, {center_lng:.4f}"
                )
            with inspect_col:
                with st.container(border=True):
                    st.markdown("**Inspector**")
                    terrain_inspector_enabled = st.toggle(
                        "Enable Click-to-Inspect",
                        value=False,
                        key="terrain_inspector_enabled",
                    )

            terrain_map = foliumap.Map(
                center=st.session_state.get("terrain_center", [center_lat, center_lng]),
                zoom=st.session_state.get("terrain_zoom", 11),
                basemap=DEFAULT_BASEMAP,
            )
            folium.plugins.Geocoder().add_to(terrain_map)

            try:
                layer_url, elev_min, elev_max, terrain_roi = get_terrain_layer_url(
                    center_lat,
                    center_lng,
                    terrain_extent_km,
                    "Terrain",
                )
                terrain_map.add_tile_layer(
                    url=layer_url,
                    name="DEM Layer",
                    attribution="Google Earth Engine",
                )
                folium.Marker(
                    location=[center_lat, center_lng],
                    tooltip=f"{selected_mountain['mountain']} (Catalog Target)",
                    icon=folium.Icon(color="red", icon="flag"),
                ).add_to(terrain_map)

                inspect_pt = st.session_state.get("terrain_click")
                if inspect_pt and terrain_inspector_enabled:
                    folium.Marker(
                        location=[inspect_pt["lat"], inspect_pt["lng"]],
                        tooltip="Inspector Point",
                        icon=folium.Icon(color="black", icon="crosshairs", prefix="fa"),
                    ).add_to(terrain_map)

                map_data = st_folium(
                    terrain_map,
                    height=MAP_HEIGHT,
                    use_container_width=True,
                    returned_objects=["last_clicked"],
                    key="terrain_map",
                )
                if map_data and map_data.get("last_clicked"):
                    clicked = map_data["last_clicked"]
                    if st.session_state.get("terrain_click") != clicked:
                        st.session_state["terrain_click"] = clicked
                        st.session_state["terrain_center"] = [clicked["lat"], clicked["lng"]]
                        st.session_state["terrain_zoom"] = 11
                        if terrain_inspector_enabled:
                            metrics = get_terrain_point_metrics(clicked["lat"], clicked["lng"])
                            st.session_state["terrain_inspector"] = {
                                "lat": clicked["lat"],
                                "lng": clicked["lng"],
                                "elevation": metrics.get("elevation"),
                                "slope": metrics.get("slope"),
                            }
                        st.rerun()
            except Exception as e:
                st.error(f"Terrain rendering failed: {e}")
                elev_min, elev_max = 0.0, 3000.0

        with stats_col:
            st.subheader("Terrain Legend")
            palette_css = ", ".join(TERRAIN_PALETTES["Terrain"])
            st.markdown(
                f"""<div style="display:flex;flex-direction:column;align-items:center;padding:0.75rem 0;">
<div style="font-weight:700;margin-bottom:6px;">{elev_max:.1f} m</div>
<div style="width:42px;height:240px;border:1px solid #d1d5db;border-radius:6px;background:linear-gradient(to top, {palette_css});"></div>
<div style="font-weight:700;margin-top:6px;">{elev_min:.1f} m</div>
</div>""",
                unsafe_allow_html=True,
            )

            st.subheader("Click Inspector")
            inspector_data = st.session_state.get("terrain_inspector")
            if terrain_inspector_enabled and inspector_data:
                e_val = inspector_data.get("elevation")
                s_val = inspector_data.get("slope")
                e_txt = f"{e_val:.2f} m" if isinstance(e_val, (int, float)) else "No Data"
                s_txt = f"{s_val:.2f} deg" if isinstance(s_val, (int, float)) else "No Data"
                st.markdown(
                    f"""
                    <div style='background:#f3f4f6;padding:0.9rem;border-radius:8px;border-left:4px solid #2563eb;'>
                        <div style='font-weight:700;margin-bottom:0.3rem;'>Point Metrics</div>
                        <div style='font-size:0.85rem;color:#4b5563;'>Lat: {inspector_data['lat']:.5f}, Lng: {inspector_data['lng']:.5f}</div>
                        <div style='margin-top:0.4rem;'>Elevation: <b>{e_txt}</b></div>
                        <div>Slope: <b>{s_txt}</b></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.info("Enable inspector and click a map point to read elevation and slope.")

        st.markdown("---")
        st.subheader("Interactive 3D Terrain Viewer")
        with st.spinner("Building decimated elevation mesh for 3D rendering..."):
            try:
                grid = fetch_terrain_surface_grid(
                    center_lat,
                    center_lng,
                    terrain_extent_km,
                    terrain_sample_scale_m,
                )
                if not grid:
                    st.warning("Could not build 3D grid for this region.")
                else:
                    z = np.array(grid["z"], dtype=float)
                    x = np.array(grid["lon"], dtype=float)
                    y = np.array(grid["lat"], dtype=float)

                    if np.isnan(z).all():
                        st.warning("No valid SRTM elevation pixels were found for this area.")
                    else:
                        z_min = np.nanmin(z)
                        z_max = np.nanmax(z)
                        if np.isnan(z_min) or np.isnan(z_max):
                            st.warning("Elevation values are invalid for this sampled region.")
                            z_span = 1.0
                        else:
                            z_span = max(float(z_max - z_min), 1.0)

                        # Keep elevation values true, then control visual steepness using scene aspect ratio.
                        lat0 = float(np.nanmean(y))
                        lon_span = float(np.nanmax(x) - np.nanmin(x))
                        lat_span = float(np.nanmax(y) - np.nanmin(y))
                        dx_m = max(abs(lon_span) * 111320.0 * max(np.cos(np.deg2rad(lat0)), 0.01), 1.0)
                        dy_m = max(abs(lat_span) * 110540.0, 1.0)
                        base_xy = max(dx_m, dy_m)
                        aspect_x = dx_m / base_xy
                        aspect_y = dy_m / base_xy
                        aspect_z = max(0.03, (z_span * float(terrain_vertical_exaggeration)) / base_xy)

                        palette = TERRAIN_PALETTES.get(terrain_palette_name, TERRAIN_PALETTES["Terrain"])
                        plotly_scale = [[i / max(len(palette) - 1, 1), color] for i, color in enumerate(palette)]

                        fig = go.Figure(
                            data=[
                                go.Surface(
                                    x=x,
                                    y=y,
                                    z=z,
                                    surfacecolor=z,
                                    colorscale=plotly_scale,
                                    cmin=float(np.nanmin(z)),
                                    cmax=float(np.nanmax(z)),
                                    colorbar={"title": "Elevation (m)"},
                                )
                            ]
                        )
                        fig.update_layout(
                            height=640,
                            margin={"l": 0, "r": 0, "t": 20, "b": 0},
                            scene={
                                "xaxis_title": "Longitude",
                                "yaxis_title": "Latitude",
                                "zaxis_title": "Elevation (m)",
                                "aspectmode": "manual",
                                "aspectratio": {"x": aspect_x, "y": aspect_y, "z": aspect_z},
                                "camera": {"eye": {"x": 1.5, "y": 1.6, "z": 0.8}},
                            },
                        )
                        st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"3D surface rendering failed: {e}")

elif catalog_mode == "Timelapse Viewer":
    st.subheader("Satellite Image Timelapse")
    st.markdown("Observe temporal surface dynamics dynamically through Landsat archives.")
    
    click_pt = st.session_state.get("persistent_click")
    if not click_pt:
        st.info("Please switch to **Indices Analysis** to select a UNESCO site or coordinate first, then return here.")
    else:
        st.success(f"Locked on coordinates: {round(click_pt['lat'],4)}, {round(click_pt['lng'],4)}. Generating a {roi_radius} ROI timelapse.")
        
        band_map = {
            "True Color (Red, Green, Blue)": ["Red", "Green", "Blue"],
            "Color Infrared (NIR, Red, Green)": ["NIR", "Red", "Green"],
            "SWIR (SWIR2, SWIR1, Red)": ["SWIR2", "SWIR1", "Red"]
        }
        bands = band_map[tl_bands]
        
        gif_path = "scratch_timelapse.gif"
        mp4_path = "scratch_timelapse.mp4"
        location_name = get_location_name(click_pt['lat'], click_pt['lng'])
        
        if run_tl:
            radius_m = 5000 if roi_radius == "5 km" else 10000
            roi = ee.Geometry.Point([click_pt["lng"], click_pt["lat"]]).buffer(radius_m).bounds()
            with st.spinner("Compiling Earth Engine Timelapse Archive... This may take a minute."):
                try:
                    if os.path.exists(gif_path):
                        os.remove(gif_path)
                    geemap.landsat_timelapse(
                        roi,
                        out_gif=gif_path,
                        start_year=tl_start_year,
                        end_year=tl_end_year,
                        start_date="01-01",
                        end_date="12-31",
                        bands=bands,
                        frames_per_second=tl_fps,
                        add_text=False,  # Bypassing ffmpeg requirement natively!
                        progress_bar_color="blue",
                        mp4=False
                    )
                except Exception as e:
                    st.error(f"Timelapse Generation Failed: {e}")
        
        if os.path.exists(gif_path):
            # Extract frames and pass to HTML
            try:
                with Image.open(gif_path) as img:
                    frames = [frame.copy() for frame in ImageSequence.Iterator(img)]
                
                b64_frames = []
                
                # Burn text natively with Pillow to avoid ffmpeg crashes on Windows
                years = list(range(tl_start_year, tl_end_year + 1))
                
                processed_frames = []
                for idx, frame in enumerate(frames):
                    buf = io.BytesIO()
                    frame = frame.convert('RGB')
                    
                    # Draw Year Overlay directly
                    draw = ImageDraw.Draw(frame)
                    
                    # Try to use a default truetype font if available, fallback to default
                    try:
                        font = ImageFont.truetype("arial.ttf", 36)
                    except Exception:
                        font = ImageFont.load_default()
                        
                    year_text = str(years[min(idx, len(years)-1)])
                    
                    # Optional: Draw shadow for visibility
                    draw.text((22, 22), year_text, font=font, fill="black")
                    draw.text((20, 20), year_text, font=font, fill="white")
                    
                    # --- Bottom Right Location Overlay ---
                    loc_text = location_name
                    try:
                        font_loc = ImageFont.truetype("arial.ttf", 20)
                    except:
                        font_loc = ImageFont.load_default()
                    
                    w, h = frame.size
                    try:
                        bbox = draw.textbbox((0,0), loc_text, font=font_loc)
                        tw = bbox[2] - bbox[0]
                        th = bbox[3] - bbox[1]
                    except:
                        try:
                            tw, th = draw.textsize(loc_text, font=font_loc)
                        except:
                            tw, th = (len(loc_text)*10, 20)
                            
                    x_pos = w - tw - 20
                    y_pos = h - th - 20
                    draw.text((x_pos+2, y_pos+2), loc_text, font=font_loc, fill="black")
                    draw.text((x_pos, y_pos), loc_text, font=font_loc, fill="white")
                    
                    # --- Bottom Left Title Overlay ---
                    title_text = "Landsat Timelapse"
                    draw.text((20+2, y_pos+2), title_text, font=font_loc, fill="black")
                    draw.text((20, y_pos), title_text, font=font_loc, fill="white")
                    
                    # Keep for scrubber
                    frame.save(buf, format="JPEG")
                    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                    b64_frames.append(f"data:image/jpeg;base64,{b64}")
                    
                    # Keep for final GIF download
                    processed_frames.append(frame)
                
                # Save the "Burned" frames to MP4 for download
                if processed_frames:
                    try:
                        import imageio
                        images_array = [np.array(img) for img in processed_frames]
                        imageio.mimsave(mp4_path, images_array, fps=tl_fps, format='FFMPEG', macro_block_size=None)
                    except Exception as e:
                        st.error(f"Failed to save MP4: {e}")
                
                frames_json = json.dumps(b64_frames)
                
                # Render custom scrubber!
                st.markdown("### Interactive Scrubber")
                html_code = f"""
                <div style="width: 100%; max-width: 800px; margin: 0 auto; background: #fff; padding: 10px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <img id="tl-frame" src="{b64_frames[0]}" style="width: 100%; max-height: 450px; object-fit: contain; border-radius: 4px; display: block;" />
                    <div style="display: flex; align-items: center; margin-top: 15px; gap: 15px;">
                        <button id="tl-play" style="background: #111827; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600;">Play</button>
                        <input type="range" id="tl-slider" min="0" max="{len(b64_frames)-1}" value="0" style="flex-grow: 1; cursor: pointer;">
                        <span id="tl-year-badge" style="font-family: monospace; font-weight: bold; font-size: 1.1rem; color: #4B5563;">{tl_start_year}</span>
                    </div>
                </div>
                
                <script>
                    const frames = {frames_json};
                    const startYear = {tl_start_year};
                    const img = document.getElementById('tl-frame');
                    const slider = document.getElementById('tl-slider');
                    const btn = document.getElementById('tl-play');
                    const badge = document.getElementById('tl-year-badge');
                    
                    let playing = false;
                    let timer = null;
                    const fps = {tl_fps};
                    const interval = 1000 / fps;
                    
                    function updateFrame(idx) {{
                        img.src = frames[idx];
                        badge.innerText = startYear + parseInt(idx);
                    }}
                    
                    slider.addEventListener('input', function() {{
                        updateFrame(this.value);
                    }});
                    
                    function step() {{
                        let nextIdx = (parseInt(slider.value) + 1) % frames.length;
                        slider.value = nextIdx;
                        updateFrame(nextIdx);
                    }}
                    
                    btn.addEventListener('click', function() {{
                        playing = !playing;
                        if (playing) {{
                            btn.innerText = "Pause";
                            btn.style.background = "#DC2626";
                            timer = setInterval(step, interval);
                        }} else {{
                            btn.innerText = "Play";
                            btn.style.background = "#111827";
                            clearInterval(timer);
                        }}
                    }});
                </script>
                """
                # --- Export Button (Above Scrubber) ---
                st.markdown("### 📥 Download Timelapse (MP4)")
                mp4_path = "scratch_timelapse.mp4"
                if os.path.exists(mp4_path):
                    with open(mp4_path, "rb") as f:
                        st.download_button(
                            label="🎬 Download as MP4 Video",
                            data=f,
                            file_name=f"terrascan_timelapse_{tl_start_year}_{tl_end_year}.mp4",
                            mime="video/mp4",
                            use_container_width=True
                        )

                st.components.v1.html(html_code, height=700)
            except Exception as e:
                st.error(f"Error parsing GIF frames: {e}")
