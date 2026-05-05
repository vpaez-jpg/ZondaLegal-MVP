import streamlit as st
import io
import os
import json
from datetime import datetime
from docxtpl import DocxTemplate
from openai import OpenAI
from audio_recorder_streamlit import audio_recorder
from dotenv import load_dotenv
from fpdf import FPDF

# Librerías para Google Drive
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Zonda Legal | Gestión Cloud", layout="centered")
load_dotenv()

FOLDER_ID_DRIVE = "0ADXRLdoXNiWQUk9PVA"

# --- CONFIGURACIÓN DE GOOGLE DRIVE ---
def obtener_servicio_drive():
    try:
        # 1. Si existe el archivo físico (Local)
        if os.path.exists("service_account.json"):
            with open("service_account.json") as f:
                info = json.load(f)
        # 2. Si no, usamos los secretos (Nube)
        else:
            # IMPORTANTE: Eliminamos el json.loads() porque Streamlit ya lo da procesado
            info = st.secrets["google_auth"]
        
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=['https://www.googleapis.com/auth/drive']
        )
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Error de configuración con Google Drive: {e}")
        return None

drive_service = obtener_servicio_drive()

def buscar_plantilla_en_drive(nombre_usuario):
    query = f"name = '{nombre_usuario}.docx' and '{FOLDER_ID_DRIVE}' in parents and trashed = false"
    results = drive_service.files().list(
        q=query, fields="files(id, name)", includeItemsFromAllDrives=True, supportsAllDrives=True
    ).execute()
    files = results.get('files', [])
    return files[0] if files else None

def descargar_plantilla_desde_drive(file_id):
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return fh

def subir_o_actualizar_plantilla(archivo_bytes, nombre_usuario):
    file_metadata = {'name': f'{nombre_usuario}.docx', 'parents': [FOLDER_ID_DRIVE]}
    media = MediaFileUpload(archivo_bytes, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    existente = buscar_plantilla_en_drive(nombre_usuario)
    if existente:
        drive_service.files().update(fileId=existente['id'], media_body=media, supportsAllDrives=True).execute()
    else:
        drive_service.files().create(body=file_metadata, media_body=media, fields='id', supportsAllDrives=True).execute()

# --- CONEXIÓN OPENAI ---
try:
    api_key = st.secrets["OPENAI_API_KEY"]
except:
    api_key = os.getenv("OPENAI_API_KEY")
cliente_openai = OpenAI(api_key=api_key)

# --- UTILIDADES ---
def obtener_fecha_actual():
    return datetime.now().strftime("%d/%m/%Y")

# --- DISEÑO ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { border-radius: 5px; height: 3em; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- ESTADO DE SESIÓN ---
if 'usuario_actual' not in st.session_state:
    st.session_state.usuario_actual = None
if 'texto_input' not in st.session_state:
    st.session_state.texto_input = ""
if 'ultimo_audio' not in st.session_state:
    st.session_state.ultimo_audio = None
if 'herramienta_actual' not in st.session_state:
    st.session_state.herramienta_actual = "Propuestas"

# ==========================================
# BARRA LATERAL
# ==========================================
with st.sidebar:
    st.title("ZONDA LEGAL")
    if st.session_state.usuario_actual is None:
        usuario_input = st.text_input("Ingresa tu nombre")
        if st.button("Iniciar Sesión"):
            if usuario_input:
                st.session_state.usuario_actual = usuario_input.lower().strip()
                st.rerun()
    else:
        user = st.session_state.usuario_actual
        st.write(f"Hola, **{user.capitalize()}**")
        if st.button("Cerrar Sesión"):
            st.session_state.usuario_actual = None
            st.rerun()
        
        st.markdown("---")
        st.subheader("Herramientas")
        st.session_state.herramienta_actual = st.radio(
            "Selecciona una opción:",
            ["Propuestas", "Cartas Poder"]
        )
        
        st.markdown("---")
        if st.session_state.herramienta_actual == "Propuestas":
            info_drive = buscar_plantilla_en_drive(user)
            if info_drive:
                st.success("✅ Plantilla lista en Drive")
                nuevo_archivo = st.file_uploader("Actualizar plantilla (.docx)", type=['docx'])
                if nuevo_archivo:
                    with open("temp_upload.docx", "wb") as f:
                        f.write(nuevo_archivo.getbuffer())
                    subir_o_actualizar_plantilla("temp_upload.docx", user)
                    st.success("¡Actualizada!")
                    st.rerun()
            else:
                st.warning("No tienes plantilla")
                nuevo_archivo = st.file_uploader("Sube tu modelo (.docx)", type=['docx'])
                if nuevo_archivo:
                    with open("temp_upload.docx", "wb") as f:
                        f.write(nuevo_archivo.getbuffer())
                    subir_o_actualizar_plantilla("temp_upload.docx", user)
                    st.success("¡Guardada en Drive!")
                    st.rerun()

# ==========================================
# PANTALLA PRINCIPAL - RUTEO
# ==========================================
if st.session_state.usuario_actual is None:
    st.header("Zonda Legal")
    st.write("Inicia sesión para continuar.")

# ------------------------------------------
# HERRAMIENTA 1: PROPUESTAS
# ------------------------------------------
elif st.session_state.herramienta_actual == "Propuestas":
    info_drive = buscar_plantilla_en_drive(st.session_state.usuario_actual)
    if info_drive:
        st.header("Generador de Propuestas")
        col1, col2 = st.columns(2)
        with col1:
            input_cliente = st.text_input("Cliente")
        with col2:
            input_marca = st.text_input("Marca")

        # Inicialización de estado conectada directamente a la caja de texto
        if "texto_propuesta" not in st.session_state:
            st.session_state.texto_propuesta = ""

        # Agregamos un key="audio_propuesta" para que no se mezcle con el otro micrófono
        audio_bytes = audio_recorder(text="Hablar", icon_size="2x", pause_threshold=5.0, key="audio_propuesta")
        
        if audio_bytes and audio_bytes != st.session_state.get("ultimo_audio_propuesta"):
            if len(audio_bytes) > 2000:
                with st.spinner("Escuchando..."):
                    archivo_audio = io.BytesIO(audio_bytes)
                    archivo_audio.name = "audio.wav"
                    transcripcion = cliente_openai.audio.transcriptions.create(model="whisper-1", file=archivo_audio)
                    
                    # Almacenamos la transcripción directamente en la llave de la caja de texto
                    st.session_state.texto_propuesta = transcripcion.text
                    st.session_state.ultimo_audio_propuesta = audio_bytes
                    st.rerun()

        # Usamos el key="texto_propuesta" para que se actualice solo
        input_negocio_texto = st.text_area("Descripción del negocio", key="texto_propuesta")
        input_honorarios = st.number_input("Honorarios (ARS)", value=230000)

        if st.button("Generar Propuesta", type="primary"):
            if input_cliente and input_marca and st.session_state.texto_propuesta:
                with st.spinner("Creando documento..."):
                    
                    # PROMPT ESTRICTO PARA EVITAR ASTERISCOS Y SALUDOS
                    instruccion_propuesta = """
                    Eres un abogado experto en marcas en Argentina. El usuario describirá un negocio y debes sugerir las clases de Niza pertinentes.
                    REGLAS ESTRICTAS DE FORMATO:
                    1. NO escribas ningún párrafo introductorio (Ej: Prohibido escribir "Para una marca de ropa..."). Empieza tu respuesta directamente con la lista.
                    2. PROHIBIDO usar formato Markdown. NO uses asteriscos (**) en ningún lado. Escribe en texto plano.
                    3. Usa guiones simples (-) para las viñetas.
                    4. Detalla el número de clase y el contenido específico que le sirve a esa marca.
                    5. Al final de la lista, agrega un único párrafo muy breve avisando que si planea expandir o diversificar el negocio, debería considerar otras clases.
                    """
                    
                    res = cliente_openai.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "system", "content": instruccion_propuesta},
                                  {"role": "user", "content": st.session_state.texto_propuesta}]
                    )
                    clases = res.choices[0].message.content
                    
                    plantilla_io = descargar_plantilla_desde_drive(info_drive['id'])
                    doc = DocxTemplate(plantilla_io)
                    total = input_honorarios + 36000
                    doc.render({
                        "FECHA": obtener_fecha_actual(), "CLIENTE": input_cliente, "MARCA": input_marca.upper(),
                        "CLASES": clases, "HONORARIOS": f"{input_honorarios:,.0f}".replace(",", "."),
                        "ARANCEL": "36.000", "TOTAL": f"{total:,.0f}".replace(",", ".")
                    })
                    final_io = io.BytesIO()
                    doc.save(final_io)
                    final_io.seek(0)
                    st.session_state.word_final = final_io
                    st.success("¡Propuesta lista!")

        if 'word_final' in st.session_state:
            st.download_button("Descargar Archivo", data=st.session_state.word_final, file_name=f"Propuesta_{input_marca}.docx")
    else:
        st.info("Sube una plantilla en la barra lateral para generar propuestas.")

# ------------------------------------------
# HERRAMIENTA 2: CARTAS PODER (NUEVA)
# ------------------------------------------
elif st.session_state.herramienta_actual == "Cartas Poder":
    st.header("Generador Automático de Cartas Poder")
    st.write("Dicta los datos del cliente. La IA detectará automáticamente si es persona física o sociedad.")
    
    # Inicialización de estado para la carta poder
    if "texto_poder" not in st.session_state:
        st.session_state.texto_poder = ""

    # Micrófono independiente
    audio_bytes = audio_recorder(text="Hablar", icon_size="2x", pause_threshold=5.0, key="audio_poder")
    
    if audio_bytes and audio_bytes != st.session_state.get("ultimo_audio_poder"):
        if len(audio_bytes) > 2000: 
            with st.spinner("Escuchando los datos..."):
                try:
                    archivo_audio = io.BytesIO(audio_bytes)
                    archivo_audio.name = "audio.wav"
                    transcripcion = cliente_openai.audio.transcriptions.create(model="whisper-1", file=archivo_audio)
                    
                    # Conectamos transcripción directo a la caja de texto
                    st.session_state.texto_poder = transcripcion.text
                    st.session_state.ultimo_audio_poder = audio_bytes
                    st.rerun()
                except Exception as e:
                    st.error(f"Error procesando el audio: {e}")
        else:
            st.warning("El audio fue muy corto o no se detectó sonido. Intenta de nuevo.")
            st.session_state.ultimo_audio_poder = audio_bytes

    # Usamos key="texto_poder" para que el texto aparezca instantáneamente
    datos_cliente = st.text_area("Datos detectados o escríbalos aquí:", key="texto_poder", height=150)

    if st.button("Generar Carta Poder (PDF)", type="primary"):
        if st.session_state.texto_poder:
            with st.spinner("Analizando tipo de persona y redactando..."):
                instruccion = """
                Eres un asistente legal experto en Argentina. Tu tarea es analizar los datos provistos y redactar SOLO la parte inicial de una carta poder.
                DEBES APLICAR ESTAS REGLAS ESTRICTAS PARA DETECTAR EL TIPO DE PERSONA:
                
                - REGLA JURÍDICA: Si en el texto identificas un tipo social (SAS, S.A., S.R.L., Sociedad, Empresa, etc.), se trata de una PERSONA JURÍDICA. Debes extraer el nombre del representante legal humano, su DNI, el nombre de la sociedad, el CUIT de la sociedad y su domicilio.
                  Ejemplo de redacción exigida: 'El Sr. [NOMBRE REPRESENTANTE], DNI N° [NUMERO], actuando en representación de la sociedad "[NOMBRE SOCIEDAD]", CUIT [NUMERO], con domicilio en [DOMICILIO]...'
                  
                - REGLA FÍSICA: Si solo hay nombres de personas humanas sin tipos sociales, se trata de una PERSONA FÍSICA. Extrae el nombre, DNI/CUIT y domicilio. Si hay varias, menciónalas a todas.
                  Ejemplo de redacción exigida: 'El Sr. [NOMBRE], DNI N° [NUMERO], con domicilio real en [DOMICILIO]...'
                
                Devuelve la respuesta en formato JSON con esta estructura exacta:
                {
                  "encabezado": "El texto de presentación redactado. Termina el texto justo antes de la palabra 'otorga/otorgan'. NO agregues el nombre de los apoderados (Valentín, Franco, etc.).",
                  "verbo": "otorga" (si es una sola persona física o una sola sociedad) u "otorgan" (si son varias personas físicas),
                  "firmantes": [ {"nombre": "NOMBRE DEL FIRMANTE HUMANO", "dni": "NUMERO DE DNI/CUIT"} ]
                }
                """
                
                respuesta_ia = cliente_openai.chat.completions.create(
                    model="gpt-4o",
                    response_format={ "type": "json_object" },
                    messages=[
                        {"role": "system", "content": instruccion},
                        {"role": "user", "content": st.session_state.texto_poder}
                    ]
                )
                
                datos_procesados = json.loads(respuesta_ia.choices[0].message.content)
                encabezado_cliente = datos_procesados.get("encabezado", "")
                verbo = datos_procesados.get("verbo", "otorga")
                firmantes = datos_procesados.get("firmantes", [])

                texto_apoderados = f" por la presente {verbo} a favor del Sr. Valentín Nehuen Páez, DNI N° 42.749.912, con domicilio en calle Las Malvinas 2621, San Rafael, Mendoza, al Sr. Franco Sileoni D´Angelo, DNI N° 42.266.242, con domicilio en calle Barrio puesta del sol, casa 5, Chacras de coria, Mendoza y al Sr. Hugo Matías Bindelli, DNI N° 43.369.631 con domicilio en calle Julio A. Roca 316, Ciudad de Mendoza, Provincia de Mendoza poder amplio para "
                texto_cuerpo = "que en su nombre y representación inicie, entienda e intervenga hasta su total terminación en los procesos administrativos frente al Instituto Nacional de la Propiedad Industrial y la Dirección Nacional de Derechos de Autor, necesarios para la obtención de patentes de invención, modelos de utilidad, marcas, modelos y diseños industriales, derechos de autor y conexos; la renovación de todos ellos, pudiendo presentarse ante las autoridades que corresponda, ya sean nacionales, provinciales o municipales, con intervenciones, solicitudes, declaraciones, descripciones, apelaciones y otros recursos; formular, limitar, modificar y retirar oposiciones, reclamos y llamados de atención; justificar explotaciones y usos; efectuar modificaciones; solicitar testimonios; pedir plazos; retirar, inspeccionar, presentar y recibir documentos; desistir y hacer cuanto fuere menester ante las autoridades administrativas de cualquier orden. Al efecto, lo faculta para que se presente ante las autoridades o terceros particulares que corresponda, con escritos, documentos y cuantos justificativos creyera necesario, ya sea en soporte papel o mediante la utilización de presentaciones electrónicas, para hacer valer sus derechos de propiedad intelectual y asociados; como así también a constituir domicilio electrónico y recibir las notificaciones que a su nombre allí se diligencien, y toda cuanta otra facultad más le fuera necesaria, para mejor desempeño de este mandato y hasta su completa terminación."

                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(0, 10, "CARTA PODER", ln=True, align='C')
                pdf.ln(10)
                
                pdf.set_font("Arial", '', 11)
                texto_completo = f"{encabezado_cliente}{texto_apoderados}{texto_cuerpo}"
                pdf.multi_cell(0, 7, texto_completo.encode('latin-1', 'replace').decode('latin-1'))
                
                pdf.ln(15)
                fecha_str = f"Fecha: {obtener_fecha_actual()}"
                pdf.cell(0, 7, fecha_str, ln=True)
                
                pdf.ln(20)
                for firmante in firmantes:
                    pdf.cell(0, 7, f"Aclaración: {firmante.get('nombre', '')}", ln=True)
                    pdf.cell(0, 7, f"DNI/CUIT: {firmante.get('dni', '')}", ln=True)
                    pdf.cell(0, 7, "Firma: ________________________", ln=True)
                    pdf.ln(15)

                pdf_bytes = bytes(pdf.output()) 
                st.session_state.pdf_final = pdf_bytes
                st.success("¡Carta Poder PDF generada con éxito!")

    if 'pdf_final' in st.session_state and st.session_state.herramienta_actual == "Cartas Poder":
        st.download_button(
            label="Descargar Carta Poder (PDF)",
            data=st.session_state.pdf_final,
            file_name="Carta_Poder.pdf",
            mime="application/pdf"
        )
