import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np
from datetime import datetime

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
            'vitalidad_ok': [False] * 10, 'ombligo_ok': [False] * 10,
            'patas_ok': [False] * 10, 'ojos_ok': [False] * 10,
            'pico_ok': [False] * 10, 'abdomen_ok': [False] * 10,
            'plumon_ok': [False] * 10, 'cuello_ok': [False] * 10,
            'peso_gr': [40.0] * 10, 'temp_cloacal': [40.0] * 10
        })

initialize_session_state()

# --- INTERFAZ DE USUARIO ---
st.title("Método Rodriguez: Evaluación de Calidad de Pollito")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["Paso 1: Incubadora", "Paso 2: Transporte", "Paso 3: Granja"])

# --- Pestaña 1: Evaluación en Incubadora ---
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
        edited_df = st.data_editor(st.session_state.pollitos_data, column_config={"numero_pollito": st.column_config.NumberColumn("Pollito #", disabled=True), "vitalidad_ok": st.column_config.CheckboxColumn("Vitalidad OK?"), "ombligo_ok": st.column_config.CheckboxColumn("Ombligo OK?"), "patas_ok": st.column_config.CheckboxColumn("Patas OK?"), "ojos_ok": st.column_config.CheckboxColumn("Ojos OK?"), "pico_ok": st.column_config.CheckboxColumn("Pico OK?"), "abdomen_ok": st.column_config.CheckboxColumn("Abdomen OK?"), "plumon_ok": st.column_config.CheckboxColumn("Plumón OK?"), "cuello_ok": st.column_config.CheckboxColumn("Cuello OK?"), "peso_gr": st.column_config.NumberColumn("Peso (gr)", format="%.2f"), "temp_cloacal": st.column_config.NumberColumn("Temp. Cloacal (°C)", format="%.2f"),}, hide_index=True, num_rows="fixed", key="data_editor")
        submitted_incubadora = st.form_submit_button("Guardar Evaluación de Incubadora")
        if submitted_incubadora:
            if not lote_id or not granja_origen or not evaluador:
                st.error("Por favor, completa todos los campos de información general (ID Lote, Granja, Evaluador).")
            elif not spreadsheet:
                st.error("No se pudo establecer conexión con la base de datos. Revisa la configuración.")
            else:
                with st.spinner("Calculando resultados y guardando datos..."):
                    df = edited_df
                    puntuaciones = {'vitalidad_ok': 15, 'ombligo_ok': 15, 'patas_ok': 4.75, 'ojos_ok': 4.75, 'pico_ok': 9.5, 'abdomen_ok': 9.5, 'plumon_ok': 9.5, 'cuello_ok': 9.5}
                    df['puntuacion_individual'] = sum(df[param] * (score / 10) for param, score in puntuaciones.items())
                    df['puntuacion_individual'] += np.where(df['peso_gr'] >= 34, 9.5 / 10, 0)
                    puntuacion_final = df['puntuacion_individual'].sum()
                    peso_promedio = df['peso_gr'].mean()
                    pollitos_en_rango = df[df['peso_gr'].between(peso_promedio * 0.9, peso_promedio * 1.1)].shape[0]
                    uniformidad = (pollitos_en_rango / 10) * 100
                    if uniformidad >= 82: puntuacion_final += 13
                    temp_cloacal_promedio = df['temp_cloacal'].mean()
                    desviacion_estandar_peso = df['peso_gr'].std()
                    cv_peso = (desviacion_estandar_peso / peso_promedio) * 100 if peso_promedio > 0 else 0
                    resumen_data = [lote_id, granja_origen, linea_genetica, str(fecha_nacimiento), int(cantidad_total), evaluador, float(temp_furgon), float(temp_cascara), float(temp_salon), bool(huevo_sudado), int(aves_por_caja), round(temp_cloacal_promedio, 2), round(puntuacion_final, 2), round(uniformidad, 2), round(cv_peso, 2)]
                    df_detalle = df.copy()
                    df_detalle.insert(0, 'lote_id', lote_id)
                    for col in df_detalle.select_dtypes(include='bool').columns:
                        df_detalle[col] = df_detalle[col].astype(str).str.upper()
                    columnas_detalle = ['lote_id', 'numero_pollito', 'vitalidad_ok', 'ombligo_ok', 'patas_ok', 'ojos_ok', 'pico_ok', 'abdomen_ok', 'plumon_ok', 'cuello_ok', 'peso_gr', 'temp_cloacal']
                    detalle_data = df_detalle[columnas_detalle].values.tolist()
                    try:
                        spreadsheet.worksheet("Lotes_Resumen").append_row(resumen_data)
                        spreadsheet.worksheet("Pollitos_Detalle").append_rows(detalle_data)
                        st.success(f"¡Éxito! Evaluación de incubadora del lote {lote_id} guardada.")
                        st.balloons()
                        st.subheader("Resultados Calculados:")
                        res1, res2, res3, res4 = st.columns(4)
                        res1.metric("Puntuación Final", f"{puntuacion_final:.2f} / 100")
                        res2.metric("Uniformidad", f"{uniformidad:.2f} %")
                        res3.metric("Temp. Cloacal Prom.", f"{temp_cloacal_promedio:.2f} °C")
                        res4.metric("CV% del Peso", f"{cv_peso:.2f} %")
                    except gspread.exceptions.WorksheetNotFound as e:
                        st.error(f"Error: No se encontró la hoja '{e.worksheet_title}'. Verifica que exista en tu Google Sheet.")
                    except Exception as e:
                        st.error(f"Ocurrió un error al guardar los datos: {e}")

