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

# --- CARGA Y LIMPIEZA DE DATOS PARA EL DASHBOARD (VERSIÓN ROBUSTA) ---
@st.cache_data(ttl=600) # Cache por 10 minutos
def load_all_data(_spreadsheet):
    if not _spreadsheet:
        return (None,) * 6
    try:
        df_names = {
            "lotes_resumen": "Lotes_Resumen",
            "pollitos_detalle": "Pollitos_Detalle",
            "transporte": "Transporte_Evaluacion",
            "granja_resumen": "Granja_Evaluacion",
            "granja_detalle": "Granja_Detalle_Temp",
            "seguimiento": "Seguimiento_7_Dias"
        }
        dataframes = {}

        for df_key, sheet_name in df_names.items():
            worksheet = _spreadsheet.worksheet(sheet_name)
            values = worksheet.get_all_values()
            if len(values) < 2:
                dataframes[df_key] = pd.DataFrame()
            else:
                headers = values.pop(0)
                dataframes[df_key] = pd.DataFrame(values, columns=headers)

        for df_name, df in dataframes.items():
            if not df.empty and 'lote_id' in df.columns:
                df['lote_id'] = df['lote_id'].astype(str)

        cols_to_convert = {
            "lotes_resumen": ['cantidad_total', 'temp_cloacal_promedio', 'puntuacion_final', 'uniformidad', 'cv_peso'],
            "pollitos_detalle": ['numero_pollito', 'peso_gr', 'temp_cloacal'],
            "granja_resumen": ['buche_lleno_24h_pct', 'cv_temp_cloacal_pct', 'cv_peso_granja_pct'],
            "granja_detalle": ['numero_pollito', 'temp_cloacal_granja_c', 'peso_granja_gr'],
            "seguimiento": ['mortalidad_7_dias_n']
        }

        for df_name, df in dataframes.items():
            if not df.empty:
                for col in cols_to_convert.get(df_name, []):
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce')
                    else:
                        df[col] = np.nan

        return tuple(dataframes.values())
    except gspread.exceptions.WorksheetNotFound as e:
        st.error(f"Error al cargar datos: La hoja '{e.worksheet_title}' no fue encontrada. Por favor, créala.")
        return (None,) * 6
    except Exception as e:
        st.error(f"Ocurrió un error al cargar los datos para el dashboard: {e}")
        return (None,) * 6


# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN ---
def initialize_session_state():
    if 'pollitos_data' not in st.session_state:
        st.session_state.pollitos_data = pd.DataFrame({'numero_pollito': range(1, 11), 'vitalidad_ok': [False]*10, 'ombligo_ok': [False]*10, 'patas_ok': [False]*10, 'ojos_ok': [False]*10, 'pico_ok': [False]*10, 'abdomen_ok': [False]*10, 'plumon_ok': [False]*10, 'cuello_ok': [False]*10, 'peso_gr': [40.0]*10, 'temp_cloacal': [40.0]*10})
    if 'granja_detalle_data' not in st.session_state:
        st.session_state.granja_detalle_data = pd.DataFrame({'numero_pollito': range(1, 11), 'temp_cloacal_granja_c': [40.0]*10, 'peso_granja_gr': [42.0]*10})

initialize_session_state()

# --- INTERFAZ DE USUARIO ---

# --- BARRA LATERAL ---
st.sidebar.image("pollito_logo_al.jpg", caption="Calidad desde el Origen")
st.sidebar.markdown("---")
st.sidebar.subheader("Instrucciones de Uso")
st.sidebar.info(
    """
    **Paso 1: Incubadora**
    Complete la información del lote y los datos de la muestra de 10 pollitos antes del despacho.

    **Paso 2: Transporte**
    Registre los datos del viaje una vez que el vehículo llegue a la granja.

    **Paso 3: Granja**
    Tome las mediciones de la muestra de pollitos y las condiciones del galpón a la llegada.

    **Paso 4: Seguimiento**
    Pasados 7 días, ingrese la mortalidad acumulada para el lote.

    **Paso 5: Dashboard**
    Seleccione un lote para visualizar sus KPIs, gráficos y recomendaciones.
    """
)
st.sidebar.markdown("---")
# --- MEJORA: Añadir nota de responsabilidad ---
st.sidebar.caption(
    """
    **Nota de Responsabilidad:** Esta es una herramienta de apoyo para uso en granja. La utilización de los resultados es de su exclusiva responsabilidad. No sustituye la asesoría profesional y Albateq S.A. no se hace responsable por las decisiones tomadas con base en la información aquí presentada.
    
    *Desarrollado por la Dirección Técnica de Albateq (dtecnico@albateq.com) con el apoyo del Dr. Manuel Rodríguez Garzón MV.*
    """
)


