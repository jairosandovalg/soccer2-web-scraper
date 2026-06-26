import streamlit as st
import pandas as pd
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configuración de la interfaz de Streamlit
st.set_page_config(page_title="Bot de Estadísticas Final", layout="wide")
st.title("📊 Monitor de Estadísticas en Vivo - Flashscore")
st.subheader("Análisis de métricas en tiempo real para decisiones de apuestas")

@st.cache_resource
def iniciar_navegador():
    """Configura e inicia el navegador en modo oculto (headless) anti-detección."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    try:
        service = Service()
        return webdriver.Chrome(service=service, options=chrome_options)
    except Exception:
        service = Service("/usr/bin/chromedriver")
        chrome_options.binary_location = "/usr/bin/chromium-browser"
        return webdriver.Chrome(service=service, options=chrome_options)

def extraer_estadisticas_partido(driver, url_partido):
    """Navega a la URL del partido, asegura la carga de datos y extrae todo."""
    datos_partido = {
        "Marcador": "- - -",
        "Tiempo/Estado": "-",
        "Stats": {}
    }
    try:
        driver.get(url_partido)
        
        # 1. ESPERA CRUCIAL: Esperar a que el contenedor del marcador esté presente en la página
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.detailScore__wrapper"))
        )
        time.sleep(1.0) # Pequeño margen para estabilización de carga de texto
        
        # Parsear el HTML con BeautifulSoup para el marcador y tiempo
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Extraer el marcador usando selectores CSS más precisos
        score_wrapper = soup.select_one("div.detailScore__wrapper")
        if score_wrapper:
            datos_partido["Marcador"] = score_wrapper.get_text(strip=True)
            
        # Extraer el tiempo o estado del partido
        status_span = soup.select_one("span.fixedHeaderDuel__detailStatus")
        if status_span:
            datos_partido["Tiempo/Estado"] = status_span.get_text(strip=True)
        
        # 2. Verificar si el botón de estadísticas está disponible para hacer click
        botones_tab = driver.find_elements(By.XPATH, "//button[@role='tab' and contains(., 'Estadísticas')]")
        if botones_tab:
            driver.execute_script("arguments[0].click();", botones_tab[0])
            time.sleep(1.5)  # Espera para que las barras de estadísticas se animen y carguen los números
            
            # Volver a parsear el HTML ahora con la pestaña de estadísticas activa
            soup_stats = BeautifulSoup(driver.page_source, "html.parser")
            filas_estadisticas = soup_stats.find_all("div", {"data-testid": "wcl-statistics"})
            
            for fila in filas_estadisticas:
                cat_div = fila.find("div", {"data-testid": "wcl-statistics-category"})
                if cat_div:
                    categoria = cat_div.get_text(strip=True)
                    
                    home_val_div = fila.find("div", class_=lambda x: x and 'wcl-homeValue' in x)
                    away_val_div = fila.find("div", class_=lambda x: x and 'wcl-awayValue' in x)
                    
                    val_home = home_val_div.get_text(strip=True) if home_val_div else "0"
                    val_away = away_val_div.get_text(strip=True) if away_val_div else "0"
                    
                    datos_partido["Stats"][f"{categoria} (L)"] = val_home
                    datos_partido["Stats"][f"{categoria} (V)"] = val_away
                    
    except Exception as e:
        # En caso de que falle la espera o el click, dejamos un registro sutil para no congelar el avance
        pass
        
    return datos_partido

# --- PROCESO PRINCIPAL EN INTERFAZ ---

if st.button("🔄 Ejecutar Escaneo Completo y Generar Tabla"):
    with st.spinner("Iniciando escáner... Conectando a la sección EN DIRECTO..."):
        try:
            driver = iniciar_navegador()
            
            url_principal = "https://www.flashscore.pe/"
            driver.get(url_principal)
            
            boton_directo = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'filters__text') and text()='EN DIRECTO']"))
            )
            driver.execute_script("arguments[0].click();", boton_directo)
            time.sleep(4)
            
            soup = BeautifulSoup(driver.page_source, "html.parser")
            partidos_en_vivo = soup.find_all("div", id=lambda x: x and x.startswith("g_1_"))
            
            if not partidos_en_vivo:
                st.warning("No se encontraron partidos en directo para analizar en este momento.")
            else:
                st.success(f"Se detectaron {len(partidos_en_vivo)} partidos activos. Extrayendo métricas individuales...")
                
                barra_progreso = st.progress(0)
                lista_registros_finales = []
                
                for idx, fila in enumerate(partidos_en_vivo):
                    id_partido = fila.get('id').split('_')[-1]
                    url_match_stats = f"https://www.flashscore.pe/partido/{id_partido}/#/resumen/estadisticas"
                    
                    local_div = fila.find("div", class_=lambda c: c and "home" in c.lower() and "participant" in c.lower())
                    visitante_div = fila.find("div", class_=lambda c: c and "away" in c.lower() and "participant" in c.lower())
                    nom_local = local_div.get_text(strip=True) if local_div else "Local"
                    nom_visitante = visitante_div.get_text(strip=True) if visitante_div else "Visitante"
                    
                    # Ejecutar raspado individual por partido
                    resultado_profundo = extraer_estadisticas_partido(driver, url_match_stats)
                    
                    # Consolidar datos generales
                    registro = {
                        "Partido en Vivo": f"{nom_local} vs {nom_visitante}",
                        "Marcador": resultado_profundo["Marcador"],
                        "Tiempo/Estado": resultado_profundo["Tiempo/Estado"]
                    }
                    
                    # Añadir las estadísticas numéricas si existían
                    registro.update(resultado_profundo["Stats"])
                    lista_registros_finales.append(registro)
                    
                    barra_progreso.progress((idx + 1) / len(partidos_en_vivo))
                
                # Construcción del DataFrame
                df_final = pd.DataFrame(lista_registros_finales).fillna("-")
                
                # Reorganizar el orden visual de las columnas primarias
                columnas_fijas = ["Partido en Vivo", "Marcador", "Tiempo/Estado"]
                columnas_stats = [col for col in df_final.columns if col not in columnas_fijas]
                df_final = df_final[columnas_fijas + columnas_stats]
                
                st.write("### 📈 Cuadro de Control General (Estadísticas Principales)")
                st.dataframe(df_final, use_container_width=True)
                st.balloons()
                
            driver.quit()
                
        except Exception as e:
            st.error(f"Fallo crítico en el sistema de análisis: {str(e)}")
            try:
                driver.quit()
            except:
                pass