# --- Pestaña 2: Evaluación en Transporte ---
with tab2:
    st.header("Módulo de Evaluación en Transporte")
    with st.form("transporte_form"):
        st.info("Registra aquí los datos del viaje desde la incubadora hasta la granja.")
        t_col1, t_col2, t_col3 = st.columns(3)
        with t_col1:
            lote_id_transporte = st.text_input("ID del Lote", help="Debe coincidir con el ID de la evaluación en incubadora.")
            fecha_transporte = st.date_input("Fecha del Transporte")
            placa_vehiculo = st.text_input("Placa del Vehículo")
            conductor = st.text_input("Nombre del Conductor")
        with t_col2:
            hora_salida = st.time_input("Hora de Salida de Incubadora")
            hora_llegada = st.time_input("Hora de Llegada a Granja")
            st.markdown("---")
            temp_inicio = st.slider("Temp. Camión al Inicio (°C)", 18.0, 35.0, 24.0)
            hum_inicio = st.slider("Humedad Camión al Inicio (%)", 30, 80, 65)
        with t_col3:
            comportamiento_llegada = st.selectbox("Comportamiento a la Llegada", ["Calmos y distribuidos uniformemente", "Ruidosos y agrupados (frío)", "Jadeando y apartados (calor)", "Letárgicos o débiles"])
            mortalidad_transporte = st.number_input("Mortalidad en Transporte (N° de aves)", min_value=0, step=1)
            st.markdown("---")
            temp_final = st.slider("Temp. Camión al Final (°C)", 18.0, 35.0, 25.0)
            hum_final = st.slider("Humedad Camión al Final (%)", 30, 80, 70)
        submitted_transporte = st.form_submit_button("Guardar Evaluación de Transporte")
        if submitted_transporte:
            if not lote_id_transporte:
                st.error("El campo 'ID del Lote' es obligatorio para guardar la evaluación.")
            elif not spreadsheet:
                st.error("No se pudo establecer conexión con la base de datos.")
            else:
                with st.spinner("Guardando datos de transporte..."):
                    datetime_salida = datetime.combine(fecha_transporte, hora_salida)
                    datetime_llegada = datetime.combine(fecha_transporte, hora_llegada)
                    duracion = (datetime_llegada - datetime_salida).total_seconds() / 60
                    if duracion < 0: duracion = 0
                    transporte_data = [lote_id_transporte, str(fecha_transporte), placa_vehiculo, conductor, str(hora_salida), str(hora_llegada), int(duracion), float(temp_inicio), int(hum_inicio), float(temp_final), int(hum_final), comportamiento_llegada, int(mortalidad_transporte)]
                    try:
                        sheet_transporte = spreadsheet.worksheet("Transporte_Evaluacion")
                        sheet_transporte.append_row(transporte_data)
                        st.success(f"¡Éxito! Evaluación de transporte del lote {lote_id_transporte} guardada.")
                    except gspread.exceptions.WorksheetNotFound:
                        st.error("Error: No se encontró la hoja 'Transporte_Evaluacion'. Por favor, créala en tu Google Sheet.")
                    except Exception as e:
                        st.error(f"Ocurrió un error al guardar los datos: {e}")

