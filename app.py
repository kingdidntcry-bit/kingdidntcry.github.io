import streamlit as st
import base64
from PIL import Image, ImageSequence, ImageDraw, ImageFont
import os
import geemap
from streamlit_folium import st_folium
import ee
import datetime
import folium.plugins
import leafmap.foliumap as foliumap
import requests
import json
from concurrent.futures import ThreadPoolExecutor

# --- Setup & Initialize ---
st.set_page_config(layout="wide", page_title="TerraScan")

DEFAULT_CENTER = [2.9264, 101.6964]
DEFAULT_ZOOM = 12
EE_PROJECT = "geomatic-competition-2026"
DEFAULT_BASEMAP = "CartoDB.Positron"
MAP_HEIGHT = 460
UNESCO_WHC_API_URL = "https://data.unesco.org/api/explore/v2.0/catalog/datasets/whc001/records"

SESSION_DEFAULTS = {
    "persistent_click": None,
    "map_locked": False,
    "persistent_zoom": DEFAULT_ZOOM,
    "persistent_center": DEFAULT_CENTER,
    "selected_unesco_site_id": None,
    "ml_cache": None,
}
for key, value in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- SPA Routing Core (Basewell Logic) ---
if "page" not in st.session_state:
    st.session_state.page = "landing"

