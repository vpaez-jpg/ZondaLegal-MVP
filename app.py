import streamlit as st
import io
from datetime import datetime
from docxtpl import DocxTemplate

# --- CONFIGURACIÓN DE PÁGINA ---
# Eliminamos el ícono del emoji y dejamos el título limpio
st.set_page_config(page_title="Zonda Legal | Sistema de Gestión", layout="centered")

# --- INYECCIÓN DE CSS (DISEÑO PREMIUM Y CORPORATIVO) ---
st.markdown("""
    <style>
    /* Ocultar marca de agua y menú de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Forzar tipografía Sans Serif en toda la app por seguridad */
    html, body, [class*="css"] {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
    }
    
    /* Estilizar botones para un look profesional */
    .stButton>button {
        border-radius: 4px;
        font-weight: 500;
        transition: all 0.2s ease-in-out;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    /* Suavizar bordes de los campos de texto */
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

# --- ESTADO DE SESIÓN ---
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
    st.write("Complete los datos del cliente para procesar el documento comercial.")
    
    # FORMULARIO VISUAL (Sin Emojis)
    with st.form("formulario_propuesta"):
        
        col1, col2 = st.columns(2)
        with col1:
            input_cliente = st.text_input("Nombre del Cliente", placeholder="Ej: Diego Maza")
        with col2:
            input_marca = st.text_input("Marca a Registrar", placeholder="Ej: EDESTE")
            
        input_clases = st.text_area("Detalle de Clases y Productos", 
                                    height=150, 
                                    placeholder="- Clase 37: Instalación de aparatos...\n- Clase 39: Suministro de energía...")
        
        st.markdown("---")
        st.subheader("Presupuesto")
        
        col3, col4 = st.columns(2)
        with col3:
            input_honorarios = st.number_input("Honorarios Profesionales (ARS)", min_value=0, step=1000, value=180000)
        with col4:
            st.number_input("Arancel INPI Fijo (ARS)", value=36000, disabled=True)
            
        submit_btn = st.form_submit_button("Procesar Documento", type="primary", use_container_width=True)

    # --- LÓGICA DE GENERACIÓN ---
    if submit_btn:
        if input_cliente and input_marca and input_clases:
            
            arancel_fijo = 36000
            monto_total = input_honorarios + arancel_fijo
            
            honorarios_str = f"$ {input_honorarios:,.0f}".replace(',', '.')
            arancel_str = f"$ {arancel_fijo:,.0f}".replace(',', '.')
            total_str = f"$ {monto_total:,.0f}".replace(',', '.')
            
            doc = DocxTemplate(archivo_word)
            contexto = {
                "FECHA": obtener_fecha_actual(),
                "CLIENTE": input_cliente,
                "MARCA": input_marca.upper(),
                "CLASES": input_clases,
                "HONORARIOS": honorarios_str,
                "ARANCEL": arancel_str,
                "TOTAL": total_str
            }
            doc.render(contexto)
            
            buffer = io.BytesIO()
            doc.save(buffer)
            buffer.seek(0)
            
            st.session_state.word_final = buffer
            st.success("Documento generado exitosamente. Listo para descargar.")
        else:
            st.error("Error: Todos los campos del cliente son obligatorios.")

    if 'word_final' in st.session_state:
        st.download_button(
            label="Descargar Propuesta",
            data=st.session_state.word_final,
            file_name=f"Propuesta_{input_cliente.replace(' ', '_')}.docx" if 'input_cliente' in locals() and input_cliente else "Propuesta.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )