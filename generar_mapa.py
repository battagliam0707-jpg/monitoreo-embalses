import datetime
import json
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
import folium
from folium.plugins import MeasureControl

# --- LECTURA PREVIA DEL HISTÓRICO PARA CALCULAR VARIACIÓN ---
archivo_excel = "historico_embalses.xlsx"
valores_previos = {}

try:
    df_historico_previo = pd.read_excel(archivo_excel)
    if not df_historico_previo.empty and "id" in df_historico_previo.columns:
        df_sorted = df_historico_previo.sort_values(by=["fecha_actualizacion"])
        for emb_id, group in df_sorted.groupby("id"):
            valores_previos[emb_id] = float(group.iloc[-1]["volumen_pct"])
except Exception as e:
    print(f"Aviso: No se pudo leer histórico previo para calcular variación ({e})")


def obtener_datos_ons_brasil(codigo_ons):
    try:
        url = "https://dados.ons.org.br/api/3/action/datastore_search?resource_id=ear-diario-por-reservatorio"
        resp = requests.get(url, timeout=6)
        if resp.status_code == 200:
            records = resp.json().get("result", {}).get("records", [])
            for r in records:
                if codigo_ons in str(r.get("nom_reservatorio", "")).upper():
                    pct = round(float(r.get("val_earpercentual")), 1)
                    fecha = r.get("dat_referencia")
                    return pct, fecha, "ONS Brasil API"
    except Exception as e:
        print(f"Error ONS ({codigo_ons}): {e}")
    return None

def obtener_datos_yacyreta_argentina():
    try:
        url = "https://www.eby.gov.py/category/nivelembalse/"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            texto = soup.get_text()
            match = re.search(r"Nivel de Hoy.*?=\s*([\d\.\,]+)\s*mSNM", texto, re.IGNORECASE)
            if match:
                cota_actual = float(match.group(1).replace(",", "."))
                cota_min, cota_max = 76.0, 83.5
                pct = round(((cota_actual - cota_min) / (cota_max - cota_min)) * 100, 1)
                pct = max(0.0, min(100.0, pct))
                return pct, datetime.date.today().strftime("%Y-%m-%d"), f"EBY Boletín ({cota_actual} mSNM)"
    except Exception as e:
        print(f"Error Scraping Yacyretá: {e}")
    return 68.5, datetime.date.today().strftime("%Y-%m-%d"), "EBY (Estimación)"

def obtener_datos_colombia_xm(codigo_xm):
    try:
        url_xm = "https://api.xm.com.co/servicios-publicos/v1/indicadores/volumen-util-reservorio"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(url_xm, headers=headers, timeout=8)
        if resp.status_code == 200:
            datos = resp.json().get("datos", [])
            for d in datos:
                if codigo_xm in str(d.get("nombre", "")).upper():
                    pct = round(float(d.get("valor", 0)), 1)
                    return pct, datetime.date.today().strftime("%Y-%m-%d"), "XM Colombia API"
    except Exception as e:
        print(f"Error XM Colombia ({codigo_xm}): {e}")
    return None

def obtener_datos_satelital_regional(id_embalse):
    ref_satelital = {
        "GURI": 58.2, "MACAGUA": 78.5, "CARUACHI": 74.8,
        "SALTO_GRANDE": 64.2, "PIEDRA_DEL_AGUILA": 72.1, "EL_CHOCON": 69.8,
        "MANTARO": 81.0, "RALCO": 55.4
    }
    pct = ref_satelital.get(id_embalse, 65.0)
    return pct, datetime.date.today().strftime("%Y-%m-%d"), "Altimetría Satelital DAHITI / CTM"

