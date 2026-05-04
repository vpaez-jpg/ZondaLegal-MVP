import streamlit as st
import io
import os
from datetime import datetime
from docxtpl import DocxTemplate
from openai import OpenAI

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Zonda Legal | Sistema de Gestión", layout="centered")

# --- CONEXIÓN SEGURA CON OPENAI ---
# Intentamos leer la clave desde los secretos de Streamlit Cloud, si falla, busca en el entorno local
try:
    api_key = st.secrets["OPENAI_API_KEY"]
except:
    api_key = os.getenv("OPENAI_API_KEY")

cliente_openai = OpenAI(api_key=api_key)

# --- INYECCIÓN DE CSS (DISEÑO CORPORATIVO) ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    html, body, [class*="css"] {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
    }
    .stButton>button {
        border-radius: 4px;
        font-weight: 500;
        transition: all 0.2s ease-in-out;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {
        border-radius: 4px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES AUXILIARES ---
def obtener_fecha_actual():
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    hoy = datetime.now()
    return f"{hoy.day} de {meses[hoy.month - 1]} del {hoy.year}"

if 'usuario_actual' not in st.session_state:
    st.session_state.usuario_actual = None

# ==========================================
# BARRA LATERAL (SIDEBAR)
# ==========================================
with st.sidebar:
    st.title("ZONDA LEGAL")
    st.markdown("---")
    
    if st.session_state.usuario_actual is None:
        st.subheader("Acceso al Sistema")
        usuario_input = st.text_input("Usuario")
        if st.button("Iniciar Sesión", use_container_width=True):
            if usuario_input:
                st.session_state.usuario_actual = usuario_input.lower()
                st.rerun()
    else:
        st.write(f"Usuario activo: **{st.session_state.usuario_actual.capitalize()}**")
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state.usuario_actual = None
            st.rerun()
        
        st.markdown("---")
        st.subheader("Configuración")
        st.info("Cargue su plantilla base (.docx) para continuar.")
        archivo_word = st.file_uploader("Plantilla de Propuesta", type=['docx'], label_visibility="collapsed")

# ==========================================
# PANTALLA PRINCIPAL
# ==========================================
if st.session_state.usuario_actual is None:
    st.header("Bienvenido a la Plataforma de Gestión")
    st.write("Por favor, inicie sesión en el panel lateral para acceder a las herramientas.")
    
elif archivo_word is None:
    st.header("Configuración Requerida")
    st.warning("Para habilitar la generación de documentos, cargue su modelo de Word en el panel lateral.")
    
else:
    st.header("Nueva Propuesta de Registro")
    st.write("Complete los datos básicos. La IA se encargará de redactar las clases correspondientes.")
    
    # FORMULARIO VISUAL
    with st.form("formulario_propuesta"):
        
        col1, col2 = st.columns(2)
        with col1:
            input_cliente = st.text_input("Nombre del Cliente", placeholder="Ej: Diego Maza")
        with col2:
            input_marca = st.text_input("Marca a Registrar", placeholder="Ej: EDESTE")
            
        # NUEVO CAMPO: Solo pedimos a qué se dedican, no las clases exactas
        input_negocio = st.text_area("Descripción del Negocio / Producto", 
                                    height=100, 
                                    placeholder="Ej: Desarrollamos un software de gestión para estudios jurídicos y damos asesoría.")
        
        st.markdown("---")
        st.subheader("Presupuesto")
        
        col3, col4 = st.columns(2)
        with col3:
            input_honorarios = st.number_input("Honorarios Profesionales (ARS)", min_value=0, step=1000, value=230000)
        with col4:
            st.number_input("Arancel INPI Fijo (ARS)", value=36000, disabled=True)
            
        submit_btn = st.form_submit_button("Generar Propuesta Inteligente", type="primary", use_container_width=True)

    # --- LÓGICA DE GENERACIÓN ---
    if submit_btn:
        if input_cliente and input_marca and input_negocio:
            
            with st.spinner("La IA está analizando las clases de Niza correspondientes..."):
                
                # 1. LLAMADA A LA IA PARA LAS CLASES
                instruccion_sistema = """
                Eres un abogado experto en marcas en Argentina y la Clasificación de Niza.
                El usuario te describirá un negocio. Tu tarea es sugerir las clases pertinentes para registrar la marca.
                Devuelve ÚNICAMENTE las clases redactadas en formato de lista con guiones, sin saludos ni introducciones.
                Ejemplo:
                - Clase 9: Software de gestión legal; Programas informáticos...
                - Clase 42: Diseño y desarrollo de software...
                """
                
                respuesta_ia = cliente_openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": instruccion_sistema},
                        {"role": "user", "content": input_negocio}
                    ]
                )
                
                clases_sugeridas = respuesta_ia.choices[0].message.content
                
                # 2. MATEMÁTICA Y FORMATO NUMÉRICO (Sin el símbolo de $)
                arancel_fijo = 36000
                monto_total = input_honorarios + arancel_fijo
                
                # Formateamos con puntos para los miles, pero SIN agregar el $ en Python
                honorarios_str = f"{input_honorarios:,.0f}".replace(',', '.')
                arancel_str = f"{arancel_fijo:,.0f}".replace(',', '.')
                total_str = f"{monto_total:,.0f}".replace(',', '.')
                
                # 3. INYECCIÓN EN EL WORD
                doc = DocxTemplate(archivo_word)
                contexto = {
                    "FECHA": obtener_fecha_actual(),
                    "CLIENTE": input_cliente,
                    "MARCA": input_marca.upper(),
                    "CLASES": clases_sugeridas,
                    "HONORARIOS": honorarios_str,
                    "ARANCEL": arancel_str,
                    "TOTAL": total_str
                }
                doc.render(contexto)
                
                buffer = io.BytesIO()
                doc.save(buffer)
                buffer.seek(0)
                
                st.session_state.word_final = buffer
                st.success("¡Documento y clases generadas exitosamente!")
                
        else:
            st.error("Error: Todos los campos son obligatorios.")

    if 'word_final' in st.session_state:
        st.download_button(
            label="Descargar Propuesta",
            data=st.session_state.word_final,
            file_name=f"Propuesta_{input_cliente.replace(' ', '_')}.docx" if 'input_cliente' in locals() and input_cliente else "Propuesta.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
