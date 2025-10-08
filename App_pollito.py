import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np
from datetime import datetime, date
import plotly.graph_objects as go
import plotly.express as px

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
@st.cache_data(ttl=600)
def load_all_data(_spreadsheet):
    if not _spreadsheet:
        return (None,) * 7
    try:
        df_names = {
            "huevo_recepcion": "Huevo_Recepcion",
            "lotes_resumen": "Lotes_Resumen",
            "pollitos_detalle": "Pollitos_Detalle",
            "transporte": "Transporte_Evaluacion",
            "granja_resumen": "Granja_Evaluacion",
            "granja_detalle": "Granja_Detalle_Calidad",
            "seguimiento": "Seguimiento_7_Dias"
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

        for df_name, df in dataframes.items():
            id_col = 'id_lote_huevo' if 'id_lote_huevo' in df.columns else 'lote_id'
            if not df.empty and id_col in df.columns:
                df[id_col] = df[id_col].astype(str)

        cols_to_convert = {
            "pollitos_detalle": ['numero_pollito', 'peso_gr', 'temp_cloacal'],
            "granja_detalle": ['numero_pollito', 'peso_granja_gr', 'temp_cloacal_granja_c'],
        }

        for df_name, df in dataframes.items():
            if not df.empty:
                for col in df.columns:
                    # Limpiar y convertir todas las columnas que no sean de texto
                    if '_ok' not in col and col not in ['lote_id', 'granja_origen', 'linea_genetica', 'evaluador', 'comportamiento_llegada', 'placa_vehiculo', 'conductor', 'id_lote_huevo', 'fecha_recepcion', 'fecha_nacimiento', 'fecha_transporte']:
                         if df[col].dtype == 'object':
                            df[col] = pd.to_numeric(df[col].str.replace(',', '.'), errors='coerce')

        return tuple(dataframes.values())
    except Exception as e:
        st.error(f"Ocurrió un error al cargar los datos para el dashboard: {e}")
        return (None,) * 7

# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN ---
def initialize_session_state():
    sample_size = 30
    if 'pollitos_data' not in st.session_state:
        st.session_state.pollitos_data = pd.DataFrame({
            'numero_pollito': range(1, sample_size + 1), 'vitalidad_ok': [True] * sample_size, 'ombligo_ok': [True] * sample_size,
            'patas_ok': [True] * sample_size, 'ojos_ok': [True] * sample_size, 'pico_ok': [True] * sample_size, 
            'abdomen_ok': [True] * sample_size, 'plumon_ok': [True] * sample_size, 'cuello_ok': [True] * sample_size,
            'peso_gr': [40.0] * sample_size, 'temp_cloacal': [40.0] * sample_size
        })
    if 'granja_detalle_data' not in st.session_state:
        st.session_state.granja_detalle_data = pd.DataFrame({
            'numero_pollito': range(1, sample_size + 1), 'vitalidad_ok': [True] * sample_size, 'ombligo_ok': [True] * sample_size,
            'patas_ok': [True] * sample_size, 'ojos_ok': [True] * sample_size, 'pico_ok': [True] * sample_size,
            'abdomen_ok': [True] * sample_size, 'plumon_ok': [True] * sample_size, 'cuello_ok': [True] * sample_size,
            'peso_granja_gr': [42.0] * sample_size, 'temp_cloacal_granja_c': [40.0] * sample_size
        })
    if 'huevo_data' not in st.session_state:
        st.session_state.huevo_data = pd.DataFrame({'numero_huevo': range(1, 31), 'peso_huevo_gr': [60.0]*30})

initialize_session_state()

# --- INTERFAZ DE USUARIO ---
st.sidebar.image("pollito_logo_al.jpg", caption="Calidad desde el Origen")
st.sidebar.markdown("---")
st.sidebar.subheader("Instrucciones de Uso")
st.sidebar.info(
    """
    **Paso 0-5:** Navegue por cada pestaña para registrar los datos correspondientes a cada fase del proceso, desde la recepción del huevo hasta el seguimiento en granja y el análisis final en el dashboard.
    """
)
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

tab0, tab1, tab2, tab3, tab4, tab5 = st.tabs(["Paso 0: Recepción Huevo", "Paso 1: Incubadora", "Paso 2: Transporte", "Paso 3: Granja (Recepción)", "Paso 4: Seguimiento 7 Días", "Paso 5: Dashboard de Análisis"])

# --- LÓGICA DE CÁLCULO DE PUNTUACIÓN ---
def calcular_puntuacion(df, sample_size):
    puntuaciones = {'vitalidad_ok': 15, 'ombligo_ok': 15, 'patas_ok': 4.75, 'ojos_ok': 4.75, 'pico_ok': 9.5, 'abdomen_ok': 9.5, 'plumon_ok': 9.5, 'cuello_ok': 9.5}
    peso_col = 'peso_gr' if 'peso_gr' in df.columns else 'peso_granja_gr'
    
    df['puntuacion_individual'] = sum(df[param].astype(bool) * (score / sample_size) for param, score in puntuaciones.items())
    df['puntuacion_individual'] += np.where(df[peso_col] >= 34, 9.5 / sample_size, 0)
    puntuacion_final = df['puntuacion_individual'].sum()
    
    peso_promedio = df[peso_col].mean()
    pollitos_en_rango = df[df[peso_col].between(peso_promedio * 0.9, peso_promedio * 1.1)].shape[0]
    uniformidad = (pollitos_en_rango / sample_size) * 100
    if uniformidad >= 82:
        puntuacion_final += 13
    return puntuacion_final, uniformidad

# Pestañas
with tab0:
    with st.form("huevo_form"):
        # ... (código existente sin cambios) ...
        h_col1, h_col2, h_col3 = st.columns(3)
        with h_col1: lote_id_huevo = st.text_input("ID Lote de Huevo (Ej: LoteGranja_Fecha)"); granja_origen_huevo = st.text_input("Granja de Origen del Huevo"); edad_reproductoras = st.number_input("Edad Lote Reproductoras (semanas)", min_value=20, max_value=80, value=40)
        with h_col2: fecha_recepcion_huevo = st.date_input("Fecha de Recepción"); temp_camion = st.slider("Temperatura del Camión (°C)", 15.0, 25.0, 18.0); tiempo_espera = st.number_input("Tiempo de Espera Descarga (min)", min_value=0, value=15)
        with h_col3: st.write("**Evaluación Física (Muestra)**"); huevos_sucios = st.number_input("N° Huevos Sucios en Muestra", min_value=0, step=1); huevos_fisurados = st.number_input("N° Huevos Fisurados en Muestra", min_value=0, step=1); total_muestra = st.number_input("Total Huevos en Muestra", min_value=30, value=100, step=10)
        st.markdown("---"); st.subheader("Análisis de Peso de la Muestra (30 Huevos)");
        edited_huevo_df = st.data_editor(st.session_state.huevo_data, hide_index=True, num_rows="fixed")
        if st.form_submit_button("Guardar Evaluación de Huevo"):
            if not lote_id_huevo or not granja_origen_huevo: st.error("Por favor, complete al menos el ID del Lote y la Granja de Origen.")
            else:
                with st.spinner("Calculando y guardando..."):
                    df_huevo = edited_huevo_df; porc_sucios = (huevos_sucios / total_muestra) * 100 if total_muestra > 0 else 0; porc_fisurados = (huevos_fisurados / total_muestra) * 100 if total_muestra > 0 else 0; peso_promedio = df_huevo['peso_huevo_gr'].mean(); peso_std = df_huevo['peso_huevo_gr'].std(); cv_peso = (peso_std / peso_promedio) * 100 if peso_promedio > 0 else 0;
                    huevo_data_row = [lote_id_huevo, granja_origen_huevo, int(edad_reproductoras), str(fecha_recepcion_huevo), float(temp_camion), int(tiempo_espera), round(porc_sucios, 2), round(porc_fisurados, 2), round(peso_promedio, 2), round(cv_peso, 2)]
                    try: spreadsheet.worksheet("Huevo_Recepcion").append_row(huevo_data_row); st.success(f"¡Éxito! Evaluación del lote de huevo {lote_id_huevo} guardada.")
                    except Exception as e: st.error(f"Error al guardar: {e}")

with tab1:
    with st.form("info_lote_form"):
        col1, col2, col3 = st.columns(3);
        with col1: lote_id = st.text_input("ID del Lote"); granja_origen = st.text_input("Granja de Origen"); linea_genetica = st.selectbox("Línea Genética", ["Cobb", "Ross", "Otra"])
        with col2: fecha_nacimiento = st.date_input("Fecha de Nacimiento"); cantidad_total = st.number_input("Cantidad Total de Pollitos", min_value=1, step=1000); evaluador = st.text_input("Nombre del Evaluador")
        with col3: temp_furgon = st.slider("Temperatura Furgón (°C)", 18.0, 25.0, 22.0); temp_cascara = st.slider("Temperatura Cáscara (°C)", 16.0, 20.0, 18.0); temp_salon = st.slider("Temperatura Salón (°C)", 18.0, 24.0, 21.0); huevo_sudado = st.toggle("Huevo Sudado", value=False); aves_por_caja = st.number_input("Aves por Caja", min_value=50, max_value=150, value=100)
        st.markdown("---"); st.header("Puntuación Detallada de la Muestra (30 Pollitos)");
        edited_df = st.data_editor(st.session_state.pollitos_data, hide_index=True, num_rows="fixed", key="data_editor_incubadora")
        if st.form_submit_button("Guardar Evaluación de Incubadora"):
            if not lote_id or not granja_origen or not evaluador: st.error("Por favor, completa los campos de información general.")
            else:
                with st.spinner("Guardando..."):
                    puntuacion_final, uniformidad = calcular_puntuacion(edited_df.copy(), 30)
                    temp_cloacal_promedio = edited_df['temp_cloacal'].mean(); cv_peso = (edited_df['peso_gr'].std() / edited_df['peso_gr'].mean()) * 100 if edited_df['peso_gr'].mean() > 0 else 0
                    resumen_data = [lote_id, granja_origen, linea_genetica, str(fecha_nacimiento), int(cantidad_total), evaluador, float(temp_furgon), float(temp_cascara), float(temp_salon), bool(huevo_sudado), int(aves_por_caja), round(temp_cloacal_promedio, 2), round(puntuacion_final, 2), round(uniformidad, 2), round(cv_peso, 2)]
                    df_detalle = edited_df.copy(); df_detalle.insert(0, 'lote_id', lote_id)
                    df_detalle[df_detalle.select_dtypes(include=['bool']).columns] = df_detalle.select_dtypes(include=['bool']).astype(str).apply(lambda x: x.str.upper())
                    try: spreadsheet.worksheet("Lotes_Resumen").append_row(resumen_data); spreadsheet.worksheet("Pollitos_Detalle").append_rows(df_detalle.values.tolist()); st.success(f"¡Éxito! Evaluación de incubadora del lote {lote_id} guardada.")
                    except Exception as e: st.error(f"Error al guardar: {e}")

with tab2:
    # ... (código existente sin cambios) ...
    with st.form("transporte_form"):
        t_col1, t_col2, t_col3 = st.columns(3);
        with t_col1: lote_id_transporte = st.text_input("ID del Lote"); fecha_transporte = st.date_input("Fecha del Transporte"); placa_vehiculo = st.text_input("Placa del Vehículo"); conductor = st.text_input("Nombre del Conductor");
        with t_col2: hora_salida = st.time_input("Hora de Salida"); hora_llegada = st.time_input("Hora de Llegada"); st.markdown("---"); temp_inicio = st.slider("Temp. Camión Inicio (°C)", 18.0, 35.0, 24.0); hum_inicio = st.slider("Humedad Camión Inicio (%)", 30, 80, 65);
        with t_col3: comportamiento_llegada = st.selectbox("Comportamiento a la Llegada", ["Calmos y distribuidos", "Ruidosos (frío)", "Jadeando (calor)", "Letárgicos"]); mortalidad_transporte = st.number_input("Mortalidad en Transporte", min_value=0, step=1); st.markdown("---"); temp_final = st.slider("Temp. Camión Final (°C)", 18.0, 35.0, 25.0); hum_final = st.slider("Humedad Camión Final (%)", 30, 80, 70);
        if st.form_submit_button("Guardar Evaluación de Transporte"):
            if not lote_id_transporte: st.error("El 'ID del Lote' es obligatorio.")
            else:
                with st.spinner("Guardando..."):
                    duracion = (datetime.combine(date.today(), hora_llegada) - datetime.combine(date.today(), hora_salida)).total_seconds() / 60
                    transporte_data = [lote_id_transporte, str(fecha_transporte), placa_vehiculo, conductor, str(hora_salida), str(hora_llegada), int(duracion), float(temp_inicio), int(hum_inicio), float(temp_final), int(hum_final), comportamiento_llegada, int(mortalidad_transporte)]
                    try: spreadsheet.worksheet("Transporte_Evaluacion").append_row(transporte_data); st.success(f"¡Éxito! Evaluación de transporte del lote {lote_id_transporte} guardada.")
                    except Exception as e: st.error(f"Error al guardar: {e}")

with tab3:
    with st.form("granja_form"):
        g_col1, g_col2 = st.columns(2);
        with g_col1: lote_id_granja = st.text_input("ID del Lote"); fecha_recepcion = st.date_input("Fecha de Recepción"); evaluador_granja = st.text_input("Nombre del Evaluador en Granja")
        with g_col2: st.subheader("Condiciones del Galpón"); temp_ambiente_c = st.slider("Temperatura Ambiente (°C)", 28.0, 35.0, 32.0); hum_relativa_pct = st.slider("Humedad Relativa (%)", 40, 80, 65); temp_cama_c = st.slider("Temperatura de Cama (°C)", 28.0, 34.0, 31.0)
        st.markdown("---"); st.header("Puntuación Detallada en Granja (30 Pollitos)");
        edited_granja_df = st.data_editor(st.session_state.granja_detalle_data, hide_index=True, num_rows="fixed", key="data_editor_granja")
        st.markdown("---"); st.subheader("Prueba de Buche Lleno (a las 24 horas)");
        b_col1, b_col2 = st.columns(2);
        with b_col1: muestra_buche_n = st.number_input("N° Pollitos Muestreados", min_value=30, value=50)
        with b_col2: llenos_buche_24h_n = st.number_input("N° Pollitos con Buche Lleno", min_value=0, value=45)
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
                    df_granja_detalle[df_granja_detalle.select_dtypes(include=['bool']).columns] = df_granja_detalle.select_dtypes(include=['bool']).astype(str).apply(lambda x: x.str.upper())
                    try: spreadsheet.worksheet("Granja_Evaluacion").append_row(resumen_granja_data); spreadsheet.worksheet("Granja_Detalle_Calidad").append_rows(df_granja_detalle.values.tolist()); st.success(f"¡Éxito! Evaluación de recepción del lote {lote_id_granja} guardada.")
                    except Exception as e: st.error(f"Error al guardar: {e}")

with tab4:
    # ... (código existente sin cambios) ...
    with st.form("seguimiento_form"):
        st.info("Registra aquí la mortalidad acumulada al final de la primera semana.");
        s_col1, s_col2 = st.columns(2);
        with s_col1: lote_id_seguimiento = st.text_input("ID del Lote")
        with s_col2: mortalidad_7_dias_n = st.number_input("Mortalidad Acumulada a los 7 Días", min_value=0, step=1)
        if st.form_submit_button("Guardar Datos de Seguimiento"):
            if not lote_id_seguimiento: st.error("El 'ID del Lote' es obligatorio.")
            else:
                with st.spinner("Guardando..."):
                    try: spreadsheet.worksheet("Seguimiento_7_Dias").append_row([lote_id_seguimiento, str(date.today()), int(mortalidad_7_dias_n)]); st.success(f"¡Éxito! Seguimiento del lote {lote_id_seguimiento} guardado.")
                    except Exception as e: st.error(f"Error al guardar: {e}")

with tab5:
    st.header("Dashboard de Análisis de Lotes")
    if st.button('Refrescar Datos'):
        st.cache_data.clear(); st.rerun()
    
    huevo_recepcion, lotes_resumen, pollitos_detalle, transporte, granja_resumen, granja_detalle, seguimiento = load_all_data(spreadsheet)

    if lotes_resumen is not None and not lotes_resumen.empty:
        lista_lotes = lotes_resumen['lote_id'].unique().tolist()
        lote_seleccionado = st.selectbox("Selecciona un Lote para Analizar", options=lista_lotes)

        if lote_seleccionado:
            st.markdown(f"### Análisis para el Lote: **{lote_seleccionado}**")
            lote_resumen_data = lotes_resumen[lotes_resumen['lote_id'] == lote_seleccionado].iloc[0]
            
            kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
            puntuacion_incubadora = lote_resumen_data.get('puntuacion_final', 0)
            kpi1.metric("Calidad Incubadora", f"{puntuacion_incubadora:.1f}/100")
            
            puntuacion_granja, buche_lleno, mortalidad_pct, merma = 0, 0, 0, 0
            granja_resumen_data = granja_resumen[granja_resumen['lote_id'] == lote_seleccionado]
            if not granja_resumen_data.empty:
                puntuacion_granja = granja_resumen_data.iloc[0].get('puntuacion_final_granja', 0)
                buche_lleno = granja_resumen_data.iloc[0].get('buche_lleno_24h_pct', 0)
                kpi2.metric("Calidad Granja", f"{puntuacion_granja:.1f}/100")
                kpi3.metric("% Buche Lleno", f"{buche_lleno:.1f}%")

            if puntuacion_incubadora > 0:
                caida_calidad = ((puntuacion_incubadora - puntuacion_granja) / puntuacion_incubadora) * 100 if puntuacion_granja > 0 else 0
                kpi2.metric("Calidad Granja", f"{puntuacion_granja:.1f}/100", delta=f"{-caida_calidad:.1f}% Caída", delta_color="inverse")

            mortalidad_data = seguimiento[seguimiento['lote_id'] == lote_seleccionado]
            if not mortalidad_data.empty and 'mortalidad_7_dias_n' in mortalidad_data.columns and not mortalidad_data['mortalidad_7_dias_n'].isnull().all():
                mortalidad_7d = mortalidad_data['mortalidad_7_dias_n'].iloc[0]; total_aves = lote_resumen_data.get('cantidad_total', 0)
                mortalidad_pct = (mortalidad_7d / total_aves) * 100 if total_aves > 0 else 0
                kpi4.metric("Mortalidad 7 Días", f"{mortalidad_pct:.2f}%", help=f"{int(mortalidad_7d)} aves")

            peso_incubadora = pollitos_detalle[pollitos_detalle['lote_id'] == lote_seleccionado]['peso_gr'].mean()
            peso_granja = granja_detalle[granja_detalle['lote_id'] == lote_seleccionado]['peso_granja_gr'].mean()
            if not np.isnan(peso_incubadora) and not np.isnan(peso_granja):
                merma = ((peso_incubadora - peso_granja) / peso_incubadora) * 100
                kpi5.metric("Merma de Peso", f"{merma:.2f}%")

            # ... (resto del código del dashboard sin cambios) ...

    else:
        st.info("Aún no hay datos para mostrar.")

