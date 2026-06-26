import streamlit as st
import pandas as pd
import asyncio
import os
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# --- CONFIGURACIÓN DE RUTA LOCAL PARA PLAYWRIGHT ---
# Forzamos a Playwright a instalar y buscar el navegador dentro del directorio de la app
NUEVA_RUTA_CACHE = os.path.join(os.getcwd(), ".playwright_cache")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = NUEVA_RUTA_CACHE

st.set_page_config(page_title="Bot de Estadísticas Final", layout="wide")

@st.cache_resource
def instalar_dependencias_playwright():
    """Instala Chromium de forma local en el proyecto para que no se pierda."""
    with st.spinner("Instalando componentes del navegador en el servidor local... (Solo la primera vez)"):
        # Asegura la instalación en la ruta que definimos arriba
        os.system("python -m playwright install chromium")

# Ejecutar la instalación limpia antes de todo
instalar_dependencias_playwright()

# --- INTERFAZ DE USUARIO ---
st.title("📊 Monitor de Estadísticas en Vivo - Flashscore")
st.subheader("Análisis de métricas en tiempo real para decisiones de apuestas")

# Control del tiempo de actualización en la barra lateral
INTERVALO = st.sidebar.slider("⏱️ Intervalo de actualización automática (segundos)", 30, 300, 60)

# --- FUNCIONES DE EXTRACCIÓN ---

async def extraer_estadisticas_partido(context, url_partido):
    datos_stats = {}
    page = await context.new_page()
    try:
        await page.goto(url_partido, timeout=12000)
        
        boton_stats = page.locator("//button[@role='tab' and contains(., 'Estadísticas')]")
        await boton_stats.wait_for(state="visible", timeout=4000)
        await boton_stats.click()
        
        await page.wait_for_timeout(1500)
        
        contenido = await page.content()
        soup = BeautifulSoup(contenido, "html.parser")
        filas_estadisticas = soup.find_all("div", {"data-testid": "wcl-statistics"})
        
        for fila in filas_estadisticas:
            cat_div = fila.find("div", {"data-testid": "wcl-statistics-category"})
            if cat_div:
                categoria = cat_div.get_text(strip=True)
                home_val_div = fila.find("div", class_=lambda x: x and 'wcl-homeValue' in x)
                away_val_div = fila.find("div", class_=lambda x: x and 'wcl-awayValue' in x)
                
                datos_stats[f"{categoria} (L)"] = home_val_div.get_text(strip=True) if home_val_div else "0"
                datos_stats[f"{categoria} (V)"] = away_val_div.get_text(strip=True) if away_val_div else "0"
    except Exception:
        pass
    finally:
        await page.close()
    return datos_stats

async def ejecutar_escaneo_completo(status_placeholder):
    lista_registros_finales = []
    
    status_placeholder.write("🔍 Inicializando Playwright local...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        
        status_placeholder.write("🌐 Conectando a Flashscore...")
        page = await context.new_page()
        await page.goto("https://www.flashscore.pe/", timeout=20000)
        
        status_placeholder.write("📌 Filtrando partidos EN DIRECTO...")
        boton_directo = page.locator("//div[contains(@class, 'filters__text') and text()='EN DIRECTO']")
        await boton_directo.wait_for(state="visible", timeout=10000)
        await boton_directo.click()
        await page.wait_for_timeout(3000)
        
        contenido_principal = await page.content()
        soup = BeautifulSoup(contenido_principal, "html.parser")
        partidos_en_vivo = soup.find_all("div", id=lambda x: x and x.startswith("g_1_"))
        
        if not partidos_en_vivo:
            await browser.close()
            return None
            
        status_placeholder.write(f"⚡ Procesando {len(partidos_en_vivo)} partidos encontrados...")
        barra_progreso = st.progress(0)
        
        for idx, fila in enumerate(partidos_en_vivo):
            id_partido = fila.get('id').split('_')[-1]
            url_match_stats = f"https://www.flashscore.pe/partido/{id_partido}/#/resumen/estadisticas"
            
            local_div = fila.find("div", class_=lambda c: c and "home" in c.lower() and "participant" in c.lower())
            visitante_div = fila.find("div", class_=lambda c: c and "away" in c.lower() and "participant" in c.lower())
            nom_local = local_div.get_text(strip=True) if local_div else "Local"
            nom_visitante = visitante_div.get_text(strip=True) if visitante_div else "Visitante"
            
            métricas_partido = await extraer_estadisticas_partido(context, url_match_stats)
            
            # Línea corregida con comillas de cierre fijadas
            registro = {"Partido en Vivo": f"{nom_local} vs {nom_visitante}"}
            registro.update(métricas_partido)
            lista_registros_finales.append(registro)
            
            barra_progreso.progress((idx + 1) / len(partidos_en_vivo))
            
        await browser.close()
    return lista_registros_finales

# --- CONTENEDOR REACTIVO AUTOMÁTICO ---

@st.fragment(run_every=INTERVALO)
def contenedor_monitoreo():
    st.write(f"⏱️ *Última actualización solicitada: {pd.Timestamp.now().strftime('%H:%M:%S')}*")
    estado_bot = st.empty()
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        datos = loop.run_until_complete(ejecutar_escaneo_completo(estado_bot))
        loop.close()
        
        estado_bot.empty()
        
        if datos is None:
            st.warning("No se detectaron partidos en directo en este momento.")
        elif len(datos) > 0:
            df_final = pd.DataFrame(datos).fillna("-")
            st.write("### 📈 Cuadro de Control General")
            st.dataframe(df_final, use_container_width=True)
            
    except Exception as e:
        estado_bot.error(f"Fallo en la actualización actual: {str(e)}")

# Arrancar el monitor reactivo
contenedor_monitoreo()
