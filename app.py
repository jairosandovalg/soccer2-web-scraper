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
    """Navega a la URL del partido y extrae los datos de la pestaña de Estadísticas."""
    datos_stats = {}
    try:
        driver.get(url_partido)
        
        # 1. Esperar a que el botón de 'Estadísticas' sea cliqueable y presionarlo
        boton_stats = WebDriverWait(driver, 7).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@role='tab' and contains(., 'Estadísticas')]"))
        )
        driver.execute_script("arguments[0].click();", boton_stats)
        time.sleep(1.5)  # Tiempo de espera para que carguen las barras internas del HTML
        
        # 2. Parsear el documento HTML con BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "html.parser")
        filas_estadisticas = soup.find_all("div", {"data-testid": "wcl-statistics"})
        
        for fila in filas_estadisticas:
            # Buscar el nombre de la categoría (Ej: 'Remates totales', 'Pases', etc.)
            cat_div = fila.find("div", {"data-testid": "wcl-statistics-category"})
            if cat_div:
                categoria = cat_div.get_text(strip=True)
                
                # Buscar valores de Local y Visitante mediante sus respectivas clases
                home_val_div = fila.find("div", class_=lambda x: x and 'wcl-homeValue' in x)
                away_val_div = fila.find("div", class_=lambda x: x and 'wcl-awayValue' in x)
                
                val_home = home_val_div.get_text(strip=True) if home_val_div else "0"
                val_away = away_val_div.get_text(strip=True) if away_val_div else "0"
                
                # Asignar al diccionario temporal de columnas
                datos_stats[f"{categoria} (L)"] = val_home
                datos_stats[f"{categoria} (V)"] = val_away
                
    except Exception:
        # Si un partido va iniciando y no tiene la pestaña habilitada, continúa sin detener el script
        pass
    return datos_stats

# --- PROCESO PRINCIPAL EN INTERFAZ ---

if st.button("🔄 Ejecutar Escaneo Completo y Generar Tabla"):
    with st.spinner("Iniciando escáner... Conectando a la sección EN DIRECTO..."):
        try:
            driver = iniciar_navegador()
            
            # Navegamos a la sección de partidos en directo
            url_principal = "https://www.flashscore.pe/"
            driver.get(url_principal)
            
            boton_directo = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'filters__text') and text()='EN DIRECTO']"))
            )
            driver.execute_script("arguments[0].click();", boton_directo)
            time.sleep(4)
            
            # Detectar los partidos actuales usando BeautifulSoup
            soup = BeautifulSoup(driver.page_source, "html.parser")
            partidos_en_vivo = soup.find_all("div", id=lambda x: x and x.startswith("g_1_"))
            
            if not partidos_en_vivo:
                st.warning("No se encontraron partidos en directo para analizar en este momento.")
            else:
                st.success(f"Se detectaron {len(partidos_en_vivo)} partidos activos. Extrayendo métricas individuales...")
                
                # Barra de progreso visual en Streamlit
                barra_progreso = st.progress(0)
                lista_registros_finales = []
                
                # Recorrer cada partido e ir recolectando su información interna
                for idx, fila in enumerate(partidos_en_vivo):
                    id_partido = fila.get('id').split('_')[-1]
                    url_match_stats = f"https://www.flashscore.pe/partido/{id_partido}/#/resumen/estadisticas"
                    
                    # Extraer los nombres de los equipos de la lista de origen
                    local_div = fila.find("div", class_=lambda c: c and "home" in c.lower() and "participant" in c.lower())
                    visitante_div = fila.find("div", class_=lambda c: c and "away" in c.lower() and "participant" in c.lower())
                    nom_local = local_div.get_text(strip=True) if local_div else "Local"
                    nom_visitante = visitante_div.get_text(strip=True) if visitante_div else "Visitante"
                    
                    # Llamar a la función de raspado profundo por link
                    métricas_partido = extraer_estadisticas_partido(driver, url_match_stats)
                    
                    # Consolidar los datos básicos junto a sus estadísticas raspadas
                    registro = {
                        "Partido en Vivo": f"{nom_local} vs {nom_visitante}"
                    }
                    registro.update(métricas_partido)
                    lista_registros_finales.append(registro)
                    
                    # Actualizar progreso en la pantalla de la app
                    barra_progreso.progress((idx + 1) / len(partidos_en_vivo))
                
                # 3. Construir el cuadro de datos final usando Pandas
                df_final = pd.DataFrame(lista_registros_finales)
                
                # Rellenar con guiones los espacios de estadísticas que no existan o no hayan cargado aún
                df_final = df_final.fillna("-")
                
                # Desplegar el cuadro interactivo en Streamlit
                st.write("### 📈 Cuadro de Control General (Estadísticas Principales)")
                st.dataframe(df_final, use_container_width=True)
                
                st.balloons()
                
        except Exception as e:
            st.error(f"Fallo crítico en el sistema de análisis: {str(e)}")
