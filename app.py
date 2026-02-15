import streamlit as st
import pandas as pd
import zipfile
from datetime import datetime
import io
from streamlit_cookies_controller import CookieController

from email_client import EmailClient
from json_processor import JSONProcessor
from db_manager import DBManager

# Configuración principal
st.set_page_config(page_title="Procesador DTE SaaS", page_icon="🧾", layout="centered")

# Inicializar Controladores
cookie_controller = CookieController()
db = DBManager()

# Inicializar variables de sesión
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_data = None
    st.session_state.license_key = ""

# --- LÓGICA DE AUTO-LOGIN POR COOKIE ---
# Retrasamos la lectura de la cookie medio segundo por cómo funciona Streamlit
saved_cookie = cookie_controller.get("dte_license_cookie")

if saved_cookie and not st.session_state.authenticated:
    valid, msg, user_data = db.validar_licencia(saved_cookie)
    if valid:
        st.session_state.authenticated = True
        st.session_state.license_key = saved_cookie
        st.session_state.user_data = user_data
        st.rerun()

# ==========================================
# PANTALLA DE LOGIN
# ==========================================
if not st.session_state.authenticated:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 Mejia -- ")
        st.markdown("🔐Portal para descargar documentos de correo electronico--  Json, se convierten a XLS automaticamente")
        st.markdown("Ingrese su licencia activa para acceder al sistema.")
        
        lic_input = st.text_input("Clave de Licencia", type="password")
        recordarme = st.checkbox("Recordarme en este equipo", value=True)
        
        if st.button("Ingresar al Sistema", type="primary", use_container_width=True):
            if not lic_input:
                st.warning("Por favor, ingrese su licencia.")
            else:
                with st.spinner("Verificando credenciales..."):
                    valid, msg, user_data = db.validar_licencia(lic_input)
                    if valid:
                        # Guardar cookie si el usuario lo pidió (dura 30 días)
                        if recordarme:
                            cookie_controller.set("dte_license_cookie", lic_input, max_age=30*24*60*60)
                        
                        st.session_state.authenticated = True
                        st.session_state.license_key = lic_input
                        st.session_state.user_data = user_data
                        st.rerun()
                    else:
                        st.error(msg)

