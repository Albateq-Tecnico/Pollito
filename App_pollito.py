import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np
from datetime import datetime, date
import plotly.graph_objects as go
import plotly.express as px
from io import StringIO

# --- CONFIGURACIÓN DE PÁGINA Y ESTILOS ---
st.set_page_config(page_title="Método Rodriguez - Calidad de Pollito", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
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
        return None

spreadsheet = connect_to_google_sheets()

# --- CARGA Y LIMPIEZA DE DATOS ---
@st.cache_data(ttl=300)
def load_all_data(_spreadsheet):
    if not _spreadsheet:
        return (None,) * 8
    try:
        df_names = {
            "huevo_recepcion": "Huevo_Recepcion", "lotes_resumen": "Lotes_Resumen",
            "pollitos_detalle": "Pollitos_Detalle", "transporte": "Transporte_Evaluacion",
            "granja_resumen": "Granja_Evaluacion", "granja_detalle": "Granja_Detalle_Calidad",
            "seguimiento_resumen": "Seguimiento_7_Dias_Resumen", "seguimiento_detalle": "Seguimiento_7_Dias_Detalle"
        }
        dataframes = {}
        for df_key, sheet_name in df_names.items():
            try:
                worksheet = _spreadsheet.worksheet(sheet_name)
                values = worksheet.get_all_values()
                headers = values.pop(0) if values else []
                dataframes[df_key] = pd.DataFrame(values, columns=headers)
            except gspread.exceptions.WorksheetNotFound:
                dataframes[df_key] = pd.DataFrame()

        for df in dataframes.values():
            if not df.empty:
                id_col = next((col for col in ['id_lote_huevo', 'lote_id'] if col in df.columns), None)
                if id_col:
                    df[id_col] = df[id_col].astype(str).str.strip()
                for col in df.columns:
                    if df[col].dtype == 'object' and '_ok' not in col and 'fecha' not in col and 'hora' not in col:
                        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce')
        return tuple(dataframes.values())
    except Exception as e:
        st.error(f"Ocurrió un error al cargar los datos: {e}")
        return (None,) * 8

# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN ---
def initialize_session_state():
    sample_size = 30
    if 'pollitos_data' not in st.session_state:
        st.session_state.pollitos_data = pd.DataFrame({'numero_pollito': range(1, sample_size + 1), 'vitalidad_ok': True, 'ombligo_ok': True, 'patas_ok': True, 'ojos_ok': True, 'pico_ok': True, 'abdomen_ok': True, 'plumon_ok': True, 'cuello_ok': True, 'peso_gr': 40.0, 'temp_cloacal': 40.0})
    if 'granja_detalle_data' not in st.session_state:
        st.session_state.granja_detalle_data = pd.DataFrame({'numero_pollito': range(1, sample_size + 1), 'vitalidad_ok': True, 'ombligo_ok': True, 'patas_ok': True, 'ojos_ok': True, 'pico_ok': True, 'abdomen_ok': True, 'plumon_ok': True, 'cuello_ok': True, 'peso_granja_gr': 42.0, 'temp_cloacal_granja_c': 40.0})
    if 'huevo_data' not in st.session_state:
        st.session_state.huevo_data = pd.DataFrame({'numero_huevo': range(1, 31), 'peso_huevo_gr': [60.0]*30})
    if 'seguimiento_data' not in st.session_state:
        st.session_state.seguimiento_data = pd.DataFrame({'numero_pollito': range(1, sample_size + 1), 'vitalidad_ok': True, 'ombligo_ok': True, 'patas_ok': True, 'ojos_ok': True, 'pico_ok': True, 'abdomen_ok': True, 'plumon_ok': True, 'cuello_ok': True, 'peso_7d_gr': 180.0})

initialize_session_state()

# --- INTERFAZ DE USUARIO ---
st.sidebar.image("pollito_logo_al.jpg", caption="Calidad desde el Origen")
st.sidebar.markdown("---")
st.sidebar.subheader("Instrucciones de Uso")
st.sidebar.info("Navegue por cada pestaña para registrar y analizar los datos de calidad del lote.")
st.sidebar.markdown("---")
st.sidebar.caption(
    """
    **Nota de Responsabilidad:** Herramienta de apoyo. Su uso es de exclusiva responsabilidad del usuario y no sustituye la asesoría profesional. Albateq S.A. no se hace responsable por las decisiones tomadas.
    
    *Desarrollado por la Dirección Técnica de Albateq con el apoyo del Dr. Manuel Rodríguez Garzón MV.*
    """
)

col_titulo, col_logo = st.columns([3, 1])
with col_titulo:
    st.title("Método Rodriguez: Evaluación de Calidad de Pollito")
with col_logo:
    st.image("logo mejorado_PEQ.png", width=150)

st.markdown("---")

tab_names = ["Paso 0: Recepción Huevo", "Paso 1: Incubadora", "Paso 2: Transporte", "Paso 3: Granja (Recepción)", "Paso 4: Evaluación 7 Días", "Paso 5: Dashboard de Análisis"]
tabs = st.tabs(tab_names)

# --- LÓGICA DE CÁLCULO Y FORMATO ---
def calcular_puntuacion(df, sample_size):
    puntuaciones = {'vitalidad_ok': 15, 'ombligo_ok': 15, 'patas_ok': 9.5, 'ojos_ok': 9.5, 'pico_ok': 7.125, 'abdomen_ok': 7.125, 'plumon_ok': 7.125, 'cuello_ok': 7.125}
    peso_col = next((col for col in ['peso_gr', 'peso_granja_gr', 'peso_7d_gr'] if col in df.columns), None)
    if not peso_col: return 0, 0
    
    for col in puntuaciones.keys():
        if col in df.columns:
            df[col] = df[col].apply(lambda x: str(x).strip().upper() == 'TRUE')

    df['puntuacion_individual'] = sum(df[param] * (score / sample_size) for param, score in puntuaciones.items() if param in df.columns)
    df['puntuacion_individual'] += np.where(df[peso_col] >= 34, 9.5 / sample_size, 0)
    puntuacion_final = df['puntuacion_individual'].sum()
    
    peso_promedio = df[peso_col].mean()
    uniformidad = (df[peso_col].between(peso_promedio * 0.9, peso_promedio * 1.1).sum() / sample_size) * 100
    if uniformidad >= 82:
        puntuacion_final += 13
    return puntuacion_final, uniformidad

def get_score_rating(score):
    if score > 95: return "Excelente", "green"
    if score > 85: return "Bueno", "blue"
    return "Alerta", "red"

# --- PESTAÑAS ---
with tabs[0]: # Paso 0
    with st.form("huevo_form"):
        h_col1, h_col2, h_col3 = st.columns(3)
        with h_col1: lote_id_huevo = st.text_input("ID Lote de Huevo").strip(); granja_origen_huevo = st.text_input("Granja de Origen del Huevo"); edad_reproductoras = st.number_input("Edad Lote Reproductoras (semanas)", 20, 80, 40)
        with h_col2: fecha_recepcion_huevo = st.date_input("Fecha de Recepción"); temp_camion = st.slider("Temperatura del Camión (°C)", 15.0, 25.0, 18.0); tiempo_espera = st.number_input("Tiempo de Espera Descarga (min)", 0, value=15)
        with h_col3: st.write("**Evaluación Física (Muestra)**"); huevos_sucios = st.number_input("N° Huevos Sucios", 0, step=1); huevos_fisurados = st.number_input("N° Huevos Fisurados", 0, step=1); total_muestra = st.number_input("Total Huevos Muestra", 30, value=100, step=10)
        st.markdown("---"); st.subheader("Análisis de Peso (30 Huevos)")
        edited_huevo_df = st.data_editor(st.session_state.huevo_data, hide_index=True, num_rows="fixed")
        if st.form_submit_button("Guardar Evaluación de Huevo"):
            if not lote_id_huevo or not granja_origen_huevo: st.error("ID del Lote y Granja de Origen son obligatorios.")
            else:
                with st.spinner("Guardando..."):
                    df_huevo = edited_huevo_df; porc_sucios = (huevos_sucios / total_muestra) * 100 if total_muestra > 0 else 0; porc_fisurados = (huevos_fisurados / total_muestra) * 100 if total_muestra > 0 else 0; peso_promedio = df_huevo['peso_huevo_gr'].mean(); cv_peso = (df_huevo['peso_huevo_gr'].std() / peso_promedio) * 100 if peso_promedio > 0 else 0
                    huevo_data_row = [lote_id_huevo, granja_origen_huevo, int(edad_reproductoras), str(fecha_recepcion_huevo), float(temp_camion), int(tiempo_espera), round(porc_sucios, 2), round(porc_fisurados, 2), round(peso_promedio, 2), round(cv_peso, 2)]
                    try: spreadsheet.worksheet("Huevo_Recepcion").append_row(huevo_data_row); st.success(f"Evaluación del lote de huevo {lote_id_huevo} guardada.")
                    except Exception as e: st.error(f"Error al guardar: {e}")

with tabs[1]: # Paso 1
    with st.form("info_lote_form"):
        col1, col2, col3 = st.columns(3)
        with col1: lote_id = st.text_input("ID del Lote").strip(); granja_origen = st.text_input("Granja de Origen"); linea_genetica = st.selectbox("Línea Genética", ["Cobb", "Ross", "Otra"])
        with col2: fecha_nacimiento = st.date_input("Fecha de Nacimiento"); cantidad_total = st.number_input("Cantidad Total de Pollitos", 1, step=1000); evaluador = st.text_input("Nombre del Evaluador")
        with col3: temp_furgon = st.slider("Temp. Furgón (°C)", 18.0, 25.0, 22.0); temp_cascara = st.slider("Temp. Cáscara (°C)", 16.0, 20.0, 18.0); temp_salon = st.slider("Temp. Salón (°C)", 18.0, 24.0, 21.0); huevo_sudado = st.toggle("Huevo Sudado", False); aves_por_caja = st.number_input("Aves por Caja", 50, 150, 100)
        st.markdown("---"); st.header("Puntuación Detallada (30 Pollitos)")
        edited_df = st.data_editor(st.session_state.pollitos_data, hide_index=True, num_rows="fixed", key="data_editor_incubadora")
        if st.form_submit_button("Guardar Evaluación de Incubadora"):
            if not lote_id or not granja_origen or not evaluador: st.error("ID del Lote, Granja de Origen y Evaluador son obligatorios.")
            else:
                with st.spinner("Guardando..."):
                    puntuacion_final, uniformidad = calcular_puntuacion(edited_df.copy(), 30)
                    temp_cloacal_promedio = edited_df['temp_cloacal'].mean(); cv_peso = (edited_df['peso_gr'].std() / edited_df['peso_gr'].mean()) * 100 if edited_df['peso_gr'].mean() > 0 else 0
                    resumen_data = [lote_id, granja_origen, linea_genetica, str(fecha_nacimiento), int(cantidad_total), evaluador, float(temp_furgon), float(temp_cascara), float(temp_salon), bool(huevo_sudado), int(aves_por_caja), round(temp_cloacal_promedio, 2), round(puntuacion_final, 2), round(uniformidad, 2), round(cv_peso, 2)]
                    df_detalle = edited_df.copy(); df_detalle.insert(0, 'lote_id', lote_id)
                    for col in df_detalle.select_dtypes(include=['bool']).columns: df_detalle[col] = df_detalle[col].astype(str).str.upper()
                    try: spreadsheet.worksheet("Lotes_Resumen").append_row(resumen_data); spreadsheet.worksheet("Pollitos_Detalle").append_rows(df_detalle.values.tolist()); st.success(f"Evaluación de incubadora del lote {lote_id} guardada.")
                    except Exception as e: st.error(f"Error al guardar: {e}")

with tabs[2]: # Paso 2
    with st.form("transporte_form"):
        t_col1, t_col2, t_col3 = st.columns(3)
        with t_col1: lote_id_transporte = st.text_input("ID del Lote").strip(); fecha_transporte = st.date_input("Fecha"); placa_vehiculo = st.text_input("Placa Vehículo"); conductor = st.text_input("Conductor")
        with t_col2: hora_salida = st.time_input("Hora Salida"); hora_llegada = st.time_input("Hora Llegada"); st.markdown("---"); temp_inicio = st.slider("Temp. Inicio (°C)", 18.0, 35.0, 24.0); hum_inicio = st.slider("Hum. Inicio (%)", 30, 80, 65)
        with t_col3: comportamiento_llegada = st.selectbox("Comportamiento", ["Calmos", "Ruidosos (frío)", "Jadeando (calor)", "Letárgicos"]); mortalidad_transporte = st.number_input("Mortalidad", 0, step=1); st.markdown("---"); temp_final = st.slider("Temp. Final (°C)", 18.0, 35.0, 25.0); hum_final = st.slider("Hum. Final (%)", 30, 80, 70)
        if st.form_submit_button("Guardar Evaluación de Transporte"):
            if not lote_id_transporte: st.error("El 'ID del Lote' es obligatorio.")
            else:
                duracion = (datetime.combine(date.today(), hora_llegada) - datetime.combine(date.today(), hora_salida)).total_seconds() / 60
                transporte_data = [lote_id_transporte, str(fecha_transporte), placa_vehiculo, conductor, str(hora_salida), str(hora_llegada), int(duracion), float(temp_inicio), int(hum_inicio), float(temp_final), int(hum_final), comportamiento_llegada, int(mortalidad_transporte)]
                try: spreadsheet.worksheet("Transporte_Evaluacion").append_row(transporte_data); st.success(f"Evaluación de transporte del lote {lote_id_transporte} guardada.")
                except Exception as e: st.error(f"Error al guardar: {e}")

with tabs[3]: # Paso 3
    with st.form("granja_form"):
        g_col1, g_col2 = st.columns(2)
        with g_col1: lote_id_granja = st.text_input("ID del Lote").strip(); fecha_recepcion = st.date_input("Fecha Recepción"); evaluador_granja = st.text_input("Evaluador en Granja")
        with g_col2: st.subheader("Condiciones del Galpón"); temp_ambiente_c = st.slider("Temp. Ambiente (°C)", 28.0, 35.0, 32.0); hum_relativa_pct = st.slider("Hum. Relativa (%)", 40, 80, 65); temp_cama_c = st.slider("Temp. de Cama (°C)", 28.0, 34.0, 31.0)
        st.markdown("---"); st.header("Puntuación Detallada en Granja (30 Pollitos)")
        edited_granja_df = st.data_editor(st.session_state.granja_detalle_data, hide_index=True, num_rows="fixed", key="data_editor_granja")
        st.markdown("---"); st.subheader("Prueba de Buche Lleno (24h)")
        b_col1, b_col2 = st.columns(2)
        with b_col1: muestra_buche_n = st.number_input("N° Pollitos Muestreados", 30, value=50)
        with b_col2: llenos_buche_24h_n = st.number_input("N° Pollitos con Buche Lleno", 0, value=45)
        if st.form_submit_button("Guardar Evaluación de Recepción"):
            if not lote_id_granja: st.error("El 'ID del Lote' es obligatorio.")
            else:
                with st.spinner("Guardando..."):
                    puntuacion_final_granja, _ = calcular_puntuacion(edited_granja_df.copy(), 30)
                    cv_temp = (edited_granja_df['temp_cloacal_granja_c'].std() / edited_granja_df['temp_cloacal_granja_c'].mean()) * 100 if edited_granja_df['temp_cloacal_granja_c'].mean() > 0 else 0
                    cv_peso_granja = (edited_granja_df['peso_granja_gr'].std() / edited_granja_df['peso_granja_gr'].mean()) * 100 if edited_granja_df['peso_granja_gr'].mean() > 0 else 0
                    buche_lleno_pct = (llenos_buche_24h_n / muestra_buche_n) * 100 if muestra_buche_n > 0 else 0
                    resumen_granja_data = [lote_id_granja, str(fecha_recepcion), evaluador_granja, float(temp_ambiente_c), int(hum_relativa_pct), float(temp_cama_c), round(buche_lleno_pct, 2), round(cv_temp, 2), round(cv_peso_granja, 2), round(puntuacion_final_granja, 2)]
                    df_granja_detalle = edited_granja_df.copy(); df_granja_detalle.insert(0, 'lote_id', lote_id_granja)
                    for col in df_granja_detalle.select_dtypes(include=['bool']).columns: df_granja_detalle[col] = df_granja_detalle[col].astype(str).str.upper()
                    try: spreadsheet.worksheet("Granja_Evaluacion").append_row(resumen_granja_data); spreadsheet.worksheet("Granja_Detalle_Calidad").append_rows(df_granja_detalle.values.tolist()); st.success(f"Evaluación de recepción del lote {lote_id_granja} guardada.")
                    except Exception as e: st.error(f"Error al guardar: {e}")

with tabs[4]: # Paso 4
    with st.form("seguimiento_form"):
        s_col1, s_col2 = st.columns(2)
        with s_col1: lote_id_seg = st.text_input("ID del Lote").strip(); fecha_eval_7d = st.date_input("Fecha de Evaluación (Día 7)")
        with s_col2: mortalidad_7d_n = st.number_input("Mortalidad Acumulada a Día 7", min_value=0, step=1)
        st.markdown("---"); st.header("Evaluación Detallada (30 Pollitos a Día 7)")
        edited_seg_df = st.data_editor(st.session_state.seguimiento_data, hide_index=True, num_rows="fixed", key="data_editor_seguimiento")
        if st.form_submit_button("Guardar Evaluación de 7 Días"):
            if not lote_id_seg: st.error("El ID del Lote es obligatorio.")
            else:
                with st.spinner("Guardando..."):
                    df_seg = edited_seg_df.copy()
                    peso_promedio_7d = df_seg['peso_7d_gr'].mean()
                    cv_peso_7d = (df_seg['peso_7d_gr'].std() / peso_promedio_7d) * 100 if peso_promedio_7d > 0 else 0
                    
                    st.cache_data.clear()
                    h, lotes, p, t, granja, granja_det, sr, sd = load_all_data(spreadsheet)
                    
                    lote_info = lotes[lotes['lote_id'] == lote_id_seg] if lotes is not None and not lotes.empty else pd.DataFrame()
                    granja_detalle_info = granja_det[granja_det['lote_id'] == lote_id_seg] if granja_det is not None and not granja_det.empty else pd.DataFrame()

                    if lote_info.empty:
                        st.error(f"Error: No se encontró el ID de Lote '{lote_id_seg}' en la hoja 'Lotes_Resumen'. Verifique que el ID sea correcto y que ya exista una evaluación de incubadora para este lote.")
                    else:
                        peso_llegada = granja_detalle_info['peso_granja_gr'].mean() if not granja_detalle_info.empty else 0
                        gdp = (peso_promedio_7d - peso_llegada) / 7 if peso_llegada > 0 else 0
                        factor_crecimiento = peso_promedio_7d / peso_llegada if peso_llegada > 0 else 0
                        total_aves = lote_info['cantidad_total'].iloc[0]
                        mortalidad_pct_7d = (mortalidad_7d_n / total_aves) * 100 if total_aves > 0 else 0
                        
                        resumen_data = [lote_id_seg, str(fecha_eval_7d), round(peso_promedio_7d, 2), round(cv_peso_7d, 2), round(gdp, 2), round(factor_crecimiento, 2), int(mortalidad_7d_n), round(mortalidad_pct_7d, 2)]
                        df_seg_detalle = df_seg.copy(); df_seg_detalle.insert(0, 'lote_id', lote_id_seg)
                        for col in df_seg_detalle.select_dtypes(include=['bool']).columns: df_seg_detalle[col] = df_seg_detalle[col].astype(str).str.upper()
                        
                        try:
                            spreadsheet.worksheet("Seguimiento_7_Dias_Resumen").append_row(resumen_data)
                            spreadsheet.worksheet("Seguimiento_7_Dias_Detalle").append_rows(df_seg_detalle.values.tolist())
                            st.success(f"Evaluación de 7 días para el lote {lote_id_seg} guardada.")
                        except Exception as e:
                            st.error(f"Error al guardar en Google Sheets: {e}")

with tabs[5]: # Paso 5
    st.header("Dashboard de Análisis de Lotes")
    if st.button('Refrescar Datos'):
        st.cache_data.clear(); st.rerun()
    
    huevo, lotes, pollitos, transp, granja, granja_det, seguim_res, seguim_det = load_all_data(spreadsheet)

    if lotes is not None and not lotes.empty:
        lote_seleccionado = st.selectbox("Selecciona un Lote para Analizar", options=sorted(lotes['lote_id'].unique(), reverse=True))
        if lote_seleccionado:
            lote_data_df = lotes[lotes['lote_id'] == lote_seleccionado]
            if lote_data_df.empty:
                 st.warning(f"No se encontró información para el lote {lote_seleccionado}.")
                 st.stop()
            lote_data = lote_data_df.iloc[0]
            
            kpi_col, dl_col = st.columns([4, 1])
            with kpi_col: kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
            
            p_inc = lote_data.get('puntuacion_final', 0); rating, r_color = get_score_rating(p_inc); kpi1.markdown(f"**Calidad Incubadora** <h3 style='color:{r_color};'>{p_inc:.1f}</h3>", unsafe_allow_html=True)
            
            granja_data = granja[granja['lote_id'] == lote_seleccionado] if granja is not None else pd.DataFrame()
            if not granja_data.empty:
                p_gra = granja_data.iloc[0].get('puntuacion_final_granja', 0); rating, r_color = get_score_rating(p_gra); caida_calidad = ((p_inc - p_gra) / p_inc) * 100 if p_inc > 0 else 0
                kpi2.metric("Calidad Granja", f"{p_gra:.1f}", delta=f"{-caida_calidad:.1f}%", delta_color="inverse")
                kpi3.metric("% Buche Lleno", f"{granja_data.iloc[0].get('buche_lleno_24h_pct', 0):.1f}%")

            seg_data = seguim_res[seguim_res['lote_id'] == lote_seleccionado] if seguim_res is not None else pd.DataFrame()
            if not seg_data.empty: kpi4.metric("Mortalidad 7d", f"{seg_data.iloc[0].get('mortalidad_acumulada_7d_pct', 0):.2f}%")

            p_inc_w = pollitos[pollitos['lote_id'] == lote_seleccionado]['peso_gr'].mean() if pollitos is not None and not pollitos.empty else 0
            p_gra_w = granja_det[granja_det['lote_id'] == lote_seleccionado]['peso_granja_gr'].mean() if granja_det is not None and not granja_det.empty else 0
            if p_inc_w > 0 and p_gra_w > 0: kpi5.metric("Merma Peso", f"{((p_inc_w - p_gra_w) / p_inc_w) * 100:.2f}%")

            with dl_col:
                st.write(""); st.write("")
                all_dfs = {'lote_resumen': lotes, 'pollitos_incubadora': pollitos, 'transporte': transp, 'granja_resumen': granja, 'pollitos_granja': granja_det, 'seguimiento_resumen': seguim_res, 'seguimiento_detalle': seguim_det}
                output = StringIO()
                for name, df in all_dfs.items():
                    if df is not None and not df.empty:
                        id_col_name = next((col for col in ['id_lote_huevo', 'lote_id'] if col in df.columns), None)
                        if id_col_name:
                            df_lote = df[df[id_col_name] == lote_seleccionado]
                            if not df_lote.empty:
                                output.write(f"--- {name.upper()} ---\n")
                                df_lote.to_csv(output, index=False)
                                output.write("\n\n")
                st.download_button("📥 Descargar CSV", output.getvalue(), f"analisis_lote_{lote_seleccionado}.csv", "text/csv")

            st.markdown("---")
            st.subheader("Evolución de Uniformidad (CV%) y Peso Promedio")
            
            cv_data = {'Incubadora': lote_data.get('cv_peso', 0), 'Granja': granja_data.iloc[0].get('cv_peso_granja_pct', 0) if not granja_data.empty else 0, 'Día 7': seg_data.iloc[0].get('cv_peso_7d_pct', 0) if not seg_data.empty else 0}
            df_cv = pd.DataFrame([cv_data]).T.reset_index(); df_cv.columns = ['Fase', 'CV%']
            
            peso_data = {'Incubadora': p_inc_w, 'Granja': p_gra_w, 'Día 7': seg_data.iloc[0].get('peso_promedio_7d', 0) if not seg_data.empty else 0}
            df_peso = pd.DataFrame([peso_data]).T.reset_index(); df_peso.columns = ['Fase', 'Peso Promedio (gr)']

            plot_col1, plot_col2 = st.columns(2)
            with plot_col1: st.plotly_chart(px.bar(df_cv, x='Fase', y='CV%', title="Evolución del Coeficiente de Variación del Peso", text_auto='.2f'), use_container_width=True)
            with plot_col2: st.plotly_chart(px.bar(df_peso, x='Fase', y='Peso Promedio (gr)', title="Evolución del Peso Promedio", text_auto='.2f'), use_container_width=True)
    else:
        st.info("Aún no hay datos para mostrar.")

