import streamlit as st
import pandas as pd
import subprocess
import os
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# --- TRUCO DE RUTAS PARA SERVIDORES CLOUD ---
# Obligamos a Playwright a descargar y buscar el navegador en la carpeta '/tmp', 
# que tiene permisos abiertos de escritura en cualquier servidor Linux (Streamlit Cloud).
RUTA_TEMPORAL_NAVEGADOR = "/tmp/playwright-browsers"
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = RUTA_TEMPORAL_NAVEGADOR

# Configuración de la interfaz de Streamlit
st.set_page_config(page_title="Bot de Estadísticas Final", layout="wide")
st.title("📊 Monitor de Estadísticas en Vivo - Flashscore")
st.subheader("Análisis de métricas en tiempo real para decisiones de apuestas")

def extraer_estadisticas_partido(context, url_partido):
    """Navega a la URL del partido usando el contexto de Playwright y extrae los datos."""
    datos_stats = {}
    page = context.new_page()
    try:
        page.goto(url_partido, timeout=12000)
        
        boton_stats = page.locator("//button[@role='tab' and contains(., 'Estadísticas')]")
        boton_stats.wait_for(state="visible", timeout=4000)
        boton_stats.click()
        
        page.wait_for_timeout(1500)
        
        contenido = page.content()
        soup = BeautifulSoup(contenido, "html.parser")
        filas_estadisticas = soup.find_all("div", {"data-testid": "wcl-statistics"})
        
        for fila in filas_estadisticas:
            cat_div = fila.find("div", {"data-testid": "wcl-statistics-category"})
            if cat_div:
                categoria = cat_div.get_text(strip=True)
                
                home_val_div = fila.find("div", class_=lambda x: x and 'wcl-homeValue' in x)
                away_val_div = fila.find("div", class_=lambda x: x and 'wcl-awayValue' in x)
                
                val_home = home_val_div.get_text(strip=True) if home_val_div else "0"
                val_away = away_val_div.get_text(strip=True) if away_val_div else "0"
                
                datos_stats[f"{categoria} (L)"] = val_home
                datos_stats[f"{categoria} (V)"] = val_away
                
    except Exception:
        pass
    finally:
        page.close()
    return datos_stats

# --- PROCESO PRINCIPAL EN INTERFAZ ---

if st.button("🔄 Ejecutar Escaneo Completo y Generar Tabla"):
    # Verificar si Chromium ya está descargado en la carpeta temporal para no repetir el proceso
    if not os.path.exists(RUTA_TEMPORAL_NAVEGADOR):
        with st.spinner("Descargando Chromium de forma segura en el almacenamiento temporal..."):
            try:
                # Usamos '--with-deps' para asegurar que Linux instale cualquier librería gráfica faltante
                subprocess.run(["python", "-m", "playwright", "install", "chromium"], check=True)
                st.success("¡Navegador configurado con éxito!")
            except Exception as e:
                st.error(f"Error crítico instalando el navegador: {str(e)}")

    with st.spinner("Iniciando escáner... Conectando a la sección EN DIRECTO con Playwright..."):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
                
                page = context.new_page()
                page.goto("https://www.flashscore
