import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Método Rodriguez - Calidad de Pollito",
    page_icon="🐔",
    layout="wide"
)

# --- CONEXIÓN A GOOGLE SHEETS ---
def get_google_sheets_connection():
    """Establece conexión con Google Sheets usando los Secrets de Streamlit."""
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict)
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        authorized_creds = creds.with_scopes(scope)
        client = gspread.authorize(authorized_creds)
        # Asegúrate de que el nombre del Google Sheet coincida
        sheet = client.open("BD_Calidad_Pollito").worksheet("Evaluaciones")
        return sheet
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        st.info("Asegúrate de haber configurado los 'Secrets' de Streamlit correctamente con tus credenciales de GCP.")
        return None

sheet = get_google_sheets_connection()

# --- TÍTULO Y DESCRIPCIÓN ---
st.title("🐔 Método Rodriguez: Evaluación de Calidad de Pollito")
st.markdown("Prototipo para la captura de datos en la **Planta de Incubación**.")

# --- BARRA LATERAL - INFORMACIÓN DEL LOTE ---
st.sidebar.header("Información del Lote")
lote_id = st.sidebar.text_input("ID del Lote", f"LOTE-{datetime.date.today().strftime('%Y%m%d')}")
granja_origen = st.sidebar.selectbox("Granja de Origen (Reproductoras)", ["Granja A", "Granja B", "Granja C"])
linea_genetica = st.sidebar.selectbox("Línea Genética", ["Ross 308", "Cobb 500"])
fecha_nacimiento = st.sidebar.date_input("Fecha de Nacimiento", datetime.date.today())
cantidad_total = st.sidebar.number_input("Cantidad Total de Pollitos", min_value=0, step=1000, format="%d")
evaluador = st.sidebar.text_input("Nombre del Evaluador")

# --- PESTAÑAS PRINCIPALES ---
tab1, tab2 = st.tabs(["📋 Parámetros Generales de Incubadora", "📊 Puntuación Calidad de Pollito"])

with tab1:
    st.header("Condiciones Generales en Incubadora")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Temperaturas de Recepción")
        temp_furgon = st.number_input("Temperatura Furgón de Huevo (°C)", value=20.0, step=0.1, format="%.1f")
        temp_cascara = st.number_input("Temperatura Cáscara de Huevo (°C)", value=17.0, step=0.1, format="%.1f")
        temp_salon = st.number_input("Temperatura Salón de Recepción (°C)", value=19.0, step=0.1, format="%.1f")
    with col2:
        st.subheader("Otros Parámetros")
        huevo_sudado = st.radio("Huevo Sudado en Recepción", ["No", "Sí"])
        aves_por_caja = st.number_input("Conteo de Aves por Caja", min_value=0, value=100, format="%d")
        temp_cloacal_promedio = st.number_input("Temperatura Cloacal Promedio (°C)", value=40.0, step=0.1, format="%.1f")

with tab2:
    st.header("Evaluación Individual de 10 Pollitos")

    parametros = {
        "Vitalidad": {"max_score": 15, "desc": "Se demora < 3s en dar la vuelta"},
        "Ombligo": {"max_score": 15, "desc": "Cerrado, sin hilos ni protuberancias"},
        "Patas-Ojos": {"max_score": 9.5, "desc": "Sin codos rojos, sin deshidratación"},
        "Pico": {"max_score": 9.5, "desc": "Limpio, sin alteraciones"},
        "Abdomen": {"max_score": 9.5, "desc": "Suave, no duro ni tenso"},
        "Plumón": {"max_score": 9.5, "desc": "Seco, limpio, sin manchas"},
        "Cuello": {"max_score": 9.5, "desc": "Sin lastimaduras, vacunado"},
    }

    df_eval = pd.DataFrame(columns=list(parametros.keys()) + ["Peso (gr)"])

    cols = st.columns(5)
    for i in range(10):
        col_idx = i % 5
        with cols[col_idx]:
            st.subheader(f"Pollito {i+1}")
            pollito_data = {}
            for param, details in parametros.items():
                es_correcto = st.radio(f"{param}", ["✅", "❌"], key=f"{param}_{i}", horizontal=True, label_visibility="collapsed")
                pollito_data[param] = 1 if es_correcto == "✅" else 0
            
            peso = st.number_input("Peso (gr)", min_value=0.0, step=0.1, key=f"peso_{i}", value=42.0, format="%.1f")
            pollito_data["Peso (gr)"] = peso
            df_eval.loc[i] = pollito_data

    st.markdown("---")
    st.header("Resultados de la Evaluación")
    
    total_score = 0
    uniformidad = 0
    
    if not df_eval.empty:
        pesos_validos = df_eval[df_eval['Peso (gr)'] > 0]['Peso (gr)']

        for param, details in parametros.items():
            puntaje_parametro = df_eval[param].sum() * (details['max_score'] / 10)
            total_score += puntaje_parametro
        
        pollitos_peso_ok = (df_eval["Peso (gr)"] >= 34).sum()
        total_score += pollitos_peso_ok * (9.5 / 10)

        if not pesos_validos.empty and pesos_validos.mean() > 0:
            cv = pesos_validos.std() / pesos_validos.mean()
            uniformidad = (1 - cv) * 100
            if uniformidad >= 82:
                total_score += 13
        
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            st.metric("Puntuación Final (sobre 100)", f"{min(total_score, 100):.2f}")
        with col_res2:
            st.metric("Uniformidad (%)", f"{uniformidad:.2f}%")

        st.dataframe(df_eval)

    # --- BOTÓN DE GUARDADO ---
    if st.button("💾 Guardar Evaluación", type="primary"):
        if not all([lote_id, granja_origen, linea_genetica, fecha_nacimiento, evaluador]):
            st.warning("Por favor, completa toda la 'Información del Lote' en la barra lateral.")
        elif sheet is not None:
            with st.spinner("Guardando datos..."):
                try:
                    new_row = [
                        lote_id, granja_origen, linea_genetica, fecha_nacimiento.strftime("%Y-%m-%d"),
                        int(cantidad_total), evaluador, float(temp_furgon), float(temp_cascara), float(temp_salon),
                        huevo_sudado, int(aves_por_caja), float(temp_cloacal_promedio), 
                        round(min(total_score, 100), 2), round(uniformidad, 2)
                    ]
                    sheet.append_row(new_row)
                    st.success("¡Evaluación guardada con éxito!")
                except Exception as e:
                    st.error(f"Error al escribir en Google Sheets: {e}")
        else:
            st.error("No se pudo guardar. La conexión con la base de datos no está configurada.")