col_titulo, col_logo = st.columns([3, 1])
with col_titulo:
    st.title("Método Rodriguez: Evaluación de Calidad de Pollito")
with col_logo:
    st.image("logo mejorado_PEQ.png", width=150)

st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Paso 1: Incubadora", "Paso 2: Transporte", "Paso 3: Granja (Recepción)", "Paso 4: Seguimiento 7 Días", "Paso 5: Dashboard de Análisis"])

# Pestañas de captura de datos (1 a 4)
with tab1:
    with st.form("info_lote_form"):
        col1, col2, col3 = st.columns(3);
        with col1: lote_id = st.text_input("ID del Lote"); granja_origen = st.text_input("Granja de Origen"); linea_genetica = st.selectbox("Línea Genética", ["Cobb", "Ross", "Otra"])
        with col2: fecha_nacimiento = st.date_input("Fecha de Nacimiento"); cantidad_total = st.number_input("Cantidad Total de Pollitos", min_value=1, step=1000); evaluador = st.text_input("Nombre del Evaluador")
        with col3: temp_furgon = st.slider("Temperatura Furgón (°C)", 18.0, 25.0, 22.0); temp_cascara = st.slider("Temperatura Cáscara (°C)", 16.0, 20.0, 18.0); temp_salon = st.slider("Temperatura Salón (°C)", 18.0, 24.0, 21.0); huevo_sudado = st.toggle("Huevo Sudado", value=False); aves_por_caja = st.number_input("Aves por Caja", min_value=50, max_value=150, value=100)
        st.markdown("---"); st.header("Puntuación Detallada de la Muestra (10 Pollitos)");
        edited_df = st.data_editor(st.session_state.pollitos_data, hide_index=True, num_rows="fixed", key="data_editor", column_config={"peso_gr": st.column_config.NumberColumn("Peso (gr)", min_value=25, max_value=70, format="%.2f g"), "temp_cloacal": st.column_config.NumberColumn("Temp. Cloacal (°C)", min_value=38, max_value=42, format="%.2f °C")})
        if st.form_submit_button("Guardar Evaluación de Incubadora"):
            if not lote_id or not granja_origen or not evaluador: st.error("Por favor, completa los campos de información general.")
            else:
                with st.spinner("Guardando..."):
                    df = edited_df; puntuaciones = {'vitalidad_ok': 15, 'ombligo_ok': 15, 'patas_ok': 4.75, 'ojos_ok': 4.75, 'pico_ok': 9.5, 'abdomen_ok': 9.5, 'plumon_ok': 9.5, 'cuello_ok': 9.5}; df['puntuacion_individual'] = sum(df[param] * (score / 10) for param, score in puntuaciones.items()); df['puntuacion_individual'] += np.where(df['peso_gr'] >= 34, 9.5 / 10, 0); puntuacion_final = df['puntuacion_individual'].sum(); peso_promedio = df['peso_gr'].mean(); pollitos_en_rango = df[df['peso_gr'].between(peso_promedio * 0.9, peso_promedio * 1.1)].shape[0]; uniformidad = (pollitos_en_rango / 10) * 100;
                    if uniformidad >= 82: puntuacion_final += 13
                    temp_cloacal_promedio = df['temp_cloacal'].mean(); desviacion_estandar_peso = df['peso_gr'].std(); cv_peso = (desviacion_estandar_peso / peso_promedio) * 100 if peso_promedio > 0 else 0; resumen_data = [lote_id, granja_origen, linea_genetica, str(fecha_nacimiento), int(cantidad_total), evaluador, float(temp_furgon), float(temp_cascara), float(temp_salon), bool(huevo_sudado), int(aves_por_caja), round(temp_cloacal_promedio, 2), round(puntuacion_final, 2), round(uniformidad, 2), round(cv_peso, 2)]; df_detalle = df.copy(); df_detalle.insert(0, 'lote_id', lote_id);
                    for col in df_detalle.select_dtypes(include='bool').columns: df_detalle[col] = df_detalle[col].astype(str).str.upper()
                    columnas_detalle = ['lote_id', 'numero_pollito', 'vitalidad_ok', 'ombligo_ok', 'patas_ok', 'ojos_ok', 'pico_ok', 'abdomen_ok', 'plumon_ok', 'cuello_ok', 'peso_gr', 'temp_cloacal']; detalle_data = df_detalle[columnas_detalle].values.tolist();
                    try: spreadsheet.worksheet("Lotes_Resumen").append_row(resumen_data); spreadsheet.worksheet("Pollitos_Detalle").append_rows(detalle_data); st.success(f"¡Éxito! Evaluación de incubadora del lote {lote_id} guardada."); st.balloons();
                    except Exception as e: st.error(f"Error al guardar: {e}")