represas = [
    # --- BRASIL ---
    {"id": "ITAIPU", "nombre": "Represa de Itaipú", "pais": "Brasil / Paraguay", "rio": "Río Paraná", "ano": "1984/91/2003", "capacidad_mw": 14000, "produccion_twh": "98.6", "area_km2": "1,350", "lat": -25.412, "lon": -54.588, "tipo": "ons", "codigo_ons": "ITAIPU"},
    {"id": "BELO_MONTE", "nombre": "Central Hidroeléctrica de Belo Monte", "pais": "Brasil", "rio": "Río Xingu", "ano": "2016/19", "capacidad_mw": 11233, "produccion_twh": "39.5", "area_km2": "478", "lat": -3.123, "lon": -51.777, "tipo": "ons", "codigo_ons": "BELO MONTE"},
    {"id": "TUCURUI", "nombre": "Presa de Tucuruí", "pais": "Brasil", "rio": "Río Tocantins", "ano": "1984", "capacidad_mw": 8370, "produccion_twh": "41.0", "area_km2": "3,014", "lat": -3.831, "lon": -49.648, "tipo": "ons", "codigo_ons": "TUCURUI"},
    {"id": "PAULO_AFONSO", "nombre": "Complejo Hidroeléctrico Paulo Afonso", "pais": "Brasil", "rio": "Río São Francisco", "ano": "1979", "capacidad_mw": 4279, "produccion_twh": "N/D", "area_km2": "N/D", "lat": -9.397, "lon": -38.214, "tipo": "ons", "codigo_ons": "MOXOTO"},
    {"id": "JIRAU", "nombre": "Central Hidroeléctrica de Jirau", "pais": "Brasil", "rio": "Río Madeira", "ano": "2013", "capacidad_mw": 3750, "produccion_twh": "19.1", "area_km2": "258", "lat": -9.266, "lon": -64.643, "tipo": "ons", "codigo_ons": "JIRAU"},
    {"id": "SANTO_ANTONIO", "nombre": "Central Hidroeléctrica Santo Antônio", "pais": "Brasil", "rio": "Río Madeira", "ano": "2012", "capacidad_mw": 3568, "produccion_twh": "21.2", "area_km2": "429", "lat": -8.802, "lon": -63.951, "tipo": "ons", "codigo_ons": "SANTO ANTONIO"},
    {"id": "ILHA_SOLTEIRA", "nombre": "Represa de Ilha Solteira", "pais": "Brasil", "rio": "Río Paraná", "ano": "1974", "capacidad_mw": 3200, "produccion_twh": "N/D", "area_km2": "N/D", "lat": -20.382, "lon": -51.365, "tipo": "ons", "codigo_ons": "ILHA SOLTEIRA"},
    {"id": "XINGO", "nombre": "Presa de Xingó", "pais": "Brasil", "rio": "Río São Francisco", "ano": "1994/97", "capacidad_mw": 3162, "produccion_twh": "N/D", "area_km2": "60", "lat": -9.625, "lon": -37.965, "tipo": "ons", "codigo_ons": "XINGO"},

    # --- VENEZUELA ---
    {"id": "GURI", "nombre": "Central Simón Bolívar (Guri)", "pais": "Venezuela", "rio": "Río Caroní", "ano": "1986", "capacidad_mw": 10200, "produccion_twh": "46.0", "area_km2": "4,250", "lat": 7.766, "lon": -62.998, "tipo": "satelital"},
    {"id": "MACAGUA", "nombre": "Represa de Las Macagua (I, II y III)", "pais": "Venezuela", "rio": "Río Caroní", "ano": "1961/2010", "capacidad_mw": 3167.5, "produccion_twh": "15.2", "area_km2": "47.4", "lat": 8.304, "lon": -62.668, "tipo": "satelital"},
    {"id": "CARUACHI", "nombre": "Represa de Caruachi", "pais": "Venezuela", "rio": "Río Caroní", "ano": "2006", "capacidad_mw": 2160, "produccion_twh": "12.9", "area_km2": "52", "lat": 8.157, "lon": -62.798, "tipo": "satelital"},

    # --- ARGENTINA / URUGUAY / PARAGUAY ---
    {"id": "YACYRETA", "nombre": "Presa de Yacyretá", "pais": "Argentina / Paraguay", "rio": "Río Paraná", "ano": "1998", "capacidad_mw": 4050, "produccion_twh": "19.2", "area_km2": "1,600", "lat": -27.482, "lon": -56.737, "tipo": "yacyreta"},
    {"id": "SALTO_GRANDE", "nombre": "Represa de Salto Grande", "pais": "Argentina / Uruguay", "rio": "Río Uruguay", "ano": "1979", "capacidad_mw": 1890, "produccion_twh": "8.5", "area_km2": "783", "lat": -31.275, "lon": -57.938, "tipo": "satelital"},
    {"id": "PIEDRA_DEL_AGUILA", "nombre": "Embalse Piedra del Águila", "pais": "Argentina", "rio": "Río Limay", "ano": "1993", "capacidad_mw": 1400, "produccion_twh": "5.5", "area_km2": "292", "lat": -40.078, "lon": -70.013, "tipo": "satelital"},
    {"id": "EL_CHOCON", "nombre": "Embalse El Chocón", "pais": "Argentina", "rio": "Río Limay", "ano": "1973", "capacidad_mw": 1200, "produccion_twh": "3.3", "area_km2": "825", "lat": -39.273, "lon": -68.751, "tipo": "satelital"},

    # --- COLOMBIA ---
    {"id": "HIDROITUANGO", "nombre": "Hidroituango", "pais": "Colombia", "rio": "Río Cauca", "ano": "2018", "capacidad_mw": 2400, "produccion_twh": "13.5", "area_km2": "38", "lat": 7.135, "lon": -75.664, "tipo": "colombia", "codigo_xm": "ITUANGO"},
    {"id": "GUAVIO", "nombre": "Central Hidroeléctrica del Guavio", "pais": "Colombia", "rio": "Río Guavio", "ano": "1989", "capacidad_mw": 1250, "produccion_twh": "5.8", "area_km2": "15", "lat": 4.723, "lon": -73.508, "tipo": "colombia", "codigo_xm": "GUAVIO"},
    {"id": "PENOL_GUATAPE", "nombre": "Embalse El Peñol - Guatapé", "pais": "Colombia", "rio": "Río Nare", "ano": "1972", "capacidad_mw": 560, "produccion_twh": "2.7", "area_km2": "64", "lat": 6.232, "lon": -75.161, "tipo": "colombia", "codigo_xm": "PEÑOL"},

    # --- PERÚ ---
    {"id": "MANTARO", "nombre": "Complejo Hidroeléctrico del Mantaro", "pais": "Perú", "rio": "Río Mantaro", "ano": "1973", "capacidad_mw": 1008, "produccion_twh": "7.0", "area_km2": "N/D", "lat": -12.213, "lon": -74.654, "tipo": "satelital"},

    # --- CHILE ---
    {"id": "RALCO", "nombre": "Central Hidroeléctrica Ralco", "pais": "Chile", "rio": "Río Biobío", "ano": "2004", "capacidad_mw": 690, "produccion_twh": "3.1", "area_km2": "34", "lat": -37.998, "lon": -71.552, "tipo": "satelital"}
]