if st.session_state.page == "landing":
    st.markdown("""
        <style>
        html, body, [data-testid="stAppViewContainer"] {
            height: 100%;
            overflow: hidden;
        }
        .main .block-container {
            max-width: 100%;
            height: 100vh;
            padding-top: 0.6rem;
            padding-bottom: 0.6rem;
            overflow: hidden;
        }
        [data-testid="stSidebar"] {display: none;}
        [data-testid="collapsedControl"] {display: none;}
        
        .hero-title {
            text-align: center;
            font-size: clamp(2rem, 4.8vw, 4rem);
            font-weight: 600;
            color: #111827;
            margin-top: 1.4rem;
            line-height: 1.1;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
            letter-spacing: -0.02em;
        }
        .hero-human { color: #3B82F6; font-weight: 500; text-decoration: underline; text-decoration-color: #BFDBFE; text-decoration-thickness: 4px; text-underline-offset: 4px;}
        .hero-agent { color: #3B82F6; font-family: 'Courier New', monospace; font-weight: bold; letter-spacing: -2px;}
        
        .hero-subtitle {
            text-align: center;
            font-size: clamp(1rem, 1.5vw, 1.2rem);
            color: #4B5563;
            max-width: 650px;
            margin: 1rem auto 1.4rem auto;
            line-height: 1.5;
        }
        
        .banner {
            display: block;
            width: fit-content;
            margin: 0 auto;
            background-color: #3B82F6;
            color: white;
            padding: 6px 14px;
            border-radius: 6px;
            font-weight: 500;
            text-align: center;
            font-size: 0.9rem;
        }
        .logo-bar {
            padding: 1rem 2rem;
            font-size: 1.5rem;
            font-weight: 700;
            color: #111827;
        }
        
        div.stButton > button:first-child {
            background-color: #111827 !important;
            color: white !important;
            border-radius: 8px !important;
            padding: 0.5rem 1rem !important;
            font-weight: 600 !important;
            border: none !important;
            width: 100%;
        }
        div.stButton > button:hover {
            background-color: #374151 !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<div class='logo-bar'>☁ TerraScan</div>", unsafe_allow_html=True)
    st.markdown("<div class='banner'>TerraScan integration is live →</div>", unsafe_allow_html=True)
    
    st.markdown("""
        <div class='hero-title'>
            Satellite processing systems<br>
            for <span class='hero-human'>conservation</span> and <span class='hero-agent'>UNESCO heritage</span>
        </div>
        <div class='hero-subtitle'>
            Keep environmental analysts and preservation models aligned with TerraScan's scalable cloud platform.
        </div>
    """, unsafe_allow_html=True)
    
    _, _, col3, _, _ = st.columns([2, 1, 1, 1, 2])
    with col3:
        if st.button("Browse Catalog"):
            st.session_state.page = "dashboard"
            st.rerun()
            
    st.stop()

# Fullscreen dashboard layout (no page scroll)
st.markdown("""
    <style>
    html, body, [data-testid="stAppViewContainer"] {
        height: 100%;
        overflow: hidden;
    }
    [data-testid="stHeader"], [data-testid="stToolbar"] {
        display: none;
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

catalog_mode = st.sidebar.radio("Processing Modules", ["Indices Analysis", "Timelapse Viewer"])

# --- Main App Dashboard ---
st.sidebar.markdown("---")
run_ml = False

try:
    # 1. Try Service Account from Secrets (Streamlit Cloud best practice)
    if "EARTHENGINE_SERVICE_ACCOUNT" in st.secrets:
        sa_info = st.secrets["EARTHENGINE_SERVICE_ACCOUNT"]
        
        # Robust handling for string vs dict secrets
        if isinstance(sa_info, str):
            import json
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
        st.subheader("Data Source")
        data_source = st.radio("Select Satellite Interface", ["Landsat (30m)", "Sentinel (10m)"])
        
        st.subheader("Analysis Parameters")
        roi_radius = st.selectbox("Analysis Radius", ["5 km", "10 km"])
    
        st.subheader("Temporal Windows (Annual Median)")
        baseline_year = st.selectbox("Baseline Year", range(2015, current_y + 1), index=max(0, current_y - 2015 - 2))
        comparison_year = st.selectbox("Comparison Year", range(2015, current_y + 1), index=current_y - 2015)
    
        st.subheader("Mapping Indices")
        available_indices = ["True Color", "NDVI", "NDBI", "NDMI", "NDWI", "MNDWI", "EVI", "SAVI"]
        if data_source == "Landsat (30m)":
            available_indices.append("LST")
        layer_selection = st.selectbox("Select Layer to Display", available_indices)
    else:
        st.subheader("Timelapse Settings")
        tl_start_year = st.selectbox("Start Year", range(1984, current_y), index=0)
        tl_end_year = st.selectbox("End Year", range(1984, current_y + 1), index=current_y - 1984)
        tl_fps = st.slider("Frames Per Second", 1, 10, 5)
        tl_bands = st.selectbox("Band Combination", ["True Color (Red, Green, Blue)", "Color Infrared (NIR, Red, Green)", "SWIR (SWIR2, SWIR1, Red)"])
        run_tl = st.button("Generate Timelapse", use_container_width=True)


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
    
    # 2. NDVI
    ndvi = img.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI')
    
    # 3. Proportion of Vegetation Pv
    pv = ndvi.subtract(0.2).divide(0.3).clamp(0, 1).pow(2).rename('Pv')
    
    # 4. Emissivity \u03b5 (Mono-Window Thresholds)
    epsMixed = pv.multiply(0.004).add(0.986)
    eps = ee.Image(0.99) \
            .where(ndvi.gt(0.5), 0.990) \
            .where(ndvi.gte(0.2).And(ndvi.lte(0.5)), epsMixed) \
            .rename('EMIS')
    
    # 5. Mono-Window LST Evaluation
    # lst_k = btk / (1 + (btk * 0.00115 / 1.438) * ln(eps))
    lst_k = img.expression(
        'BTK / (1 + (BTK * 0.00115 / 1.438) * log(EPS))', {
            'BTK': btk, 
            'EPS': eps
        }
    )
    return lst_k.subtract(273.15).rename('LST')

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
            st.markdown("Observation Mode: The map is locked for stable UI interaction.")
            if st.button("Unlock & Select New Region", use_container_width=True):
                st.session_state["map_locked"] = False
                st.session_state["persistent_click"] = None
                st.session_state["selected_unesco_site_id"] = None
                st.session_state["unesco_reset_pending"] = True
                st.rerun()
                
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
            
                if layer_selection == "NDVI":
                    vis_params = {'bands': ['NDVI'], 'min': -1.0, 'max': 1.0, 'palette': ['red', 'yellow', 'green']}
                    def fetch_url(img): 
                        return img.getMapId(vis_params)['tile_fetcher'].url_format
                elif layer_selection == "LST" and data_source == "Landsat (30m)":
                    vis_params = {'bands': ['LST'], 'min': 20.0, 'max': 45.0, 'palette': ['blue', 'yellow', 'red']}
                    baseline_img = calculate_manual_lst(baseline_img)
                    comp_img = calculate_manual_lst(comp_img)
                    def fetch_url(img):
                        return img.getMapId(vis_params)['tile_fetcher'].url_format
                else:
                    if layer_selection == "True Color":
                        if data_source == "Landsat (30m)":
                            vis_params = {'bands': ['SR_B4', 'SR_B3', 'SR_B2'], 'min': 0.0, 'max': 0.3}
                        else:
                            vis_params = {'bands': ['B4', 'B3', 'B2'], 'min': 0.0, 'max': 0.3}
                    elif layer_selection == "NDBI":
                        vis_params = {'bands': ['NDBI'], 'min': -1.0, 'max': 1.0, 'palette': ['green', 'yellow', 'red']}
                    elif layer_selection == "NDMI":
                        vis_params = {'bands': ['NDMI'], 'min': -1.0, 'max': 1.0, 'palette': ['brown', 'yellow', 'blue']}
                    elif layer_selection == "NDWI":
                        vis_params = {'bands': ['NDWI'], 'min': -1.0, 'max': 1.0, 'palette': ['brown', 'white', 'blue']}
                    elif layer_selection == "MNDWI":
                        vis_params = {'bands': ['MNDWI'], 'min': -1.0, 'max': 1.0, 'palette': ['brown', 'white', 'cyan']}
                    elif layer_selection == "EVI":
                        vis_params = {'bands': ['EVI'], 'min': -1.0, 'max': 1.0, 'palette': ['red', 'yellow', 'green']}
                    elif layer_selection == "SAVI":
                        vis_params = {'bands': ['SAVI'], 'min': -1.0, 'max': 1.0, 'palette': ['red', 'yellow', 'green']}
                    elif layer_selection == "LST":
                        vis_params = {'bands': ['LST'], 'min': 20.0, 'max': 45.0, 'palette': ['blue', 'yellow', 'red']}
                    
                    def fetch_url(img):
                        return img.getMapId(vis_params)['tile_fetcher'].url_format
    
                with ThreadPoolExecutor(max_workers=2) as executor:
                    f_base = executor.submit(fetch_url, baseline_img)
                    f_comp = executor.submit(fetch_url, comp_img)
                    left_url = f_base.result()
                    right_url = f_comp.result()
    
                m.split_map(left_layer=left_url, right_layer=right_url)
        except Exception as e:
            st.error(f"Error drawing map: {e}")
    
        # Render st_folium locally for tracking OR static DOM natively for security structurally scaling 
        if not st.session_state.get("map_locked", False):
            map_data = st_folium(m, height=MAP_HEIGHT, use_container_width=True, returned_objects=["last_clicked"], key="main_map")
            
            if map_data and map_data.get("last_clicked"):
                if st.session_state["persistent_click"] != map_data["last_clicked"]:
                    st.session_state["persistent_click"] = map_data["last_clicked"]
                    new_c = map_data["last_clicked"]
                    st.session_state["persistent_center"] = [new_c["lat"], new_c["lng"]]
                    st.session_state["map_locked"] = True
                    st.rerun()
        else:
            m.to_streamlit(height=MAP_HEIGHT)
    
    # --- Dynamic Legends Area ---
    with col_stats:
        st.subheader("Interactive Indicator Legends")
        st.markdown("Use the classifications below to interpret the satellite spectral maps mathematically.")
    
        if layer_selection == "True Color":
            st.info("True Color visualizes standard human-visible satellite reflections completely unmodified.")
        else:
            st.markdown(f"#### Processing Output: {layer_selection}")
            
            # Determine continuous legend properties
            if layer_selection == "NDVI":
                c_min, c_max, c_pal = -1.0, 1.0, "red, yellow, green"
            elif layer_selection == "LST":
                c_min, c_max, c_pal = 20.0, 45.0, "blue, yellow, red"
            elif layer_selection == "NDBI":
                c_min, c_max, c_pal = -1.0, 1.0, "green, yellow, red"
            elif layer_selection == "NDMI":
                c_min, c_max, c_pal = -1.0, 1.0, "brown, yellow, blue"
            elif layer_selection == "NDWI":
                c_min, c_max, c_pal = -1.0, 1.0, "brown, white, blue"
            elif layer_selection == "MNDWI":
                c_min, c_max, c_pal = -1.0, 1.0, "brown, white, cyan"
            elif layer_selection in ["EVI", "SAVI"]:
                c_min, c_max, c_pal = -1.0, 1.0, "red, yellow, green"
            else:
                c_min, c_max, c_pal = -1.0, 1.0, "black, white"
    
            st.markdown(f"""
            <div style="display: flex; flex-direction: column; align-items: center; width: 100%; padding: 1rem 0;">
                <div style="margin-bottom: 5px; font-weight: 600; font-size: 1.1rem;">{c_max}</div>
                <div style="width: 40px; height: 250px; background: linear-gradient(to top, {c_pal}); border-radius: 6px; border: 1px solid #d1d5db; box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.05);"></div>
                <div style="margin-top: 5px; font-weight: 600; font-size: 1.1rem;">{c_min}</div>
            </div>
            """, unsafe_allow_html=True)
    
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
    

elif catalog_mode == "Timelapse Viewer":
    st.subheader("Satellite Image Timelapse")
    st.markdown("Observe temporal surface dynamics dynamically through Landsat archives.")
    
    click_pt = st.session_state.get("persistent_click")
    if not click_pt:
        st.info("Please switch to **Indices Analysis** to select a UNESCO site or coordinate first, then return here.")
    else:
        st.success(f"Locked on coordinates: {round(click_pt['lat'],4)}, {round(click_pt['lng'],4)}. Generating a 5km ROI timelapse.")
        
        band_map = {
            "True Color (Red, Green, Blue)": ["Red", "Green", "Blue"],
            "Color Infrared (NIR, Red, Green)": ["NIR", "Red", "Green"],
            "SWIR (SWIR2, SWIR1, Red)": ["SWIR2", "SWIR1", "Red"]
        }
        bands = band_map[tl_bands]
        
        gif_path = "scratch_timelapse.gif"
        
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
                        title="Landsat Timelapse",
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
                import io
                
                # Burn text natively with Pillow to avoid ffmpeg crashes on Windows
                years = list(range(tl_start_year, tl_end_year + 1))
                
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
                    
                    frame.save(buf, format="JPEG")
                    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                    b64_frames.append(f"data:image/jpeg;base64,{b64}")
                
                import json
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
                st.components.v1.html(html_code, height=700)
            except Exception as e:
                st.error(f"Error parsing GIF frames: {e}")