with tab2:
    with st.form("transporte_form"):
        t_col1, t_col2, t_col3 = st.columns(3);
        with t_col1: lote_id_transporte = st.text_input("ID del Lote"); fecha_transporte = st.date_input("Fecha del Transporte"); placa_vehiculo = st.text_input("Placa del Vehículo"); conductor = st.text_input("Nombre del Conductor");
        with t_col2: hora_salida = st.time_input("Hora de Salida"); hora_llegada = st.time_input("Hora de Llegada"); st.markdown("---"); temp_inicio = st.slider("Temp. Camión Inicio (°C)", 18.0, 35.0, 24.0); hum_inicio = st.slider("Humedad Camión Inicio (%)", 30, 80, 65);
        with t_col3: comportamiento_llegada = st.selectbox("Comportamiento a la Llegada", ["Calmos y distribuidos", "Ruidosos (frío)", "Jadeando (calor)", "Letárgicos"]); mortalidad_transporte = st.number_input("Mortalidad en Transporte", min_value=0, step=1); st.markdown("---"); temp_final = st.slider("Temp. Camión Final (°C)", 18.0, 35.0, 25.0); hum_final = st.slider("Humedad Camión Final (%)", 30, 80, 70);
        if st.form_submit_button("Guardar Evaluación de Transporte"):
            if not lote_id_transporte: st.error("El 'ID del Lote' es obligatorio.")
            else:
                with st.spinner("Guardando..."):
                    datetime_salida = datetime.combine(fecha_transporte, hora_salida); datetime_llegada = datetime.combine(fecha_transporte, hora_llegada); duracion = (datetime_llegada - datetime_salida).total_seconds() / 60;
                    if duracion < 0: duracion = 0
                    transporte_data = [lote_id_transporte, str(fecha_transporte), placa_vehiculo, conductor, str(hora_salida), str(hora_llegada), int(duracion), float(temp_inicio), int(hum_inicio), float(temp_final), int(hum_final), comportamiento_llegada, int(mortalidad_transporte)]
                    try: spreadsheet.worksheet("Transporte_Evaluacion").append_row(transporte_data); st.success(f"¡Éxito! Evaluación de transporte del lote {lote_id_transporte} guardada.")
                    except Exception as e: st.error(f"Error al guardar: {e}")