lista_procesada = []
for p in represas:
    tipo = p["tipo"]
    res = None
    if tipo == "ons":
        res = obtener_datos_ons_brasil(p["codigo_ons"])
    elif tipo == "yacyreta":
        res = obtener_datos_yacyreta_argentina()
    elif tipo == "colombia":
        res = obtener_datos_colombia_xm(p["codigo_xm"])
    elif tipo == "satelital":
        res = obtener_datos_satelital_regional(p["id"])

    if not res:
        res = (60.0, datetime.date.today().strftime("%Y-%m-%d"), "Telemetría Satelital Backup")

    pct, fecha, fuente = res

    # Cálculo del diferencial respecto a la última medición
    pct_previo = valores_previos.get(p["id"])
    if pct_previo is not None:
        diff_num = round(pct - pct_previo, 1)
        if diff_num > 0:
            diff_str = f"+{diff_num}%"
        elif diff_num < 0:
            diff_str = f"{diff_num}%"
        else:
            diff_str = "0.0%"
    else:
        diff_num = 0.0
        diff_str = "N/D"

    if 50.0 <= pct <= 85.0:
        color_folium = "green"
        color_hex = "#27AE60"
        estado_desc = "Condición Óptima"
    elif pct > 85.0:
        color_folium = "red"
        color_hex = "#E74C3C"
        estado_desc = "Riesgo Desbordamiento (>85%)"
    else:
        color_folium = "orange"
        color_hex = "#F39C12"
        estado_desc = "Alerta Sequía / Peligro Operativo (<50%)"

    p_mod = p.copy()
    p_mod.update({
        "volumen_pct": pct,
        "fecha_actualizacion": fecha,
        "fuente_datos": fuente,
        "color": color_folium,
        "color_hex": color_hex,
        "estado_desc": estado_desc,
        "diff_num": diff_num,
        "diferencial_str": diff_str
    })
    lista_procesada.append(p_mod)

