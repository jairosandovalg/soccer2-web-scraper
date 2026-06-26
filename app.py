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
    """Navega a la URL del partido, extrae marcador, tiempo y las estadísticas."""
    datos_partido = {
        "Marcador": "- - -",
        "Tiempo/Estado": "-",
        "Stats": {}
    }
    try:
        driver.get(url_partido)
        
        # 1. Esperar a que cargue el botón de Estadísticas en el DOM de la página del partido
        WebDriverWait(driver, 6).until(
            EC.presence_of_element_to_be_clickable((By.XPATH, "//button[@role='tab' and contains(., 'Estadísticas')]"))
        )
        
        # 2. Parsear el HTML inicial para asegurar la captura del marcador y tiempo actual
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # --- EXTRACCIÓN DEL MARCADOR REAL ---
        score_wrapper = soup.find("div", class_=lambda x: x and "detailScore__wrapper" in x)
        if score_wrapper:
            datos_partido["Marcador"] = score_wrapper.get_text(strip=True)
            
        # --- EXTRACCIÓN DEL TIEMPO / ESTADO ---
        status_span = soup.find("span", class_=lambda x: x and "detailStatus" in x)
        if status_span:
            datos_partido["Tiempo/Estado"] = status_span.get_text(strip=True)
        
        # 3. Hacer clic de manera segura usando JavaScript para evitar bloqueos visuales
        boton_stats = driver.find_element(By.XPATH, "//button[@role='tab' and contains(., 'Estadísticas')]")
        driver.execute_script("arguments[0].click();", boton_stats)
        time.sleep(1.2)  # Pausa controlada para que carguen los valores numéricos
        
        # Volver a parsear para capturar las barras de estadísticas
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
                
    except Exception:
        pass  # Si falla un partido en específico, no detiene el ciclo de los demás
    
    return datos_partido  # <--- CORREGIDO: Retorna el diccionario correcto de la función

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
                st.success(f"Se detectaron {len(partidos_en_vivo)} partidos activos. Procesando datos profundos...")
                
                barra_progreso = st.progress(0)
                lista_registros_finales = []
                
                for idx, fila in enumerate(partidos_en_vivo):
                    id_partido = fila.get('id').split('_')[-1]
                    url_match_stats = f"https://www.flashscore.pe/partido/{id_partido}/#/resumen/estadisticas"
                    
                    local_div = fila.find("div", class_=lambda c: c and "home" in c.lower() and "participant" in c.lower())
                    visitante_div = fila.find("div", class_=lambda c: c and "away" in c.lower() and "participant" in c.lower())
                    nom_local = local_div.get_text(strip=True) if local_div else "Local"
                    nom_visitante = visitante_div.get_text(strip=True) if visitante_div else "Visitante"
                    
                    # Llamar a la función interna pasándole el driver actual
                    resultado_profundo = extraer_estadisticas_partido(driver, url_match_stats)
                    
                    # Estructurar la fila base con los datos limpios extraídos
                    registro = {
                        "Partido en Vivo": f"{nom_local} vs {nom_visitante}",
                        "Marcador": resultado_profundo["Marcador"],
                        "Tiempo/Estado": resultado_profundo["Tiempo/Estado"]
                    }
                    
                    # Insertar de manera dinámica las estadísticas numéricas raspadas
                    registro.update(resultado_profundo["Stats"])
                    lista_registros_finales.append(registro)
                    
                    barra_progreso.progress((idx + 1) / len(partidos_en_vivo))
                
                # Construir DataFrame final con Pandas
                df_final = pd.DataFrame(lista_registros_finales).fillna("-")
                
                # Forzar el orden visual para que las columnas de control queden fijas al inicio
                columnas_fijas = ["Partido en Vivo", "Marcador", "Tiempo/Estado"]
                columnas_stats = [col for col in df_final.columns if col not in columnas_fijas]
                df_final = df_final[columnas_fijas + columnas_stats]
                
                st.write("### 📈 Cuadro de Control General (Estadísticas Principales)")
                st.dataframe(df_final, use_container_width=True)
                st.balloons()
                
            driver.quit()  # Cerrar de forma limpia el navegador al terminar el análisis
                
        except Exception as e:
            st.error(f"Fallo crítico en el sistema de análisis: {str(e)}")
            try:
                driver.quit()
            except:
                pass