with tab3:
    with st.form("granja_form"):
        g_col1, g_col2 = st.columns(2);
        with g_col1: lote_id_granja = st.text_input("ID del Lote"); fecha_recepcion = st.date_input("Fecha de Recepción"); evaluador_granja = st.text_input("Nombre del Evaluador en Granja")
        with g_col2: st.subheader("Condiciones del Galpón"); temp_ambiente_c = st.slider("Temperatura Ambiente (°C)", 28.0, 35.0, 32.0); hum_relativa_pct = st.slider("Humedad Relativa (%)", 40, 80, 65); temp_cama_c = st.slider("Temperatura de Cama (°C)", 28.0, 34.0, 31.0)
        st.markdown("---"); st.subheader("Medición Detallada de la Muestra (10 Pollitos)");
        edited_granja_df = st.data_editor(st.session_state.granja_detalle_data, hide_index=True, num_rows="fixed", column_config={"numero_pollito": st.column_config.NumberColumn("Pollito #", disabled=True), "temp_cloacal_granja_c": st.column_config.NumberColumn("Temp. Cloacal (°C)", min_value=38, max_value=42, format="%.2f °C"), "peso_granja_gr": st.column_config.NumberColumn("Peso (gr)", min_value=25, max_value=70, format="%.2f g")})
        st.markdown("---"); st.subheader("Prueba de Buche Lleno (a las 24 horas)");
        b_col1, b_col2 = st.columns(2);
        with b_col1: muestra_buche_n = st.number_input("N° Pollitos Muestreados", min_value=10, value=30)
        with b_col2: llenos_buche_24h_n = st.number_input("N° Pollitos con Buche Lleno", min_value=0, value=25)
        if st.form_submit_button("Guardar Evaluación de Recepción"):
            if not lote_id_granja: st.error("El 'ID del Lote' es obligatorio.")
            else:
                with st.spinner("Guardando..."):
                    df_granja = edited_granja_df; temp_promedio = df_granja['temp_cloacal_granja_c'].mean(); temp_std_dev = df_granja['temp_cloacal_granja_c'].std(); cv_temp = (temp_std_dev / temp_promedio) * 100 if temp_promedio > 0 else 0; peso_promedio_granja = df_granja['peso_granja_gr'].mean(); peso_std_dev_granja = df_granja['peso_granja_gr'].std(); cv_peso_granja = (peso_std_dev_granja / peso_promedio_granja) * 100 if peso_promedio_granja > 0 else 0;
                    buche_lleno_pct = (llenos_buche_24h_n / muestra_buche_n) * 100 if muestra_buche_n > 0 else 0;
                    resumen_granja_data = [lote_id_granja, str(fecha_recepcion), evaluador_granja, float(temp_ambiente_c), int(hum_relativa_pct), float(temp_cama_c), round(buche_lleno_pct, 2), round(cv_temp, 2), round(cv_peso_granja, 2)];
                    df_granja_detalle = df_granja.copy(); df_granja_detalle.insert(0, 'lote_id', lote_id_granja); detalle_granja_data = df_granja_detalle.values.tolist();
                    try: spreadsheet.worksheet("Granja_Evaluacion").append_row(resumen_granja_data); spreadsheet.worksheet("Granja_Detalle_Temp").append_rows(detalle_granja_data); st.success(f"¡Éxito! Evaluación de recepción del lote {lote_id_granja} guardada.")
                    except Exception as e: st.error(f"Error al guardar: {e}")
with tab4:
    with st.form("seguimiento_form"):
        st.info("Registra aquí la mortalidad acumulada al final de la primera semana.");
        s_col1, s_col2 = st.columns(2);
        with s_col1: lote_id_seguimiento = st.text_input("ID del Lote")
        with s_col2: mortalidad_7_dias_n = st.number_input("Mortalidad Acumulada a los 7 Días", min_value=0, step=1)
        if st.form_submit_button("Guardar Datos de Seguimiento"):
            if not lote_id_seguimiento: st.error("El 'ID del Lote' es obligatorio.")
            else:
                with st.spinner("Guardando..."):
                    seguimiento_data = [lote_id_seguimiento, str(date.today()), int(mortalidad_7_dias_n)];
                    try: spreadsheet.worksheet("Seguimiento_7_Dias").append_row(seguimiento_data); st.success(f"¡Éxito! Seguimiento del lote {lote_id_seguimiento} guardada.")
                    except Exception as e: st.error(f"Error al guardar: {e}")

