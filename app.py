import streamlit as st
import pandas as pd
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Configuración de la interfaz de Streamlit
st.set_page_config(page_title="Bot de Estadísticas Final", layout="wide")
st.title("📊 Monitor de Estadísticas en Vivo - Flashscore")
st.subheader("Análisis de métricas en tiempo real para decisiones de apuestas")

def extraer_estadisticas_partido(context, url_partido):
    """Navega a la URL del partido usando el contexto de Playwright y extrae los datos."""
    datos_stats = {}
    page = context.new_page()
    try:
        # Abrir enlace del partido con tiempo límite de 12 segundos
        page.goto(url_partido, timeout=12000)
        
        # Esperar y hacer clic en la pestaña de Estadísticas
        boton_stats = page.locator("//button[@role='tab' and contains(., 'Estadísticas')]")
        boton_stats.wait_for(state="visible", timeout=4000)
        boton_stats.click()
        
        # Esperar a que se rendericen las barras internas
        page.wait_for_timeout(1500)
        
        # Parsear el HTML con BeautifulSoup
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
        pass  # Continúa si el partido no tiene estadísticas activas
    finally:
        page.close()  # Cerrar la pestaña para liberar memoria RAM
    return datos_stats

# --- PROCESO PRINCIPAL EN INTERFAZ ---

if st.button("🔄 Ejecutar Escaneo Completo y Generar Tabla"):
    with st.spinner("Iniciando escáner... Conectando a la sección EN DIRECTO con Playwright..."):
        try:
            # Inicializamos Playwright de forma síncrona
            with sync_playwright() as p:
                # Lanzar navegador con argumentos optimizados para servidores Linux cloud
                browser = p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
                
                page = context.new_page()
                page.goto("https://www.flashscore.pe/", timeout=20000)
                
                # Detectar y cliquear el botón EN DIRECTO
                boton_directo = page.locator("//div[contains(@class, 'filters__text') and text()='EN DIRECTO']")
                boton_directo.wait_for(state="visible", timeout=10000)
                boton_directo.click()
                
                # Espera de asentamiento de la lista
                page.wait_for_timeout(3000)
                
                # Detectar los partidos actuales usando BeautifulSoup
                contenido_principal = page.content()
                soup = BeautifulSoup(contenido_principal, "html.parser")
                partidos_en_vivo = soup.find_all("div", id=lambda x: x and x.startswith("g_1_"))
                
                if not partidos_en_vivo:
                    st.warning("No se encontraron partidos en directo para analizar en este momento.")
                else:
                    st.success(f"Se detectaron {len(partidos_en_vivo)} partidos activos. Extrayendo métricas individuales...")
                    
                    barra_progreso = st.progress(0)
                    lista_registros_finales = []
                    
                    # Recorrer cada partido
                    for idx, fila in enumerate(partidos_en_vivo):
                        id_partido = fila.get('id').split('_')[-1]
                        url_match_stats = f"https://www.flashscore.pe/partido/{id_partido}/#/resumen/estadisticas"
                        
                        local_div = fila.find("div", class_=lambda c: c and "home" in c.lower() and "participant" in c.lower())
                        visitante_div = fila.find("div", class_=lambda c: c and "away" in c.lower() and "participant" in c.lower())
                        nom_local = local_div.get_text(strip=True) if local_div else "Local"
                        nom_visitante = visitante_div.get_text(strip=True) if visitante_div else "Visitante"
                        
                        # Pasar el contexto del navegador para procesar el partido
                        métricas_partido = extraer_estadisticas_partido(context, url_match_stats)
                        
                        registro = {"Partido en Vivo": f"{nom_local} vs {nom_visitante}"}
                        registro.update(métricas_partido)
                        lista_registros_finales.append(registro)
                        
                        barra_progreso.progress((idx + 1) / len(partidos_en_vivo))
                    
                    # Construir la tabla final
                    df_final = pd.DataFrame(lista_registros_finales).fillna("-")
                    
                    st.write("### 📈 Cuadro de Control General (Estadísticas Principales)")
                    st.dataframe(df_final, use_container_width=True)
                    st.balloons()
                
                browser.close()
                
        except Exception as e:
            st.error(f"Fallo crítico en el sistema de análisis: {str(e)}")
