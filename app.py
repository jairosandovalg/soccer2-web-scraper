import streamlit as st
import pandas as pd
import asyncio
import os
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# --- CONFIGURACIÓN INICIAL Y DEPENDENCIAS ---
st.set_page_config(page_title="Bot de Estadísticas Final", layout="wide")

@st.cache_resource
def instalar_dependencias_playwright():
    """Asegura que los binarios de Chromium estén instalados en el servidor de Streamlit."""
    with st.spinner("Configurando entorno del navegador (esto puede tardar un momento la primera vez)..."):
        os.system("playwright install chromium")

# Ejecutar la instalación automática del navegador antes de iniciar el flujo
instalar_dependencias_playwright()

# --- INTERFAZ DE USUARIO ---
st.title("📊 Monitor de Estadísticas en Vivo - Flashscore")
st.subheader("Análisis de métricas en tiempo real para decisiones de apuestas")

# Control del tiempo de actualización en la barra lateral
INTERVALO = st.sidebar.slider("⏱️ Intervalo de actualización automática (segundos)", 30, 300, 60)

# --- FUNCIONES DE EXTRACCIÓN (SCRAPING ASÍNCRONO) ---

async def extraer_estadisticas_partido(context, url_partido):
    """Abre una pestaña en segundo plano, extrae las estadísticas y la cierra."""
    datos_stats = {}
    page = await context.new_page()
    try:
        # Navegar al partido con un tiempo límite de 10 segundos
        await page.goto(url_partido, timeout=10000)
        
        # Localizar el botón de 'Estadísticas' y hacer clic de forma segura
        boton_stats = page.locator("//button[@role='tab' and contains(., 'Estadísticas')]")
        await boton_stats.wait_for(state="visible", timeout=4000)
        await boton_stats.click()
        
        # Breve espera para que terminen de renderizarse las barras internas del HTML
        await page.wait_for_timeout(1200)
        
        # Procesar el HTML obtenido con BeautifulSoup
        contenido = await page.content()
        soup = BeautifulSoup(contenido, "html.parser")
        filas_estadisticas = soup.find_all("div", {"data-testid": "wcl-statistics"})
        
        for fila in filas_estadisticas:
            cat_div = fila.find("div", {"data-testid": "wcl-statistics-category"})
            if cat_div:
                categoria = cat_div.get_text(strip=True)
                
                # Capturar valores de Local y Visitante
                home_val_div = fila.find("div", class_=lambda x: x and 'wcl-homeValue' in x)
                away_val_div = fila.find("div", class_=lambda x: x and 'wcl-awayValue' in x)
                
                val_home = home_val_div.get_text(strip=True) if home_val_div else "0"
                val_away = away_val_div.get_text(strip=True) if away_val_div else "0"
                
                # Asignar al diccionario temporal
                datos_stats[f"{categoria} (L)"] = val_home
                datos_stats[f"{categoria} (V)"] = val_away
    except Exception:
        pass  # Si el partido no tiene la pestaña activa, continúa sin romper el ciclo
    finally:
        await page.close()
    return datos_stats

async def ejecutar_escaneo_completo():
    """Flujo principal que coordina el scraping de la lista 'EN DIRECTO' y cada partido."""
    lista_registros_finales = []
    
    async with async_playwright() as p:
        # Iniciar Chromium en modo oculto con argumentos de optimización
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        await page.goto("https://www.flashscore.pe/", timeout=15000)
        
        # Cambiar a la pestaña 'EN DIRECTO'
        boton_directo = page.locator("//div[contains(@class, 'filters__text') and text()='EN DIRECTO']")
        await boton_directo.wait_for(state="visible", timeout=8000)
        await boton_directo.click()
        await page.wait_for_timeout(2500)
        
        # Parsear la lista de partidos en directo
        contenido_principal = await page.content()
        soup = BeautifulSoup(contenido_principal, "html.parser")
        partidos_en_vivo = soup.find_all("div", id=lambda x: x and x.startswith("g_1_"))
        
        if not partidos_en_vivo:
            await browser.close()
            return None
            
        st.info(f"Se detectaron {len(partidos_en_vivo)} partidos activos. Extrayendo métricas...")
        barra_progreso = st.progress(0)
        
        #