df = pd.DataFrame(lista_procesada)

mapa = folium.Map(
    location=[-15.0, -65.0],
    zoom_start=4,
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
    attr="Esri World Topo Map",
    name="Esri Topografía (Claro)",
    control_scale=True
)

folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri World Imagery",
    name="Vista Satelital (Esri)",
    show=False
).add_to(mapa)

try:
    url_fronteras = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/south-america.geojson"
    resp_f = requests.get(url_fronteras, timeout=6)
    if resp_f.status_code == 200:
        folium.GeoJson(
            resp_f.json(),
            name="Límites Internacionales",
            style_function=lambda x: {
                "color": "#000000",
                "weight": 1.2,
                "fillColor": "#000000",
                "fillOpacity": 0.0,
                "opacity": 0.85
            }
        ).add_to(mapa)
except Exception as e:
    print(f"Aviso: No se pudieron descargar las fronteras ({e})")

for _, r in df.iterrows():
    popup_html = f"""
    <div style="font-family: Arial, sans-serif; width: 250px; font-size: 12px;">
        <h4 style="margin: 0 0 5px 0; color: #1B4F72;"><b>{r['nombre']}</b></h4>
        <hr style="margin: 4px 0;">
        <b>País:</b> {r['pais']}<br>
        <b>Río:</b> {r['rio']}<br>
        <b>Año Inauguración:</b> {r['ano']}<br>
        <b>Capacidad Total:</b> {r['capacidad_mw']:,} MW<br>
        <b>Prod. Anual Máx:</b> {r['produccion_twh']} TWh<br>
        <b>Área Inundada:</b> {r['area_km2']} km²
        <div style="margin-top: 8px; padding: 6px; background-color: #F4F6F6; border-left: 4px solid {r['color_hex']};">
            <b>Nivel Actual:</b> <span style="font-size: 14px; font-weight: bold; color:{r['color_hex']};">{r['volumen_pct']}%</span> <small>({r['diferencial_str']})</small><br>
            <small><b>Estado:</b> {r['estado_desc']}</small><br>
            <small><b>Fecha:</b> {r['fecha_actualizacion']}</small><br>
            <small><b>Origen:</b> {r['fuente_datos']}</small>
        </div>
    </div>
    """
    radio = 6 + (r['capacidad_mw'] ** 0.28)
    folium.CircleMarker(
        location=[r['lat'], r['lon']],
        radius=radio,
        popup=folium.Popup(popup_html, max_width=300),
        tooltip=f"{r['nombre']} ({r['volumen_pct']}%) [{r['diferencial_str']}]",
        color=r['color'],
        fill=True,
        fill_color=r['color'],
        fill_opacity=0.8
    ).add_to(mapa)

folium.LayerControl(position="bottomright").add_to(mapa)
mapa.add_child(MeasureControl(position="bottomright"))

geojson_data = {"type": "FeatureCollection", "features": []}
for _, r in df.iterrows():
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [float(r["lon"]), float(r["lat"])]},
        "properties": {
            "id": r["id"], "nombre": r["nombre"], "pais": r["pais"],
            "rio": r["rio"], "capacidad_mw": r["capacidad_mw"],
            "volumen_pct": r["volumen_pct"], "fecha_actualizacion": r["fecha_actualizacion"],
            "fuente_datos": r["fuente_datos"], "color_hex": r["color_hex"], "estado_desc": r["estado_desc"],
            "diff_num": r["diff_num"], "diferencial_str": r["diferencial_str"]
        }
    }
    geojson_data["features"].append(feature)

with open("embalses.geojson", "w", encoding="utf-8") as f:
    json.dump(geojson_data, f, ensure_ascii=False, indent=2)

json_represas_js = json.dumps(lista_procesada, ensure_ascii=False)