# --- Pestaña 3: Evaluación en Granja ---
with tab3:
    st.header("Módulo de Evaluación en Granja")
    with st.form("granja_form"):
        st.info("Registra las condiciones de recepción y el estado de los pollitos a su llegada a la granja.")
        g_col1, g_col2, g_col3 = st.columns(3)

        with g_col1:
            lote_id_granja = st.text_input("ID del Lote", help="Debe coincidir con el ID de las evaluaciones anteriores.")
            fecha_recepcion = st.date_input("Fecha de Recepción")
            evaluador_granja = st.text_input("Nombre del Evaluador en Granja")

        with g_col2:
            st.subheader("Condiciones del Galpón")
            temp_ambiente_c = st.slider("Temperatura Ambiente (°C)", 28.0, 35.0, 32.0)
            hum_relativa_pct = st.slider("Humedad Relativa (%)", 40, 80, 65)
            temp_cama_c = st.slider("Temperatura de Cama (°C)", 28.0, 34.0, 31.0)
            
        with g_col3:
            st.subheader("Estado del Pollito y Arranque")
            temp_cloacal_granja = st.slider("Temp. Cloacal Promedio (°C)", 39.0, 41.0, 40.0, help="Mida la temperatura de una muestra de 10 pollitos.")
            mortalidad_7_dias_n = st.number_input("Mortalidad Acumulada a los 7 Días", min_value=0, step=1)
            
        st.markdown("---")
        st.subheader("Prueba de Buche Lleno (a las 24 horas)")
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            muestra_buche_n = st.number_input("N° de Pollitos Muestreados para Buche", min_value=10, max_value=100, value=30, step=5)
        with b_col2:
            llenos_buche_24h_n = st.number_input("N° de Pollitos con Buche Lleno", min_value=0, max_value=100, value=25, step=1)

        submitted_granja = st.form_submit_button("Guardar Evaluación de Granja")

        if submitted_granja:
            if not lote_id_granja:
                st.error("El 'ID del Lote' es obligatorio para guardar la evaluación.")
            elif not spreadsheet:
                st.error("No se pudo establecer conexión con la base de datos.")
            else:
                with st.spinner("Guardando datos de la evaluación en granja..."):
                    # Calcular el porcentaje de buche lleno
                    if muestra_buche_n > 0:
                        buche_lleno_pct = (llenos_buche_24h_n / muestra_buche_n) * 100
                    else:
                        buche_lleno_pct = 0
                    
                    # Preparar la fila de datos
                    granja_data = [
                        lote_id_granja, str(fecha_recepcion), evaluador_granja,
                        float(temp_ambiente_c), int(hum_relativa_pct), float(temp_cama_c),
                        float(temp_cloacal_granja), float(round(buche_lleno_pct, 2)),
                        int(mortalidad_7_dias_n)
                    ]

                    # Escribir en la hoja de cálculo
                    try:
                        sheet_granja = spreadsheet.worksheet("Granja_Evaluacion")
                        sheet_granja.append_row(granja_data)
                        st.success(f"¡Éxito! Evaluación en granja del lote {lote_id_granja} guardada.")
                        st.metric("Resultado Clave: % Buche Lleno a 24h", f"{buche_lleno_pct:.2f} %")
                    except gspread.exceptions.WorksheetNotFound:
                        st.error("Error: No se encontró la hoja 'Granja_Evaluacion'. Por favor, créala en tu Google Sheet.")
                    except Exception as e:
                        st.error(f"Ocurrió un error al guardar los datos: {e}")

