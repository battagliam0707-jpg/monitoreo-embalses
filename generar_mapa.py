import datetime
import re
import folium
from folium.plugins import MeasureControl
import pandas as pd
import requests
from bs4 import BeautifulSoup


# ==============================================================================
# EXTRACTORES DE DATOS POR PAÍS
# ==============================================================================
def obtener_datos_ons_brasil(codigo_ons):
    """Extractor para la API de Datos Abiertos del ONS Brasil."""
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
    """Scraper para la Entidad Binacional Yacyretá (Paraguay/Argentina)."""
    try:
        url = "https://www.eby.gov.py/category/nivelembalse/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            texto = soup.get_text()
            match = re.search(
                r"Nivel de Hoy.*?=\s*([\d\.\,]+)\s*mSNM", texto, re.IGNORECASE
            )
            if match:
                cota_actual = float(match.group(1).replace(",", "."))
                cota_min, cota_max = 76.0, 83.5
                pct = round(
                    ((cota_actual - cota_min) / (cota_max - cota_min)) * 100, 1
                )
                pct = max(0.0, min(100.0, pct))
                return (
                    pct,
                    datetime.date.today().strftime("%Y-%m-%d"),
                    f"EBY Boletín ({cota_actual} mSNM)",
                )
    except Exception as e:
        print(f"Error Scraping Yacyretá: {e}")
    return 68.5, datetime.date.today().strftime("%Y-%m-%d"), "EBY (Estimación)"


def obtener_datos_hidroituango_colombia():
    """Extractor para Hidroituango vía XM (Administrador Mercado de Energía Colombia)."""
    try:
        url_xm = "https://api.xm.com.co/servicios-publicos/v1/indicadores/volumen-util-reservorio"
        resp = requests.get(url_xm, timeout=6)
        if resp.status_code == 200:
            datos = resp.json().get("datos", [])
            for d in datos:
                if "
