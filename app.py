import streamlit as st
from streamlit_folium import st_folium
import ee
import datetime
import folium.plugins
import leafmap.foliumap as foliumap
import requests
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

catalog_mode = st.sidebar.radio("Processing Modules", [
    "Temporal Indices Comparison",
    "Machine Learning Land Classification"
])

# --- Main App Dashboard ---
st.sidebar.markdown("---")
run_ml = False

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
            
    current_y = datetime.date.today().year

    if catalog_mode == "Temporal Indices Comparison":
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
    else:
        st.subheader("Machine Learning Setup")
        ml_year = st.selectbox("Classification Year", range(2017, current_y + 1), index=max(0, current_y - 2017))
        ml_trees = st.slider("Random Forest Trees", min_value=10, max_value=150, value=30, step=10)
        ml_samples_per_class = st.slider("Samples Per Class", min_value=20, max_value=200, value=40, step=10)
        run_ml = st.button("Run / Refresh Classification", use_container_width=True)

    if catalog_mode == "Temporal Indices Comparison":
        st.caption("Indices and processing documentation is available in the right panel.")

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
        qa = image.select('QA60')
        cloud_bit_mask = 1 << 10
        cirrus_bit_mask = 1 << 11
        mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
            qa.bitwiseAnd(cirrus_bit_mask).eq(0)
        )
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


def mask_s2_clouds(image):
    qa = image.select("QA60")
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    return image.updateMask(mask).divide(10000)


def classify_land_cover_rf(roi, year, trees, samples_per_class):
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    bands = ["B2", "B3", "B4", "B8", "B11"]

    img = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi)
        .filterDate(start, end)
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", 30))
        .limit(80, "CLOUDY_PIXEL_PERCENTAGE")
        .map(mask_s2_clouds)
        .median()
        .select(bands)
        .clip(roi)
    )

    class_values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100]
    remap_values = ee.List.sequence(0, 10)
    label = "lc"

    lc = (
        ee.Image("ESA/WorldCover/v100/2020")
        .remap(class_values, remap_values)
        .rename(label)
        .toByte()
        .clip(roi)
    )

    sample = img.addBands(lc).stratifiedSample(
        numPoints=samples_per_class,
        classBand=label,
        region=roi,
        scale=10,
        geometries=True,
    )
    sample = sample.randomColumn()
    training_sample = sample.filter("random <= 0.8")
    validation_sample = sample.filter("random > 0.8")

    classifier = ee.Classifier.smileRandomForest(numberOfTrees=trees).train(
        features=training_sample,
        classProperty=label,
        inputProperties=img.bandNames(),
    )

    classified = img.classify(classifier).clip(roi)
    validated = validation_sample.classify(classifier)
    error_matrix = validated.errorMatrix(label, "classification")

    metrics = {
        "overall_accuracy": ee.Number(error_matrix.accuracy()).getInfo(),
        "kappa": ee.Number(error_matrix.kappa()).getInfo(),
        "training_points": training_sample.size().getInfo(),
        "validation_points": validation_sample.size().getInfo(),
    }
    return classified, img, metrics

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_unesco_sites():
    sites = []
    limit = 200
    offset = 0
    select_fields = "id_no,name_en,name_fr,states_names,coordinates"

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

    # Deduplicate and sort for stable UI ordering.
    deduped = {}
    for site in sites:
        deduped[site["id"]] = site
    return sorted(deduped.values(), key=lambda s: (s["country"], s["site"]))


