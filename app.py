import streamlit as st
import io
import os
import json
import datetime
from datetime import datetime as dt
from docxtpl import DocxTemplate
from openai import OpenAI
from audio_recorder_streamlit import audio_recorder
from dotenv import load_dotenv
from fpdf import FPDF

# Librerías para Google Drive
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload, MediaIoBaseDownload

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
    return dt.now().strftime("%d/%m/%Y")

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
# BARRA LATERAL Y SEGURIDAD
# ==========================================
USUARIOS_PERMITIDOS = ["plabiano", "vpaez", "hbindelli", "fsileoni", "abindelli", "lcalvo", "svuanello"]
CONTRASENA_GLOBAL = "Palacio14!"

with st.sidebar:
    st.title("ZONDA LEGAL")
    
    # --- PANTALLA DE LOGIN ---
    if st.session_state.usuario_actual is None:
        st.subheader("Acceso Restringido")
        usuario_input = st.text_input("Usuario")
        password_input = st.text_input("Contraseña", type="password")
        
        if st.button("Iniciar Sesión", use_container_width=True):
            usuario_limpio = usuario_input.lower().strip()
            
            # Verificación de doble barrera (Usuario en la lista + Contraseña correcta)
            if usuario_limpio in USUARIOS_PERMITIDOS and password_input == CONTRASENA_GLOBAL:
                st.session_state.usuario_actual = usuario_limpio
                st.rerun()
            else:
                st.error("Credenciales incorrectas o usuario no autorizado.")
                
    # --- PANTALLA DE USUARIO LOGUEADO ---
    else:
        user = st.session_state.usuario_actual
        st.write(f"Abogado/a: **{user}**")
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state.usuario_actual = None
            st.rerun()
        
        st.markdown("---")
        st.subheader("Herramientas")
        st.session_state.herramienta_actual = st.radio(
            "Selecciona una opción:",
            ["Propuestas", "Cartas Poder", "Estatutos SAS", "Derechos de Autor"]
        )
        
        st.markdown("---")
        # --- Lógica exclusiva de la herramienta de Propuestas (Barra lateral) ---
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

