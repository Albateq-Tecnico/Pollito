import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np

# --- CONFIGURACIÓN DE PÁGINA Y ESTILOS ---
st.set_page_config(page_title="Método Rodriguez - Calidad de Pollito", layout="wide")

st.markdown("""
<style>
    .stButton>button {
        font-size: 1.2rem;
        font-weight: bold;
        padding: 10px 24px;
        border-radius: 8px;
        width: 100%;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #F0F2F6;
        border-radius: 8px;
        padding: 10px 15px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1E88E5;
        color: white;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- CONEXIÓN A GOOGLE SHEETS (Función cacheada para eficiencia) ---
@st.cache_resource
def connect_to_google_sheets():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(credentials)
        spreadsheet = client.open("BD_Calidad_Pollito")
        return spreadsheet
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        st.warning("Asegúrate de haber configurado los 'Secrets' de Streamlit correctamente con tus credenciales de GCP.")
        return None

spreadsheet = connect_to_google_sheets()

# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN ---
def initialize_session_state():
    if 'pollitos_data' not in st.session_state:
        st.session_state.pollitos_data = pd.DataFrame({
            'numero_pollito': range(1, 11),
            'vitalidad_ok': [False] * 10,
            'ombligo_ok': [False] * 10,
            'patas_ok': [False] * 10, # Campo separado
            'ojos_ok': [False] * 10,  # Campo separado
            'pico_ok': [False] * 10,
            'abdomen_ok': [False] * 10,
            'plumon_ok': [False] * 10,
            'cuello_ok': [False] * 10,
            'peso_gr': [40.0] * 10,
            'temp_cloacal': [40.0] * 10
        })

initialize_session_state()

# --- INTERFAZ DE USUARIO ---
st.title("Método Rodriguez: Evaluación de Calidad de Pollito")
st.markdown("---")

tab1, tab2 = st.tabs(["Paso 1: Evaluación en Incubadora", "Paso 2: Evaluación en Transporte (Próximamente)"])

with tab1:
    st.header("1. Información General y Ambiental del Lote")
    
    with st.form("info_lote_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            lote_id = st.text_input("ID del Lote", help="Código único del lote.")
            granja_origen = st.text_input("Granja de Origen", help="Granja de reproductoras.")
            linea_genetica = st.selectbox("Línea Genética", ["Cobb", "Ross", "Otra"])
        
        with col2:
            fecha_nacimiento = st.date_input("Fecha de Nacimiento")
            cantidad_total = st.number_input("Cantidad Total de Pollitos", min_value=1, step=1000)
            evaluador = st.text_input("Nombre del Evaluador")
        
        with col3:
            temp_furgon = st.slider("Temperatura Furgón (°C)", 18.0, 25.0, 22.0)
            temp_cascara = st.slider("Temperatura Cáscara (°C)", 16.0, 20.0, 18.0)
            temp_salon = st.slider("Temperatura Salón (°C)", 18.0, 24.0, 21.0)
            huevo_sudado = st.toggle("Huevo Sudado", value=False)
            aves_por_caja = st.number_input("Aves por Caja", min_value=50, max_value=150, value=100)
        
        st.markdown("---")
        st.header("2. Puntuación Detallada de la Muestra (10 Pollitos)")

        edited_df = st.data_editor(
            st.session_state.pollitos_data,
            column_config={
                "numero_pollito": st.column_config.NumberColumn("Pollito #", disabled=True),
                "vitalidad_ok": st.column_config.CheckboxColumn("Vitalidad OK?"),
                "ombligo_ok": st.column_config.CheckboxColumn("Ombligo OK?"),
                "patas_ok": st.column_config.CheckboxColumn("Patas OK?"), # Columna actualizada
                "ojos_ok": st.column_config.CheckboxColumn("Ojos OK?"),   # Nueva columna
                "pico_ok": st.column_config.CheckboxColumn("Pico OK?"),
                "abdomen_ok": st.column_config.CheckboxColumn("Abdomen OK?"),
                "plumon_ok": st.column_config.CheckboxColumn("Plumón OK?"),
                "cuello_ok": st.column_config.CheckboxColumn("Cuello OK?"),
                "peso_gr": st.column_config.NumberColumn("Peso (gr)", format="%.2f"),
                "temp_cloacal": st.column_config.NumberColumn("Temp. Cloacal (°C)", format="%.2f"),
            },
            hide_index=True,
            num_rows="fixed",
            key="data_editor"
        )

        submitted = st.form_submit_button("Guardar Evaluación Completa")

        if submitted:
            if not lote_id or not granja_origen or not evaluador:
                st.error("Por favor, completa todos los campos de información general (ID Lote, Granja, Evaluador).")
            elif not spreadsheet:
                st.error("No se pudo establecer conexión con la base de datos. Revisa la configuración.")
            else:
                with st.spinner("Calculando resultados y guardando datos..."):
                    df = edited_df

                    # --- 1. Realizar Cálculos ---
                    # Puntuación actualizada con campos separados
                    puntuaciones = {
                        'vitalidad_ok': 15, 'ombligo_ok': 15, 
                        'patas_ok': 4.75, 'ojos_ok': 4.75, # Puntuación dividida
                        'pico_ok': 9.5, 'abdomen_ok': 9.5, 'plumon_ok': 9.5, 'cuello_ok': 9.5
                    }
                    df['puntuacion_individual'] = 0
                    for param, score in puntuaciones.items():
                        df['puntuacion_individual'] += df[param] * (score / 10)

                    df['puntuacion_individual'] += np.where(df['peso_gr'] >= 34, 9.5 / 10, 0)
                    puntuacion_final = df['puntuacion_individual'].sum()
                    
                    peso_promedio = df['peso_gr'].mean()
                    pollitos_en_rango = df[df['peso_gr'].between(peso_promedio * 0.9, peso_promedio * 1.1)].shape[0]
                    uniformidad = (pollitos_en_rango / 10) * 100
                    if uniformidad >= 82:
                        puntuacion_final += 13

                    temp_cloacal_promedio = df['temp_cloacal'].mean()
                    
                    desviacion_estandar_peso = df['peso_gr'].std()
                    cv_peso = (desviacion_estandar_peso / peso_promedio) * 100 if peso_promedio > 0 else 0
                    
                    # --- 2. Preparar Datos para Guardar ---
                    resumen_data = [
                        lote_id, granja_origen, linea_genetica, str(fecha_nacimiento), int(cantidad_total), evaluador,
                        float(temp_furgon), float(temp_cascara), float(temp_salon), bool(huevo_sudado), int(aves_por_caja),
                        float(round(temp_cloacal_promedio, 2)), float(round(puntuacion_final, 2)), float(round(uniformidad, 2)),
                        float(round(cv_peso, 2))
                    ]
                    
                    df_detalle = df.copy()
                    df_detalle.insert(0, 'lote_id', lote_id)
                    for col in df_detalle.select_dtypes(include='bool').columns:
                        df_detalle[col] = df_detalle[col].astype(str).str.upper()

                    # Lista de columnas actualizada para guardar
                    columnas_detalle = ['lote_id', 'numero_pollito', 'vitalidad_ok', 'ombligo_ok', 
                                        'patas_ok', 'ojos_ok', 'pico_ok', 'abdomen_ok', 'plumon_ok', 
                                        'cuello_ok', 'peso_gr', 'temp_cloacal']
                    detalle_data = df_detalle[columnas_detalle].values.tolist()

                    # --- 3. Escribir en Google Sheets ---
                    try:
                        sheet_resumen = spreadsheet.worksheet("Lotes_Resumen")
                        sheet_resumen.append_row(resumen_data)
                        
                        sheet_detalle = spreadsheet.worksheet("Pollitos_Detalle")
                        sheet_detalle.append_rows(detalle_data)
                        
                        st.success(f"¡Éxito! Evaluación del lote {lote_id} guardada correctamente.")
                        st.balloons()
                        
                        st.subheader("Resultados Calculados:")
                        res1, res2, res3, res4 = st.columns(4)
                        res1.metric("Puntuación Final", f"{puntuacion_final:.2f} / 100")
                        res2.metric("Uniformidad", f"{uniformidad:.2f} %")
                        res3.metric("Temp. Cloacal Prom.", f"{temp_cloacal_promedio:.2f} °C")
                        res4.metric("CV% del Peso", f"{cv_peso:.2f} %")

                    except gspread.exceptions.WorksheetNotFound:
                        st.error("Error: No se encontraron las hojas 'Lotes_Resumen' o 'Pollitos_Detalle'. Por favor, verifica que existan en tu Google Sheet con los nombres correctos.")
                    except Exception as e:
                        st.error(f"Ocurrió un error al guardar los datos: {e}")

with tab2:
    st.header("Módulo de Evaluación en Transporte")
    st.info("Esta sección está en desarrollo y será el siguiente paso del proyecto.")
    st.image("https://i.imgur.com/Ghv5aX6.jpeg", caption="El transporte es una fase crítica para la calidad del pollito.")

