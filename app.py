import streamlit as st
import pandas as pd
import subprocess
import os
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# --- CONFIGURACIÓN DE RUTA PARA SERVIDORES CLOUD ---
# Evita problemas de permisos descargando Chromium en el directorio temporal
RUTA_TEMPORAL_NAVEGADOR = "/tmp/playwright-browsers"
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = RUTA_TEMPORAL_NAVEGADOR

# Configuración de la interfaz de Streamlit
st.set_page_config(page_title="Bot de Estadísticas Final", layout="wide")
st.title("📊 Monitor de Estadísticas en Vivo - Flashscore")
st.subheader("Análisis de métricas en tiempo real para decisiones de apuestas")

def extraer_estadisticas_partido(context, url_partido):
    """Navega a la URL del partido usando el contexto de Playwright y extrae las estadísticas."""
    datos_stats = {}
    page = context.new_page()
    try:
        page.goto(url_partido, timeout=12000)
        
        # Esperar y hacer clic en la pestaña de Estadísticas
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
    # Verificar instalación del navegador en la ruta temporal compartida
    if not os.path.exists(RUTA_TEMPORAL_NAVEGADOR):
        with st.spinner("Descargando componentes del navegador en el almacenamiento temporal..."):
            try:
                subprocess.run(["python", "-m", "playwright", "install", "chromium"], check=True)
            except Exception as e:
                st.error(f"Error instalando el navegador: {str(e)}")

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
                page.goto("https://www.flashscore.pe/", timeout=20000)
                
                # Detectar y cliquear el botón EN DIRECTO
                boton_directo = page.locator("//div[contains(@class, 'filters__text') and text()='EN DIRECTO']")
                boton_directo.wait_for(state="visible", timeout=10000)
                boton_directo.click()
                
                page.wait_for_timeout(3000)
                
                # Parsear el documento HTML principal
                contenido_principal = page.content()
                soup = BeautifulSoup(contenido_principal, "html.parser")
                partidos_en_vivo = soup.find_all("div", id=lambda x: x and x.startswith("g_1_"))
                
                if not partidos_en_vivo:
                    st.warning("No se encontraron partidos en directo para analizar en este momento.")
                else:
                    st.success(f"Se detectaron {len(partidos_en_vivo)} partidos activos. Extrayendo métricas...")
                    
                    barra_progreso = st.progress(0)
                    lista_registros_finales = []
                    
                    for idx, fila in enumerate(partidos_en_vivo):
                        id_partido = fila.get('id').split('_')[-1]
                        url_match_stats = f"https://www.flashscore.pe/partido/{id_partido}/#/resumen/estadisticas"
                        
                        # 1. Extraer nombres de los equipos
                        local_div = fila.find("div", class_=lambda c: c and "home" in c.lower() and "participant" in c.lower())
                        visitante_div = fila.find("div", class_=lambda c: c and "away" in c.lower() and "participant" in c.lower())
                        nom_local = local_div.get_text(strip=True) if local_div else "Local"
                        nom_visitante = visitante_div.get_text(strip=True) if visitante_div else "Visitante"
                        
                        # 2. Extraer el Marcador en Vivo directamente de la fila principal
                        home_score_div = fila.find("div", class_=lambda c: c and "home" in c.lower() and "score" in c.lower())
                        away_score_div = fila.find("div", class_=lambda c: c and "away" in c.lower() and "score" in c.lower())
                        
                        goles_local = home_score_div.get_text(strip=True) if home_score_div else "-"
                        goles_visitante = away_score_div.get_text(strip=True) if away_score_div else "-"
                        marcador_actual = f"{goles_local} - {goles_visitante}"
                        
                        # 3. Llamar a la función para extraer estadísticas internas de posesión/remates
                        métricas_partido = extraer_estadisticas_partido(context, url_match_stats)
                        
                        # Consolidar registro final incluyendo el marcador al principio
                        registro = {
                            "Partido en Vivo": f"{nom_local} vs {nom_visitante}",
                            "Marcador": marcador_actual
                        }
                        registro.update(métricas_partido)
                        lista_registros_finales.append(registro)
                        
                        barra_progreso.progress((idx + 1) / len(partidos_en_vivo))
                    
                    # Generar la tabla estructurada con Pandas
                    df_final = pd.DataFrame(lista_registros_finales).fillna("-")
                    
                    # Reordenar columnas para dejar el Marcador visible al inicio
                    columnas = ["Partido en Vivo", "Marcador"] + [col for col in df_final.columns if col not in ["Partido en Vivo", "Marcador"]]
                    df_final = df_final[columnas]
                    
                    st.write("### 📈 Cuadro de Control General (Estadísticas Principales)")
                    st.dataframe(df_final, use_container_width=True)
                    st.balloons()
                
                browser.close()
                
        except Exception as e:
            st.error(f"Fallo crítico en el sistema de análisis: {str(e)}")