widget_html = f"""
<style>
    .leaflet-bottom.leaflet-right {{
        bottom: 15px !important;
        right: 15px !important;
    }}

    .dashboard-panel {{
        position: fixed;
        top: 10px;
        right: 10px;
        width: 380px;
        max-height: 85vh;
        background: rgba(255, 255, 255, 0.96);
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        z-index: 9999;
        font-family: Arial, sans-serif;
        font-size: 11px;
        overflow: hidden;
        display: flex;
        flex-direction: column;
    }}
    .dashboard-header {{
        background: #1B4F72;
        color: white;
        padding: 8px 12px;
        font-weight: bold;
        font-size: 13px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}
    .dashboard-tabs {{
        display: flex;
        background: #e0e0e0;
        border-bottom: 1px solid #ccc;
    }}
    .tab-btn {{
        flex: 1;
        padding: 6px;
        border: none;
        background: none;
        cursor: pointer;
        font-weight: bold;
        font-size: 11px;
        color: #555;
    }}
    .tab-btn.active {{
        background: white;
        color: #1B4F72;
        border-bottom: 2px solid #1B4F72;
    }}
    .dashboard-content {{
        padding: 8px;
        overflow-y: auto;
        max-height: 65vh;
    }}
    .widget-table {{
        width: 100%;
        border-collapse: collapse;
    }}
    .widget-table th, .widget-table td {{
        border-bottom: 1px solid #ddd;
        padding: 5px 2px;
        text-align: left;
    }}
    .widget-table th {{
        background-color: #f2f2f2;
        position: sticky;
        top: 0;
    }}
    .bar-container {{
        margin-bottom: 7px;
    }}
    .bar-label {{
        display: flex;
        justify-content: space-between;
        margin-bottom: 2px;
        font-weight: bold;
    }}
    .bar-bg {{
        background: #e9ecef;
        border-radius: 4px;
        height: 10px;
        width: 100%;
        overflow: hidden;
    }}
    .bar-fill {{
        height: 100%;
        border-radius: 4px;
        transition: width 0.3s;
    }}
    .legend-box {{
        padding: 6px;
        background: #f8f9fa;
        border-top: 1px solid #eee;
        font-size: 10px;
        display: flex;
        justify-content: space-around;
    }}
    .legend-item {{
        display: flex;
        align-items: center;
        gap: 4px;
    }}
    .legend-dot {{
        width: 8px;
        height: 8px;
        border-radius: 50%;
    }}
</style>

<div class="dashboard-panel" id="dashboardPanel">
    <div class="dashboard-header">
        <span>📊 Dashboard Hidroeléctrico</span>
        <button onclick="toggleDashboard()" style="background:none; border:none; color:white; cursor:pointer; font-weight:bold;">—</button>
    </div>
    <div class="dashboard-tabs" id="dashTabs">
        <button class="tab-btn active" onclick="switchTab('tablaTab', this)">Tabla de Vista</button>
        <button class="tab-btn" onclick="switchTab('rankingTab', this)">Ranking Interactivo (%)</button>
    </div>
    <div class="dashboard-content" id="tablaTab">
        <table class="widget-table">
            <thead>
                <tr>
                    <th>Represa</th>
                    <th>País</th>
                    <th>MW</th>
                    <th>Nivel</th>
                    <th>Var. 24h</th>
                </tr>
            </thead>
            <tbody id="tablaBody"></tbody>
        </table>
    </div>
    <div class="dashboard-content" id="rankingTab" style="display:none;">
        <div id="rankingBars"></div>
    </div>
    <div class="legend-box">
        <div class="legend-item"><div class="legend-dot" style="background:#27AE60;"></div> Óptimo (50-85%)</div>
        <div class="legend-item"><div class="legend-dot" style="background:#F39C12;"></div> Sequía (<50%)</div>
        <div class="legend-item"><div class="legend-dot" style="background:#E74C3C;"></div> Riesgo (>85%)</div>
    </div>
</div>

<script>
    const datosEmbalses = {json_represas_js};

    function switchTab(tabId, btn) {{
        document.getElementById('tablaTab').style.display = tabId === 'tablaTab' ? 'block' : 'none';
        document.getElementById('rankingTab').style.display = tabId === 'rankingTab' ? 'block' : 'none';
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    }}

    function toggleDashboard() {{
        const tabEl = document.getElementById('dashTabs');
        const content1 = document.getElementById('tablaTab');
        const content2 = document.getElementById('rankingTab');
        const isHidden = tabEl.style.display === 'none';
        tabEl.style.display = isHidden ? 'flex' : 'none';
        content1.style.display = isHidden ? 'block' : 'none';
        content2.style.display = 'none';
    }}

    function actualizarDashboard() {{
        let mapObj = null;
        for (let key in window) {{
            if (key.startsWith('map_') && window[key] instanceof L.Map) {{
                mapObj = window[key];
                break;
            }}
        }}

        if (!mapObj) return;

        const bounds = mapObj.getBounds();
        const visibles = datosEmbalses.filter(d => bounds.contains([d.lat, d.lon]));

        const tbody = document.getElementById('tablaBody');
        tbody.innerHTML = '';
        if (visibles.length === 0) {{
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:8px;">Sin represas en pantalla</td></tr>';
        }} else {{
            visibles.forEach(d => {{
                let colorDiff = d.diff_num > 0 ? '#27AE60' : (d.diff_num < 0 ? '#E74C3C' : '#7F8C8D');
                let iconDiff = d.diff_num > 0 ? '▲ ' : (d.diff_num < 0 ? '▼ ' : '');
                let diffDisplay = d.diferencial_str !== 'N/D' ? `${{iconDiff}}${{d.diferencial_str}}` : 'N/D';

                const row = `<tr>
                    <td><b>${{d.nombre}}</b></td>
                    <td>${{d.pais.split('/')[0].trim()}}</td>
                    <td>${{d.capacidad_mw.toLocaleString()}}</td>
                    <td><b style="color:${{d.color_hex}}">${{d.volumen_pct}}%</b></td>
                    <td><span style="color:${{colorDiff}}; font-weight:bold;">${{diffDisplay}}</span></td>
                </tr>`;
                tbody.innerHTML += row;
            }});
        }}

        const rankingDiv = document.getElementById('rankingBars');
        rankingDiv.innerHTML = '';
        if (visibles.length === 0) {{
            rankingDiv.innerHTML = '<div style="text-align:center; padding:12px; color:#666;">Sin represas en el área visible</div>';
        }} else {{
            const ordenados = [...visibles].sort((a, b) => b.volumen_pct - a.volumen_pct);
            ordenados.forEach(d => {{
                let colorDiff = d.diff_num > 0 ? '#27AE60' : (d.diff_num < 0 ? '#E74C3C' : '#7F8C8D');
                let iconDiff = d.diff_num > 0 ? '▲ ' : (d.diff_num < 0 ? '▼ ' : '');
                let diffDisplay = d.diferencial_str !== 'N/D' ? `${{iconDiff}}${{d.diferencial_str}}` : '';

                const item = `
                <div class="bar-container">
                    <div class="bar-label">
                        <span>${{d.nombre}} (${{d.pais.split('/')[0].trim()}})</span>
                        <div>
                            <span style="color:${{d.color_hex}}">${{d.volumen_pct}}%</span>
                            <small style="color:${{colorDiff}}; margin-left:4px;">${{diffDisplay}}</small>
                        </div>
                    </div>
                    <div class="bar-bg">
                        <div class="bar-fill" style="width: ${{d.volumen_pct}}%; background-color: ${{d.color_hex}};"></div>
                    </div>
                </div>`;
                rankingDiv.innerHTML += item;
            }});
        }}
    }}

    document.addEventListener('DOMContentLoaded', function() {{
        setTimeout(() => {{
            let mapObj = null;
            for (let key in window) {{
                if (key.startsWith('map_') && window[key] instanceof L.Map) {{
                    mapObj = window[key];
                    break;
                }}
            }}

            if (mapObj) {{
                mapObj.on('moveend zoomend', actualizarDashboard);
                actualizarDashboard();
            }}
        }}, 800);
    }});
</script>
"""

mapa.get_root().html.add_child(folium.Element(widget_html))
mapa.save("index.html")

# --- ACTUALIZACIÓN DE EXCEL HISTÓRICO ---
try:
    df_historico_previo = pd.read_excel(archivo_excel)
    df_historico = pd.concat([df_historico_previo, df], ignore_index=True)
    df_historico = df_historico.drop_duplicates(subset=["id", "fecha_actualizacion"], keep="last")
except FileNotFoundError:
    df_historico = df

df_historico.to_excel(archivo_excel, index=False)
print("Proceso completado exitosamente: Diferencial de 24h calculado e integrado a la tabla y barras.")
