import streamlit as st
import datetime
import pandas as pd
import os
from playwright.sync_api import sync_playwright

# Configuración de la página
st.set_page_config(page_title="Buscador Licitaciones PAMI", layout="wide")
st.title("🔎 Monitoreo de Licitaciones PAMI")
st.subheader("Maxilofacial")

@st.cache_resource
def preparar_entorno_playwright():
    # Esto descarga el binario puro de Playwright dentro del entorno
    os.system("playwright install chromium")

# --- Parámetros de búsqueda ---
palabras_clave = ['microplacas', 'craneal', 'membrana', 'columna', 'clip']

destinos = ["UGL X LANÚS", "UGL XXIX MORÓN", "UGL XXXII LUJÁN"]

config_ugls = {
    "UGL X LANÚS": {"cod": "10", "ext": "pdf"},
    "UGL XXIX MORÓN": {"cod": "29", "ext": "pdf"},
    "UGL XXXII LUJÁN": {"cod": "32", "ext": "pdf"}
}

# --- Interfaz de Streamlit ---
if st.button('🚀 Iniciar Búsqueda en PAMI'):
    # Nos aseguramos de que el navegador esté instalado en el backend
    preparar_entorno_playwright()
    
    todos_los_resultados = []
    progreso = st.progress(0)
    
    hoy = datetime.datetime.now()
    hoy_dia = hoy.day
    mañana_dia = (hoy + datetime.timedelta(days=5)).day 

    # Contexto síncrono de Playwright
    with sync_playwright() as p:
        # Lanzamos el navegador con argumentos ligeros optimizados para servidores
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        page = browser.new_page()
        
        for i, destino in enumerate(destinos):
            st.write(f"Buscando en: **{destino}**...")
            progreso.progress((i + 1) / len(destinos))
            
            try:
                # Navegación base
                page.goto("https://prestadores.pami.org.ar/result.php?c=7-5&par=2", timeout=30000)
                
                # Selección de UGL
                page.select_option("#destino_compra", label=destino)
                
                # Selección de rango de fechas en el Datepicker
                for campo_id in ['fecha_post', 'fecha_ant']:
                    page.click(f"#{campo_id}")
                    page.wait_for_selector(".ui-datepicker-calendar", state="visible")
                    
                    dia = hoy_dia if campo_id == 'fecha_post' else mañana_dia
                    try:
                        # Hacemos click en el enlace del día correspondiente dentro del calendario
                        page.locator(f"//a[text()='{dia}']").first.click()
                    except:
                        st.warning(f"No se pudo seleccionar el día {dia} en {destino}.")
                
                # Ejecutar la consulta en el sitio
                page.click("#srchBtn")
                
                # Esperar a que la tabla de resultados se renderice en el DOM
                page.wait_for_selector('#resultados table', timeout=10000)
                
                # Capturamos todas las filas directamente
                filas = page.locator('#resultados table tr').all()
                
                for fila in filas:
                    columnas = fila.locator('td').all()
                    if len(columnas) >= 5:
                        detalle_texto = columnas[4].inner_text().lower().strip()
                        
                        # Filtrado inteligente por palabras clave
                        if any(palabra in detalle_texto for palabra in palabras_clave):
                            nro_completo = columnas[0].inner_text().strip()
                            nro_solo = nro_completo.split('/')[0]
                            
                            conf = config_ugls.get(destino, {"cod": "00", "ext": "pdf"})
                            cod_ugl = conf["cod"]
                            ext = conf["ext"]
                            
                            base_url = "https://institucional.pami.org.ar/compras/archivos"
                            # Generación de links (ajustados a PDF como solicitaste)
                            link_v1 = f"{base_url}/CAB_{nro_solo}_2026_{cod_ugl}_1.{ext}"
                            link_v2 = f"{base_url}/CAB_{nro_solo}_2026_{cod_ugl}_2.{ext}"
                            
                            todos_los_resultados.append({
                                "Número": nro_completo,
                                "UGL": columnas[2].inner_text().strip(),
                                "Detalle": columnas[4].inner_text().strip(),
                                "Fecha": columnas[5].inner_text().strip(),
                                "Link Principal": link_v1,
                                "Link Alternativo": link_v2
                            })
                            
            except Exception as e:
                continue
                
        # Cerramos de forma limpia la instancia del navegador
        browser.close()

    # --- Renderizado de Reportes ---
    progreso.progress(1.0)
    if todos_los_resultados:
        st.success(f"¡Se encontraron {len(todos_los_resultados)} coincidencias críticas!")
        df = pd.DataFrame(todos_los_resultados)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No se detectaron licitaciones abiertas para maxilofacial bajo estos parámetros.")
