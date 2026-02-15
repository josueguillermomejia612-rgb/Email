import streamlit as st
from supabase import create_client, Client
from cryptography.fernet import Fernet
import os

class DBManager:
    def __init__(self):
        # Conexión a Supabase usando los secretos de Streamlit
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        self.supabase: Client = create_client(url, key)
        
        # Encriptador de contraseñas de cliente
        self.cipher = Fernet(st.secrets["ENCRYPTION_KEY"].encode('utf-8'))

    def validar_licencia(self, license_key):
        try:
            response = self.supabase.table("licencias_clientes").select("*").eq("license_key", license_key).execute()
            data = response.data
            
            if not data:
                return False, "Licencia no encontrada en la base de datos.", None
                
            user_data = data[0]
            if user_data.get("is_revoked"):
                return False, "Esta licencia ha sido revocada.", None
                
            return True, "OK", user_data
        except Exception as e:
            return False, f"Error de conexión con el servidor: {str(e)}", None

    def guardar_preferencias(self, license_key, correo, password, extensiones):
        # Encriptamos la contraseña del correo del cliente para que viaje segura
        enc_pass = self.cipher.encrypt(password.encode()).decode() if password else ""
        
        data = {
            "correo_guardado": correo,
            "password_encriptada": enc_pass,
            "extensiones_guardadas": extensiones
        }
        
        try:
            self.supabase.table("licencias_clientes").update(data).eq("license_key", license_key).execute()
            return True
        except Exception as e:
            st.error(f"Error al guardar: {e}")
            return False

    def desencriptar_password(self, enc_pass):
        if not enc_pass: 
            return ""
        try:
            return self.cipher.decrypt(enc_pass.encode()).decode()
        except:
            return ""