# --- Pestaña 5: Dashboard de Análisis ---
with tab5:
    st.header("Dashboard de Análisis de Lotes")
    
    if st.button('Refrescar Datos'):
        st.cache_data.clear()
        st.rerun()

    lotes_resumen, pollitos_detalle, transporte, granja_resumen, granja_detalle, seguimiento = load_all_data(spreadsheet)

    if lotes_resumen is not None and not lotes_resumen.empty:
        lista_lotes = lotes_resumen['lote_id'].unique().tolist()
        lote_seleccionado = st.selectbox("Selecciona un Lote para Analizar", options=lista_lotes)

        if lote_seleccionado:
            st.markdown(f"### Análisis para el Lote: **{lote_seleccionado}**")
            
            lote_resumen_data_df = lotes_resumen[lotes_resumen['lote_id'] == str(lote_seleccionado)]

            if lote_resumen_data_df.empty:
                st.warning(f"No se encontró un resumen para el lote {lote_seleccionado}. Verifica que los datos se guardaron correctamente.")
            else:
                lote_resumen_data = lote_resumen_data_df.iloc[0]
                kpi1, kpi2, kpi3, kpi4 = st.columns(4)

                puntuacion_final = lote_resumen_data.get('puntuacion_final', 0)
                kpi1.metric("Puntuación Calidad (Incubadora)", f"{puntuacion_final:.2f} / 100")
                
                buche_lleno = 0
                buche_lleno_data = granja_resumen[granja_resumen['lote_id'] == str(lote_seleccionado)]
                if not buche_lleno_data.empty:
                    buche_lleno = buche_lleno_data.iloc[0].get('buche_lleno_24h_pct', 0)
                    kpi2.metric("% Buche Lleno (24h)", f"{buche_lleno:.2f}%")
                
                mortalidad_pct = 0
                mortalidad_data = seguimiento[seguimiento['lote_id'] == str(lote_seleccionado)]
                if not mortalidad_data.empty and not mortalidad_data['mortalidad_7_dias_n'].isnull().all():
                    mortalidad_7d = mortalidad_data['mortalidad_7_dias_n'].iloc[0]
                    total_aves = lote_resumen_data.get('cantidad_total', 0)
                    mortalidad_pct = (mortalidad_7d / total_aves) * 100 if total_aves > 0 else 0
                    kpi3.metric("Mortalidad 7 Días", f"{mortalidad_pct:.2f}%", help=f"{int(mortalidad_7d)} aves")

                merma = 0
                peso_incubadora = pollitos_detalle[pollitos_detalle['lote_id'] == str(lote_seleccionado)]['peso_gr'].mean()
                peso_granja = granja_detalle[granja_detalle['lote_id'] == str(lote_seleccionado)]['peso_granja_gr'].mean()
                if not np.isnan(peso_incubadora) and not np.isnan(peso_granja):
                    merma = ((peso_incubadora - peso_granja) / peso_incubadora) * 100 if peso_incubadora > 0 else 0
                    kpi4.metric("Merma de Peso (%)", f"{merma:.2f}%", help=f"Incubadora: {peso_incubadora:.2f}gr | Granja: {peso_granja:.2f}gr")

                st.markdown("---")
                
                g_col1, g_col2 = st.columns(2)
                with g_col1:
                    st.subheader("Análisis de Defectos (Incubadora)")
                    detalle_lote = pollitos_detalle[pollitos_detalle['lote_id'] == str(lote_seleccionado)]
                    if not detalle_lote.empty:
                        defect_cols = ['vitalidad_ok', 'ombligo_ok', 'patas_ok', 'ojos_ok', 'pico_ok', 'abdomen_ok', 'plumon_ok', 'cuello_ok']
                        defect_counts = {col.replace('_ok', '').capitalize(): (detalle_lote[col].astype(str).str.upper() == 'FALSE').sum() for col in defect_cols}
                        df_defects = pd.DataFrame(list(defect_counts.items()), columns=['Defecto', 'Número de Pollitos']).sort_values(by='Número de Pollitos', ascending=False)
                        st.bar_chart(df_defects.set_index('Defecto'))

                with g_col2:
                    st.subheader("Comparativa de Pesos")
                    pesos_incubadora = pollitos_detalle[pollitos_detalle['lote_id'] == str(lote_seleccionado)]['peso_gr'].dropna()
                    pesos_granja = granja_detalle[granja_detalle['lote_id'] == str(lote_seleccionado)]['peso_granja_gr'].dropna()
                    if not pesos_incubadora.empty or not pesos_granja.empty:
                        fig = go.Figure()
                        if not pesos_incubadora.empty: fig.add_trace(go.Box(y=pesos_incubadora, name='Incubadora', marker_color='blue'))
                        if not pesos_granja.empty: fig.add_trace(go.Box(y=pesos_granja, name='Granja', marker_color='green'))
                        fig.update_layout(title_text="Distribución de Pesos (Incubadora vs. Granja)", yaxis_title="Peso (gramos)")
                        st.plotly_chart(fig, use_container_width=True)

                st.markdown("---")

                st.subheader("Histogramas de Distribución de la Muestra")
                h_col1, h_col2 = st.columns(2)
                with h_col1:
                    fig_hist_peso = px.histogram(pollitos_detalle[pollitos_detalle['lote_id'] == str(lote_seleccionado)], x="peso_gr", title="Distribución de Peso (Incubadora)")
                    st.plotly_chart(fig_hist_peso, use_container_width=True)
                with h_col2:
                    fig_hist_temp = px.histogram(pollitos_detalle[pollitos_detalle['lote_id'] == str(lote_seleccionado)], x="temp_cloacal", title="Distribución de Temp. Cloacal (Incubadora)")
                    st.plotly_chart(fig_hist_temp, use_container_width=True)
                
                st.markdown("---")
                st.subheader("Recomendaciones Automáticas")
                
                if puntuacion_final > 95:
                    st.success("✅ **Calidad de Pollito:** ¡Excelente! El proceso de incubación parece ser óptimo.")
                elif puntuacion_final > 85:
                    st.info("👍 **Calidad de Pollito:** Buena. Revise el gráfico de defectos para identificar áreas de mejora menores.")
                else:
                    st.warning("⚠️ **Calidad de Pollito:** Puntuación baja. Es prioritario analizar el gráfico de defectos para encontrar la causa raíz en la incubadora (ej. ombligos mal curados pueden indicar problemas de T°/humedad en nacedora).")

                if mortalidad_pct == 0:
                    pass
                elif mortalidad_pct < 1:
                    st.success("✅ **Mortalidad 7 Días:** Objetivo cumplido. El arranque del lote ha sido exitoso.")
                elif mortalidad_pct < 2:
                    st.info("👍 **Mortalidad 7 Días:** En el límite del objetivo. Monitoree de cerca las condiciones de manejo y bioseguridad en granja.")
                else:
                    st.error("🚨 **Mortalidad 7 Días:** ¡Alerta! La mortalidad es alta. Se requiere una investigación urgente de las condiciones de transporte, recepción y sanidad del lote.")

                if merma > 0 and merma < 4:
                    st.success("✅ **Merma de Peso:** Controlada. Las condiciones durante el transporte (tiempo, T°, humedad) fueron adecuadas.")
                elif merma >= 4:
                    st.warning("⚠️ **Merma de Peso:** Elevada. Indica posible deshidratación. Revise los tiempos de espera y las condiciones ambientales del vehículo de transporte.")

                if buche_lleno > 95:
                    st.success("✅ **Buche Lleno (24h):** Excelente. El estímulo para el consumo de agua y alimento es óptimo. Verifique que las condiciones se mantengan.")
                elif buche_lleno > 0:
                    st.warning("⚠️ **Buche Lleno (24h):** Por debajo del objetivo. Verifique la disponibilidad y fácil acceso al agua y alimento, la intensidad lumínica y la temperatura de la cama.")
    else:
        st.info("Aún no hay datos para mostrar. Guarda al menos una evaluación completa para empezar a ver los análisis.")

