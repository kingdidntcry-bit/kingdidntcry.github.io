import streamlit as st
from streamlit_folium import st_folium
import ee
import datetime
import folium.plugins
import leafmap.foliumap as foliumap
from concurrent.futures import ThreadPoolExecutor

# --- Setup & Initialize ---
st.set_page_config(layout="wide", page_title="TerraScan")

DEFAULT_CENTER = [2.9264, 101.6964]
DEFAULT_ZOOM = 12
EE_PROJECT = "geomatic-competition-2026"

SESSION_DEFAULTS = {
    "persistent_click": None,
    "map_locked": False,
    "persistent_zoom": DEFAULT_ZOOM,
    "persistent_center": DEFAULT_CENTER,
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
        [data-testid="stSidebar"] {display: none;}
        [data-testid="collapsedControl"] {display: none;}
        
        .hero-title {
            text-align: center;
            font-size: 4.5rem;
            font-weight: 600;
            color: #111827;
            margin-top: 3rem;
            line-height: 1.1;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
            letter-spacing: -0.02em;
        }
        .hero-human { color: #3B82F6; font-weight: 500; text-decoration: underline; text-decoration-color: #BFDBFE; text-decoration-thickness: 4px; text-underline-offset: 4px;}
        .hero-agent { color: #3B82F6; font-family: 'Courier New', monospace; font-weight: bold; letter-spacing: -2px;}
        
        .hero-subtitle {
            text-align: center;
            font-size: 1.3rem;
            color: #4B5563;
            max-width: 650px;
            margin: 2rem auto;
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

# --- Sidebar Controls ---
if st.sidebar.button("← Return to Home", use_container_width=True):
    st.session_state.page = "landing"
    st.rerun()

st.sidebar.title("TerraScan Catalog")

catalog_mode = st.sidebar.radio("Processing Modules", [
    "Temporal Indices Comparison",
    "Machine Learning Land Classification"
])

if catalog_mode == "Machine Learning Land Classification":
    st.markdown("<h1 style='text-align: center;'>Machine Learning Land Classification</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: gray;'>Module Under Development</h4>", unsafe_allow_html=True)
    st.info("The AI neural networking framework parsing Land Classification is currently offline. Please toggle the sidebar to return to the Temporal Indices Processing module.")
    st.stop()

# --- Main App Dashboard ---
st.sidebar.markdown("---")

with st.sidebar.expander("⚙️ Configuration & Settings", expanded=False):
    try:
        ee.Initialize(project=EE_PROJECT)
    except Exception:
        try:
            ee.Authenticate()
            ee.Initialize(project=EE_PROJECT)
        except Exception:
            st.error(f"Failed to authenticate with project '{EE_PROJECT}'. Ensure your project exists and Earth Engine API is enabled.")
            st.stop()
            
    st.subheader("Map Preferences")
    selected_basemap = st.selectbox("Global Basemap", ["CartoDB.Positron", "CartoDB.DarkMatter", "SATELLITE", "HYBRID", "OpenStreetMap"])
    
    st.markdown("---")
    st.subheader("Data Source")
    data_source = st.radio("Select Satellite Interface", ["Landsat (30m)", "Sentinel (10m)"])
    
    st.subheader("Temporal Windows (Annual Median)")
    current_y = datetime.date.today().year
    baseline_year = st.selectbox("Baseline Year", range(2015, current_y + 1), index=max(0, current_y - 2015 - 2))
    comparison_year = st.selectbox("Comparison Year", range(2015, current_y + 1), index=current_y - 2015)
    
    st.subheader("Mapping Indices")
    available_indices = ["True Color", "NDVI", "NDBI"]
    if data_source == "Landsat (30m)":
        available_indices.append("LST")
    layer_selection = st.selectbox("Select Layer to Display", available_indices)
    
    st.markdown("""
    ---
    **Help: Indices Explained**
    - **NDVI**: Measures healthy vegetation. (> 0.7 dense veg)
    - **NDBI**: Measures built-up areas. (> 0.3 urban)
    - **LST**: Ground temperature in °C.
    """)

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
        
        # Calculate Indices using explicit formula expressions
        ndvi = optical_bands.expression(
            '(NIR - RED) / (NIR + RED + 0.0001)', {
                'NIR': optical_bands.select('SR_B5'),
                'RED': optical_bands.select('SR_B4')
            }).rename('NDVI')
        ndbi = optical_bands.expression(
            '(SWIR - NIR) / (SWIR + NIR + 0.0001)', {
                'SWIR': optical_bands.select('SR_B6'),
                'NIR': optical_bands.select('SR_B5')
            }).rename('NDBI')
        lst = thermal_bands.select('ST_B10').subtract(273.15).rename('LST')
        
        return image.addBands(optical_bands, None, True).addBands([ndvi, ndbi, lst]).updateMask(mask)

    l8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterDate(start_date, end_date)
    l9 = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2").filterDate(start_date, end_date)
    return l8.merge(l9).map(prep_landsat)

def get_sentinel_collection(start_date, end_date):
    def prep_sentinel(image):
        qa = image.select('QA60')
        cloud_bit_mask = 1 << 10
        cirrus_bit_mask = 1 << 11
        mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
            qa.bitwiseAnd(cirrus_bit_mask).eq(0)
        )
        optical_bands = image.select(['B2', 'B3', 'B4', 'B8', 'B11']).divide(10000)
        
        # Calculate Indices using explicit formula expressions
        ndvi = optical_bands.expression(
            '(NIR - RED) / (NIR + RED + 0.0001)', {
                'NIR': optical_bands.select('B8'),
                'RED': optical_bands.select('B4')
            }).rename('NDVI')
        ndbi = optical_bands.expression(
            '(SWIR - NIR) / (SWIR + NIR + 0.0001)', {
                'SWIR': optical_bands.select('B11'),
                'NIR': optical_bands.select('B8')
            }).rename('NDBI')
        
        return image.addBands(optical_bands, None, True).addBands([ndvi, ndbi]).updateMask(mask)
        
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


# --- Top App Layout (Map & Classification) ---
col_map, col_stats = st.columns([2, 1])

with col_map:
    st.subheader("Dual-Pane Interactive Map")
    
    if not st.session_state.get("map_locked", False):
        st.markdown("Click any point on the global map to dynamically evaluate a 10km UNESCO Heritage region.")
    else:
        st.markdown("🔒 **Observation Mode**: The map is locked for stable UI interaction.")
        if st.button("🔓 Unlock & Select New Region", use_container_width=True):
            st.session_state["map_locked"] = False
            st.session_state["persistent_click"] = None
            st.rerun()
            
    click_pt = st.session_state["persistent_click"]
    
    # Initialize Map preserving the exact local user viewpoint safely
    m = foliumap.Map(center=st.session_state["persistent_center"], zoom=st.session_state["persistent_zoom"], basemap=selected_basemap)
        
    folium.plugins.Geocoder().add_to(m)
    
    try:
        if not click_pt:
            st.info("Awaiting interaction. Maps will load satellite data only after a coordinate is selected.")
        else:
            pt = ee.Geometry.Point([click_pt["lng"], click_pt["lat"]])
            roi = pt.buffer(10000).bounds()
            
            baseline_img = get_annual_median(baseline_year, data_source).clip(roi)
            comp_img = get_annual_median(comparison_year, data_source).clip(roi)
        
            if layer_selection == "NDVI":
                vis_params = {'bands': ['NDVI'], 'min': -1.0, 'max': 1.0, 'palette': ['red', 'yellow', 'green']}
                m.add_colormap(width=4.0, height=0.25, vmin=-1.0, vmax=1.0, palette=['red', 'yellow', 'green'], label="NDVI Index")
                def fetch_url(img): 
                    return img.getMapId(vis_params)['tile_fetcher'].url_format
            elif layer_selection == "LST" and data_source == "Landsat (30m)":
                vis_params = {'bands': ['LST'], 'min': 20.0, 'max': 45.0, 'palette': ['blue', 'yellow', 'red']}
                m.add_colormap(width=4.0, height=0.25, vmin=20.0, vmax=45.0, palette=['blue', 'yellow', 'red'], label="LST (°C)")
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
                    m.add_colormap(width=4.0, height=0.25, vmin=-1.0, vmax=1.0, palette=['green', 'yellow', 'red'], label="NDBI Index")
                elif layer_selection == "LST":
                    vis_params = {'bands': ['LST'], 'min': 20.0, 'max': 45.0, 'palette': ['blue', 'yellow', 'red']}
                    m.add_colormap(width=4.0, height=0.25, vmin=20.0, vmax=45.0, palette=['blue', 'yellow', 'red'], label="LST (°C)")
                
                def fetch_url(img):
                    return img.getMapId(vis_params)['tile_fetcher'].url_format

            with ThreadPoolExecutor(max_workers=2) as executor:
                f_base = executor.submit(fetch_url, baseline_img)
                f_comp = executor.submit(fetch_url, comp_img)
                left_url = f_base.result()
                right_url = f_comp.result()

            m.split_map(left_layer=right_url, right_layer=left_url)
    except Exception as e:
        st.error(f"Error drawing map: {e}")

    # Render st_folium locally for tracking OR static DOM natively for security structurally scaling 
    if not st.session_state.get("map_locked", False):
        map_data = st_folium(m, height=750, use_container_width=True, returned_objects=["last_clicked"], key="main_map")
        
        if map_data and map_data.get("last_clicked"):
            if st.session_state["persistent_click"] != map_data["last_clicked"]:
                st.session_state["persistent_click"] = map_data["last_clicked"]
                new_c = map_data["last_clicked"]
                st.session_state["persistent_center"] = [new_c["lat"], new_c["lng"]]
                st.session_state["map_locked"] = True
                st.rerun()
    else:
        m.to_streamlit(height=750)

# --- Dynamic Legends Area ---
with col_stats:
    st.subheader("Interactive Indicator Legends")
    st.markdown("Use the classifications below to interpret the satellite spectral maps mathematically.")
    
    if layer_selection == "True Color":
        st.info("True Color visualizes standard human-visible satellite reflections completely unmodified.")
    else:
        st.markdown(f"#### Processing Output: {layer_selection}")
        st.info("Continuous mapping outputs are rendered directly into the viewport legend overlays.")

    st.markdown("---")
    st.markdown("### Upcoming Architecture")
    st.markdown("⚡ **Machine Learning Land Classification module** is scheduled for the next development sprint. This space will house dynamic random-forest classification breakdowns and pixel acreage.")