# --- Top App Layout (Map & Classification) ---
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
        st.markdown("Select a UNESCO place above, or click the map to evaluate a 10km UNESCO Heritage region.")
    else:
        st.markdown("Observation Mode: The map is locked for stable UI interaction.")
        if st.button("Unlock & Select New Region", use_container_width=True):
            st.session_state["map_locked"] = False
            st.session_state["persistent_click"] = None
            st.session_state["selected_unesco_site_id"] = None
            st.rerun()
            
    click_pt = st.session_state["persistent_click"]
    
    # Initialize Map preserving the exact local user viewpoint safely
    m = foliumap.Map(center=st.session_state["persistent_center"], zoom=st.session_state["persistent_zoom"], basemap=DEFAULT_BASEMAP)
        
    folium.plugins.Geocoder().add_to(m)
    ml_metrics = None
    processed_ml = False

    if catalog_mode == "Machine Learning Land Classification" and click_pt:
        ml_key = (
            round(click_pt["lat"], 5),
            round(click_pt["lng"], 5),
            int(ml_year),
            int(ml_trees),
            int(ml_samples_per_class),
        )
        cached_ml = st.session_state.get("ml_cache")
        needs_refresh = run_ml or (not cached_ml) or (cached_ml.get("key") != ml_key)

        if needs_refresh and run_ml:
            pt = ee.Geometry.Point([click_pt["lng"], click_pt["lat"]])
            roi = pt.buffer(10000).bounds()
            try:
                with st.spinner("Training Random Forest classifier and generating land cover map..."):
                    classified_img, sentinel_img, ml_metrics = classify_land_cover_rf(
                        roi=roi,
                        year=ml_year,
                        trees=ml_trees,
                        samples_per_class=ml_samples_per_class,
                    )
                st.session_state["ml_cache"] = {
                    "key": ml_key,
                    "classified_img": classified_img,
                    "sentinel_img": sentinel_img,
                    "metrics": ml_metrics,
                }
                cached_ml = st.session_state["ml_cache"]
            except Exception as ml_err:
                st.error(f"ML classification failed: {ml_err}")

        if cached_ml and cached_ml.get("key") == ml_key:
            ml_metrics = cached_ml["metrics"]
            rgb_vis = {"bands": ["B4", "B3", "B2"], "min": 0.02, "max": 0.35}
            m.add_ee_layer(cached_ml["sentinel_img"], rgb_vis, "Sentinel-2 Composite", shown=False)
            lc_palette = [
                "#419bdf", "#397d49", "#88b053", "#7a87c6", "#e49635",
                "#dfc35a", "#c4281b", "#a59b8f", "#b39fe1", "#e86d9f", "#7bc7ff",
            ]
            lc_vis = {"min": 0, "max": 10, "palette": lc_palette}
            m.add_ee_layer(cached_ml["classified_img"], lc_vis, "RF Land Cover")
            processed_ml = True
        else:
            st.info("Click `Run / Refresh Classification` to prepare land-cover output for this location.")
    
    try:
        if not click_pt:
            st.info("Awaiting interaction. Maps will load satellite data only after a coordinate is selected.")
        elif catalog_mode == "Temporal Indices Comparison":
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
                elif layer_selection == "NDMI":
                    vis_params = {'bands': ['NDMI'], 'min': -1.0, 'max': 1.0, 'palette': ['brown', 'yellow', 'blue']}
                    m.add_colormap(width=4.0, height=0.25, vmin=-1.0, vmax=1.0, palette=['brown', 'yellow', 'blue'], label="NDMI Index")
                elif layer_selection == "NDWI":
                    vis_params = {'bands': ['NDWI'], 'min': -1.0, 'max': 1.0, 'palette': ['brown', 'white', 'blue']}
                    m.add_colormap(width=4.0, height=0.25, vmin=-1.0, vmax=1.0, palette=['brown', 'white', 'blue'], label="NDWI Index")
                elif layer_selection == "MNDWI":
                    vis_params = {'bands': ['MNDWI'], 'min': -1.0, 'max': 1.0, 'palette': ['brown', 'white', 'cyan']}
                    m.add_colormap(width=4.0, height=0.25, vmin=-1.0, vmax=1.0, palette=['brown', 'white', 'cyan'], label="MNDWI Index")
                elif layer_selection == "EVI":
                    vis_params = {'bands': ['EVI'], 'min': -1.0, 'max': 1.0, 'palette': ['red', 'yellow', 'green']}
                    m.add_colormap(width=4.0, height=0.25, vmin=-1.0, vmax=1.0, palette=['red', 'yellow', 'green'], label="EVI Index")
                elif layer_selection == "SAVI":
                    vis_params = {'bands': ['SAVI'], 'min': -1.0, 'max': 1.0, 'palette': ['red', 'yellow', 'green']}
                    m.add_colormap(width=4.0, height=0.25, vmin=-1.0, vmax=1.0, palette=['red', 'yellow', 'green'], label="SAVI Index")
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
    if catalog_mode == "Temporal Indices Comparison":
        st.subheader("Interactive Indicator Legends")
        st.markdown("Use the classifications below to interpret the satellite spectral maps mathematically.")

        if layer_selection == "True Color":
            st.info("True Color visualizes standard human-visible satellite reflections completely unmodified.")
        else:
            st.markdown(f"#### Processing Output: {layer_selection}")
            st.info("Continuous mapping outputs are rendered directly into the viewport legend overlays.")

        st.markdown("---")
        st.markdown("### Machine Learning Module")
        st.markdown("Switch to **Machine Learning Land Classification** in the sidebar to run Random Forest land-cover mapping.")
    else:
        st.subheader("Machine Learning Results")
        st.markdown("Random Forest classification is trained from Sentinel-2 predictors and ESA WorldCover labels in the selected 10 km ROI.")
        st.markdown("#### Class Legend (WorldCover)")
        st.markdown(
            "0 Water, 1 Trees, 2 Grass, 3 Flooded vegetation, 4 Cropland, "
            "5 Built-up, 6 Bare/sparse, 7 Snow/ice, 8 Permanent wetlands, "
            "9 Mangroves, 10 Moss/lichen"
        )
        if ml_metrics:
            st.markdown("---")
            st.metric("Overall Accuracy", f"{ml_metrics['overall_accuracy']:.2%}")
            st.metric("Kappa", f"{ml_metrics['kappa']:.3f}")
            st.caption(
                f"Training samples: {ml_metrics['training_points']} | "
                f"Validation samples: {ml_metrics['validation_points']}"
            )
        else:
            st.info("No prepared ML output yet. Choose a UNESCO site and click `Run / Refresh Classification` in the sidebar.")

    with st.expander("Indices and Processing Documentation", expanded=False):
        st.markdown(
            """
            **Temporal index formulas**
            - NDVI: `(NIR - RED) / (NIR + RED)`
            - NDBI: `(SWIR1 - NIR) / (SWIR1 + NIR)`
            - NDMI: `(NIR - SWIR1) / (NIR + SWIR1)`
            - NDWI (McFeeters): `(GREEN - NIR) / (GREEN + NIR)`
            - MNDWI (Xu): `(GREEN - SWIR1) / (GREEN + SWIR1)`
            - EVI: `2.5 * (NIR - RED) / (NIR + 6*RED - 7.5*BLUE + 1)`
            - SAVI (L=0.5): `1.5 * (NIR - RED) / (NIR + RED + 0.5)`

            **Band mapping**
            - Sentinel-2: `NIR=B8`, `RED=B4`, `GREEN=B3`, `BLUE=B2`, `SWIR1=B11`
            - Landsat 8/9: `NIR=SR_B5`, `RED=SR_B4`, `GREEN=SR_B3`, `BLUE=SR_B2`, `SWIR1=SR_B6`

            **Machine Learning land-cover pipeline**
            1. Build cloud-masked Sentinel-2 annual composite in selected UNESCO ROI.
            2. Use ESA WorldCover classes as training labels.
            3. Stratified sampling by class.
            4. Train `smileRandomForest`.
            5. Validate with held-out samples (overall accuracy + kappa).
            6. Render predicted land-cover map.
            """
        )