# ==========================================
# PANTALLA PRINCIPAL (SISTEMA)
# ==========================================
else:
    # Encabezado con botón de Cerrar Sesión
    header_col1, header_col2 = st.columns([8, 2])
    with header_col1:
        st.title("📧 Gestor Automático DTE")
    with header_col2:
        if st.button("Cerrar Sesión"):
            cookie_controller.remove("dte_license_cookie")
            st.session_state.authenticated = False
            st.rerun()

    st.markdown("---")
    
    # Crear Pestañas
    tab_procesar, tab_config = st.tabs(["▶ Procesar Correos", "⚙️ Configuración / Preferencias"])
    
    user_data = st.session_state.user_data
    
    # Extraer datos guardados del cliente
    correo_actual = user_data.get("correo_guardado", "")
    pass_actual_enc = user_data.get("password_encriptada", "")
    pass_actual = db.desencriptar_password(pass_actual_enc)
    ext_actuales = user_data.get("extensiones_guardadas", ".json, .pdf, .xml")

    # ----------------------------------------
    # PESTAÑA 2: CONFIGURACIÓN (Se carga primero lógicamente)
    # ----------------------------------------
    with tab_config:
        st.subheader("Configuración de su cuenta de correo")
        st.info("Sus datos se guardan encriptados en la nube para su seguridad.")
        
        with st.form("config_form"):
            new_email = st.text_input("Correo Electrónico", value=correo_actual)
            new_pass = st.text_input("Contraseña de Aplicación", value=pass_actual, type="password")
            
            st.subheader("Preferencias de Descarga")
            new_exts = st.text_input("Extensiones a descargar (separadas por coma)", value=ext_actuales)
            
            submit_config = st.form_submit_button("Guardar Preferencias", type="primary")
            
            if submit_config:
                with st.spinner("Guardando en la nube..."):
                    if db.guardar_preferencias(st.session_state.license_key, new_email, new_pass, new_exts):
                        st.success("¡Preferencias guardadas exitosamente!")
                        # Actualizamos la sesión en vivo
                        st.session_state.user_data["correo_guardado"] = new_email
                        st.session_state.user_data["password_encriptada"] = db.cipher.encrypt(new_pass.encode()).decode()
                        st.session_state.user_data["extensiones_guardadas"] = new_exts
                        st.rerun()

    # ----------------------------------------
    # PESTAÑA 1: PROCESAMIENTO
    # ----------------------------------------
    with tab_procesar:
        if not correo_actual or not pass_actual:
            st.warning("⚠️ Parece que es tu primera vez. Ve a la pestaña de **Configuración** y guarda tu correo y contraseña antes de procesar.")
        else:
            st.write(f"Conectando como: **{correo_actual}**")
            
            # Valores por defecto lógicos para las fechas
            hoy = datetime.now().date()
            primer_dia_mes = hoy.replace(day=1)
            
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                prov = st.selectbox("Proveedor", ["gmail", "outlook"])
                # Se asigna el primer día del mes por defecto
                date_from = st.date_input("Buscar Desde", value=primer_dia_mes)
            with col_d2:
                # Se asigna hoy por defecto
                date_to = st.date_input("Buscar Hasta", value=hoy)
                
            if st.button("Iniciar Extracción", type="primary", use_container_width=True):
                
                # Validación para evitar buscar fechas invertidas
                if date_from > date_to:
                    st.error("❌ Error: La fecha 'Desde' no puede ser mayor que la fecha 'Hasta'.")
                else:
                    with st.spinner("Conectando al servidor IMAP y analizando facturas..."):
                        try:
                            client = EmailClient(prov, correo_actual, pass_actual)
                            client.connect()
                            
                            ext_list = [e.strip() for e in ext_actuales.split(',')]
                            
                            filters = {
                                "date_from": date_from.strftime("%d/%m/%Y"),
                                "date_to": date_to.strftime("%d/%m/%Y"),
                                "extensions": ext_list
                            }
                            
                            attachments = client.download_attachments(filters)
                            
                            if not attachments:
                                st.info("No se encontraron adjuntos en este rango de fechas con esas extensiones.")
                            else:
                                processor = JSONProcessor()
                                json_count = 0
                                omit_count = 0
                                
                                # Creamos un archivo ZIP en memoria RAM
                                zip_buffer = io.BytesIO()
                                
                                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                                    for fname, content in attachments:
                                        # Determinamos la extensión para agruparlo en carpetas dentro del ZIP
                                        ext = fname.split('.')[-1].upper() if '.' in fname else 'OTROS'
                                        
                                        if fname.lower().endswith('.json'):
                                            processor.add_json(content, fname)
                                            json_count += 1
                                        else:
                                            omit_count += 1
                                            
                                        # Guardamos TODOS los archivos en el ZIP, organizados por carpetas
                                        folder_name = f"{ext}_Files"
                                        zip_file.writestr(f"{folder_name}/{fname}", content)
                                        
                                st.success(f"Se procesaron {json_count} archivos DTE (JSON). Y se agruparon {omit_count} documentos adicionales en el ZIP.")
                                
                                # Creamos dos columnas para poner los botones de descarga
                                col_btn1, col_btn2 = st.columns(2)
                                
                                # Exportar Excel en memoria RAM solo si hubo JSONs
                                if json_count > 0:
                                    df = pd.DataFrame(processor.data_list)
                                    st.dataframe(df) # Muestra tabla visual
                                    
                                    excel_buffer = io.BytesIO()
                                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                                        df.to_excel(writer, index=False, sheet_name='DTE')
                                    
                                    with col_btn1:
                                        st.download_button(
                                            label="⬇️ Descargar Excel Agrupado",
                                            data=excel_buffer.getvalue(),
                                            file_name=f"DTE_Reporte_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                            type="primary",
                                            use_container_width=True
                                        )
                                
                                # Botón para el ZIP (estará disponible si hubo *cualquier* archivo, JSON o no)
                                if json_count > 0 or omit_count > 0:
                                    with col_btn2:
                                        st.download_button(
                                            label="🗂️ Descargar Documentos (ZIP)",
                                            data=zip_buffer.getvalue(),
                                            file_name=f"Documentos_DTE_{datetime.now().strftime('%Y%m%d')}.zip",
                                            mime="application/zip",
                                            type="secondary",
                                            use_container_width=True
                                        )
                                        
                        except Exception as e:

                            st.error(f"Error de proceso: {str(e)}")