# ------------------------------------------
# HERRAMIENTA 3: ESTATUTOS SAS (VERSIÓN DINÁMICA)
# ------------------------------------------
elif st.session_state.herramienta_actual == "Estatutos SAS":
    st.header("Generador de Estatutos SAS Dinámico")
    st.write("Configura la sociedad y los socios. Los cálculos de acciones son automáticos.")

    # 1. BÚSQUEDA DE PLANTILLA
    @st.cache_data(ttl=600)
    def buscar_plantilla_maestra_sas():
        query = f"name = 'plantilla_sas_maestra.docx' and '{FOLDER_ID_DRIVE}' in parents and trashed = false"
        results = drive_service.files().list(
            q=query, fields="files(id, name)", includeItemsFromAllDrives=True, supportsAllDrives=True
        ).execute()
        files = results.get('files', [])
        return files[0] if files else None

    info_maestra = buscar_plantilla_maestra_sas()

    if not info_maestra:
        st.error("⚠️ No se encontró 'plantilla_sas_maestra.docx' en Drive.")
    else:
        # --- SECCIÓN A: DATOS DE LA SOCIEDAD ---
        with st.expander("🏛️ Configuración de la Sociedad", expanded=True):
            col_a, col_b = st.columns(2)
            fecha_const = col_a.text_input("Fecha de constitución", value=obtener_fecha_actual())
            denom_sas = col_b.text_input("Denominación (sin S.A.S.)", placeholder="Ej: CONSTRUCTORRES")
            sede_soc = st.text_input("Sede Social completa", placeholder="Calle..., Ciudad, Mendoza")
            
            col_c, col_d = st.columns(2)
            cap_total = col_c.number_input("Capital Social Total ($)", value=700000, step=1000)
            cant_acc_total = col_d.number_input("Cantidad de Acciones Total", value=7000, step=1)

        # --- SECCIÓN B: GESTIÓN DE SOCIOS ---
        st.markdown("---")
        num_socios = st.number_input("Número de socios", min_value=1, max_value=10, value=2)
        
        lista_socios_datos = []
        nombres_para_selector = []

        # Rango de fechas para el calendario (Desde 1920 hasta hoy)
        fecha_minima = datetime.date(1920, 1, 1)
        fecha_maxima = datetime.date.today()

        tabs_socios = st.tabs([f"Socio {i+1}" for i in range(num_socios)])
        
        for i, tab in enumerate(tabs_socios):
            with tab:
                col1, col2 = st.columns(2)
                s_nom = col1.text_input(f"Nombre y Apellido", key=f"nom_{i}")
                s_dni = col2.text_input(f"DNI", key=f"dni_{i}")
                s_cuit = col1.text_input(f"CUIT/CUIL", key=f"cuit_{i}")
                s_edad = col2.text_input(f"Edad", key=f"edad_{i}")
                s_nac = col1.text_input(f"Nacionalidad", value="argentina", key=f"nac_{i}")
                
                # ¡CALENDARIO CORREGIDO! Ahora permite fechas hasta 1920
                s_fNac_date = col2.date_input(
                    f"Fecha Nacimiento", 
                    value=None, 
                    min_value=fecha_minima, 
                    max_value=fecha_maxima, 
                    format="DD/MM/YYYY", 
                    key=f"fnac_{i}"
                )
                s_fNac = s_fNac_date.strftime("%d/%m/%Y") if s_fNac_date else ""
                
                s_prof = col1.text_input(f"Profesión", key=f"prof_{i}")
                s_est = col2.text_input(f"Estado Civil", key=f"est_{i}")
                s_dom = col1.text_input(f"Domicilio Real", key=f"dom_{i}")
                s_mail = col2.text_input(f"Email", key=f"mail_{i}")
                s_porc = st.slider(f"% de participación", 0, 100, 50 if num_socios==2 else 100//num_socios, key=f"porc_{i}")
                
                s_acc_susc = int((s_porc / 100) * cant_acc_total)
                st.caption(f"Este socio suscribirá {s_acc_susc} acciones.")

                lista_socios_datos.append({
                    "nombre": s_nom, "dni": s_dni, "cuit": s_cuit, "edad": s_edad,
                    "nacionalidad": s_nac, "fecha_nacimiento": s_fNac, "profesion": s_prof,
                    "estado_civil": s_est, "domicilio": s_dom, "email": s_mail,
                    "porcentaje": f"{s_porc}%", "acciones_susc": f"{s_acc_susc:,}".replace(",", ".")
                })
                nombres_para_selector.append(s_nom if s_nom else f"Socio {i+1}")

        # --- SECCIÓN C: ADMINISTRADORES ---
        st.markdown("---")
        with st.expander("💼 Designación de Administradores"):
            idx_t = st.selectbox("Administrador Titular:", range(len(nombres_para_selector)), format_func=lambda x: nombres_para_selector[x])
            idx_s = st.selectbox("Administrador Suplente:", range(len(nombres_para_selector)), index=1 if num_socios > 1 else 0, format_func=lambda x: nombres_para_selector[x])
            
            socio_t = lista_socios_datos[idx_t]
            socio_s = lista_socios_datos[idx_s]

        # --- GENERACIÓN ---
        if st.button("Generar Estatuto SAS", type="primary"):
            errores = []
            if not denom_sas: errores.append("Falta denominación de la sociedad.")
            for i, s in enumerate(lista_socios_datos):
                if not s["nombre"] or not s["dni"] or not s["fecha_nacimiento"]:
                    errores.append(f"Faltan datos en Socio {i+1}.")
            
            total_porc = sum([int(s["porcentaje"].replace("%","")) for s in lista_socios_datos])
            if total_porc != 100: errores.append(f"La suma de porcentajes es {total_porc}%, debe ser 100%.")

            if errores:
                for err in errores: st.error(err)
            else:
                with st.spinner("Generando documento dinámico..."):
                    plantilla_io = descargar_plantilla_desde_drive(info_maestra['id'])
                    doc = DocxTemplate(plantilla_io)
                    
                    contexto = {
                        "FECHA": fecha_const,
                        "DENOMINACION_SAS": denom_sas,
                        "SEDE_SOCIAL": sede_soc,
                        "CAPITAL_SOCIAL": f"{cap_total:,}".replace(",", "."),
                        "CANTIDAD_ACCIONES": f"{cant_acc_total:,}".replace(",", "."),
                        "socios": lista_socios_datos,
                        
                        # Datos precisos para que coincidan con la plantilla
                        "ADMINISTRADOR_TITULAR": socio_t["nombre"],
                        "DNI_ADMINISTRADOR_TITULAR": socio_t["dni"],
                        "CUIT_ADMINISTRADOR_TITULAR": socio_t["cuit"],
                        "EDAD_ADMINISTRADOR_TITULAR": socio_t["edad"],
                        "NACIONALIDAD_ADMINISTRADOR_TITULAR": socio_t["nacionalidad"],
                        "FECHA_NACIMIENTO_ADMINISTRADOR_TITULAR": socio_t["fecha_nacimiento"],
                        "PROFESION_ADMINISTRADOR_TITULAR": socio_t["profesion"],
                        "ESTADO_CIVIL_ADMINISTRADOR_TITULAR": socio_t["estado_civil"],
                        "DOMICILIO_ADMINISTRADOR_TITULAR": socio_t["domicilio"],
                        "EMAIL_ADMINISTRADOR_TITULAR": socio_t["email"], # <--- ¡EMAIL AGREGADO!
                        
                        "ADMINISTRADOR_SUPLENTE": socio_s["nombre"],
                        "DNI_ADMINISTRADOR_SUPLENTE": socio_s["dni"],
                        "CUIT_ADMINISTRADOR_SUPLENTE": socio_s["cuit"],
                        "EDAD_ADMINISTRADOR_SUPLENTE": socio_s["edad"],
                        "NACIONALIDAD_ADMINISTRADOR_SUPLENTE": socio_s["nacionalidad"],
                        "FECHA_NACIMIENTO_ADMINISTRADOR_SUPLENTE": socio_s["fecha_nacimiento"],
                        "PROFESION_ADMINISTRADOR_SUPLENTE": socio_s["profesion"],
                        "ESTADO_CIVIL_ADMINISTRADOR_SUPLENTE": socio_s["estado_civil"],
                        "DOMICILIO_ADMINISTRADOR_SUPLENTE": socio_s["domicilio"],
                        "EMAIL_ADMINISTRADOR_SUPLENTE": socio_s["email"]
                    }
                    
                    doc.render(contexto)
                    final_io = io.BytesIO()
                    doc.save(final_io)
                    final_io.seek(0)
                    st.session_state.sas_final = final_io
                    st.success("¡Estatuto Dinámico Generado!")

    if 'sas_final' in st.session_state and st.session_state.herramienta_actual == "Estatutos SAS":
        st.download_button("Descargar Estatuto SAS", st.session_state.sas_final, f"Estatuto_{denom_sas}.docx")

# ------------------------------------------
# HERRAMIENTA 4: DERECHOS DE AUTOR (CORREGIDA)
# ------------------------------------------
elif st.session_state.herramienta_actual == "Derechos de Autor":
    st.header("Registro de Propiedad Intelectual")
    st.write("Siga los pasos para proteger su creación.")

    if 'paso_dnda' not in st.session_state:
        st.session_state.paso_dnda = 1

    # --- PASO 1: DATOS DE LA OBRA Y AUTORES ---
    if st.session_state.paso_dnda == 1:
        st.subheader("Paso 1: Información de la Obra")
        
        titulo_obra = st.text_input("¿Cómo se llama tu obra?", placeholder="Ej: Mi Gran Canción, Software de Ventas, etc.")
        
        estado_difusion = st.radio(
            "¿La obra ya fue mostrada o lanzada al público?",
            ["No, es INÉDITA (está guardada y nadie la ha visto/escuchado públicamente)", 
             "Sí, ya fue PUBLICADA o difundida (en redes, plataformas, librerías, etc.)"]
        )
        
        tipo_coloquial = st.selectbox(
            "¿Qué tipo de obra quieres proteger?",
            ["Música (Canción, letra o álbum)", "Software, aplicación o código fuente", "Página Web", 
             "Obra Audiovisual (Video, película)", "Obra Artística (Cuadro, foto)", "TV, Radio o Teatro", 
             "Obra Multimedia", "Libro, texto o guion"]
        )
        
        # MOTOR DE CLASIFICACIÓN TAD
        es_inedita = "INÉDITA" in estado_difusion
        if es_inedita:
            if "Música" in tipo_coloquial: nombre_tramite_tad = "Depósito de obra inédita - Música y Letra"
            elif "Software" in tipo_coloquial: nombre_tramite_tad = "Depósito de obra inédita - Software"
            else: nombre_tramite_tad = "Depósito de obra inédita - No musicales"
        else:
            if "Música" in tipo_coloquial: nombre_tramite_tad = "Inscripción de obra publicada - Musical"
            elif "Software" in tipo_coloquial: nombre_tramite_tad = "Inscripción de obra publicada - Software"
            elif "Página Web" in tipo_coloquial: nombre_tramite_tad = "Inscripción de obra publicada - Página Web"
            elif "Artística" in tipo_coloquial: nombre_tramite_tad = "Inscripción de obra publicada - Artística"
            else: nombre_tramite_tad = "Inscripción de obra publicada - Literaria"

        st.markdown("---")
        num_autores = st.number_input("¿Cuántas personas crearon esta obra?", min_value=1, max_value=10, value=1)
        lista_autores_dnda = []
        
        for i in range(int(num_autores)):
            with st.expander(f"👤 Autor {i+1}", expanded=True):
                col1, col2 = st.columns(2)
                a_nom = col1.text_input(f"Nombre / Razón Social", key=f"a_nom_{i}")
                a_doc = col2.text_input(f"DNI / CUIT", key=f"a_doc_{i}")
                a_dom = col1.text_input(f"Domicilio", key=f"a_dom_{i}")
                a_mail = col2.text_input(f"Email", key=f"a_mail_{i}")
                
                tiene_der = st.radio("¿Tiene derechos económicos?", ["Sí", "No"], key=f"a_der_{i}")
                
                # LA LÍNEA CORREGIDA ESTÁ AQUÍ ABAJO:
                a_porc = st.slider("% Titularidad", 0, 100, 100//int(num_autores), key=f"a_porc_{i}") if tiene_der == "Sí" else 0
                
                lista_autores_dnda.append({
                    "nombre": a_nom, "doc": a_doc, "domicilio": a_dom, "email": a_mail, 
                    "es_titular": tiene_der, "porcentaje": f"{a_porc}%"
                })

        detalles_extra = st.text_area("Detalles adicionales:")

        if st.button("Guardar y Continuar", type="primary"):
            if not titulo_obra or not lista_autores_dnda[0]["nombre"]:
                st.error("Completa el título y al menos un autor.")
            else:
                st.session_state.dnda_data = {
                    "TITULO": titulo_obra, "ESTADO": estado_difusion, "TIPO_OBRA": tipo_coloquial, 
                    "TRAMITE_TAD": nombre_tramite_tad, "EXTRAS": detalles_extra, "autores": lista_autores_dnda
                }
                
                with st.spinner("Creando expediente y generando resumen..."):
                    try:
                        # 1. CREAR CARPETA PRIVADA
                        nombre_f = f"DNDA - {lista_autores_dnda[0]['nombre']} - {titulo_obra}"
                        meta = {'name': nombre_f, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [FOLDER_ID_DRIVE]}
                        folder = drive_service.files().create(body=meta, fields='id', supportsAllDrives=True).execute()
                        
                        # Guardamos el ID de esta carpeta para usarlo en el Paso 2
                        st.session_state.id_carpeta_drive = folder['id'] 

                        # 2. GENERAR WORD RESUMEN
                        query = f"name = 'plantilla_maestra_dnda.docx' and '{FOLDER_ID_DRIVE}' in parents and trashed = false"
                        res = drive_service.files().list(q=query, includeItemsFromAllDrives=True, supportsAllDrives=True).execute()
                        
                        if not res.get('files'):
                            st.error("❌ No se encontró 'plantilla_maestra_dnda.docx' en la carpeta Zonda_Templates.")
                        else:
                            p_io = descargar_plantilla_desde_drive(res['files'][0]['id'])
                            doc = DocxTemplate(p_io)
                            doc.render(st.session_state.dnda_data)
                            
                            buffer = io.BytesIO()
                            doc.save(buffer)
                            buffer.seek(0)
                            
                            file_meta = {'name': f'RESUMEN_{titulo_obra}.docx', 'parents': [st.session_state.id_carpeta_drive]}
                            media = MediaIoBaseUpload(buffer, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document', resumable=True)
                            drive_service.files().create(body=file_meta, media_body=media, supportsAllDrives=True).execute()
                            
                            # Avanzamos al paso 2
                            st.session_state.paso_dnda = 2
                            st.rerun()

                    except Exception as e:
                        st.error(f"Ocurrió un error técnico generando el documento: {e}")

    # --- PASO 2: SUBIR LA OBRA (NATIVO EN STREAMLIT + LINK EXTERNO) ---
    elif st.session_state.paso_dnda == 2:
        st.subheader("Paso 2: Subir copia de la obra")
        st.info(f"Expediente interno creado para: **{st.session_state.dnda_data['TITULO']}**")
        
        st.write("Nuestro sistema resguardará su obra directamente en la bóveda privada del estudio.")
        
        # --- OPCIÓN A: Subida directa ---
        st.markdown("#### Opción A: Archivos normales (Hasta 200 MB)")
        archivo_obra = st.file_uploader("Selecciona o arrastra tu archivo aquí (PDF, MP3, MP4, ZIP, etc.)")
        
        st.markdown("---")
        
        # --- OPCIÓN B: Archivos pesados ---
        st.markdown("#### Opción B: Archivos muy pesados (+200 MB)")
        st.write("Si tu archivo es muy grande o son varios documentos pesados, puedes subirlos a tu propia cuenta de Google Drive y pegarnos el link aquí.")
        
        with st.expander("Ver instructivo paso a paso para crear y compartir la carpeta"):
            st.markdown("""
            **Cómo compartir tu obra por Google Drive:**
            1. Entra a tu cuenta de Google Drive y crea una carpeta nueva.
            2. Sube el archivo de tu obra dentro de esa carpeta.
            3. Haz clic derecho sobre el nombre de la carpeta y selecciona **Compartir** > **Compartir**.
            4. En la ventana que se abre, busca abajo donde dice "Acceso general".
            5. Cambia la opción de "Restringido" a **"Cualquier persona con el enlace"**.
            6. Haz clic en el botón **"Copiar enlace"** y pega ese texto en la casilla de abajo.
            """)
            
        link_externo = st.text_input("Pega aquí el link de tu carpeta de Google Drive:")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("Enviar obra y Continuar", type="primary"):
            # Validación: Debe haber subido un archivo O pegado un link
            if not archivo_obra and not link_externo:
                st.error("Por favor, sube un archivo (Opción A) o pega el link de Google Drive (Opción B) para continuar.")
            else:
                with st.spinner("Procesando y transfiriendo a la bóveda..."):
                    try:
                        # Si subió archivo directo (Opción A)
                        if archivo_obra:
                            file_meta = {'name': archivo_obra.name, 'parents': [st.session_state.id_carpeta_drive]}
                            buffer_archivo = io.BytesIO(archivo_obra.getvalue())
                            media = MediaIoBaseUpload(buffer_archivo, mimetype=archivo_obra.type, resumable=True)
                            drive_service.files().create(body=file_meta, media_body=media, supportsAllDrives=True).execute()
                        
                        # Si pegó un link (Opción B)
                        if link_externo:
                            # Creamos un archivo de texto con el link para guardarlo en la bóveda
                            txt_content = f"LINK A LA OBRA PESADA PROVISTO POR EL CLIENTE:\n\n{link_externo}".encode('utf-8')
                            buffer_txt = io.BytesIO(txt_content)
                            file_meta_txt = {'name': 'LINK_OBRA.txt', 'parents': [st.session_state.id_carpeta_drive]}
                            media_txt = MediaIoBaseUpload(buffer_txt, mimetype='text/plain', resumable=True)
                            drive_service.files().create(body=file_meta_txt, media_body=media_txt, supportsAllDrives=True).execute()

                        st.session_state.paso_dnda = 3
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al procesar la obra: {e}")

    # --- PASO 3: TAD (BOTÓN CORREGIDO) ---
    elif st.session_state.paso_dnda == 3:
        st.subheader("Paso 3: Autorización Legal (TAD)")
        t_tad = st.session_state.dnda_data['TRAMITE_TAD']
        st.markdown(f"""
        1. Ingrese a [TAD](https://tramitesadistancia.gob.ar/) con Clave Fiscal.
        2. Vaya a la pestaña **APODERADOS**.
        3. En “Apoderados por mí” agregue el CUIL **20427499120**.
        4. Seleccione *“Especificar trámites...”* y busque: **"{t_tad}"**.
        5. Confirme.
        """)
        
        if st.checkbox("Ya realicé el apoderamiento en TAD"):
            if st.button("Finalizar Registro", type="primary"):
                st.balloons()
                st.success("¡Excelente! Hemos recibido toda la información. Nuestro equipo revisará los archivos y le informaremos cuando el trámite esté ingresado.")
