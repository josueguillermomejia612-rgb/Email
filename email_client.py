import imaplib
import email
from email.header import decode_header
import os
from datetime import datetime, timedelta
from config import EMAIL_CONFIG

class EmailClient:
    def __init__(self, provider, email_user, password):
        self.provider = provider
        self.email_user = email_user
        self.email_pass = password
        self.server = None
        
        if provider.lower() == 'gmail':
            self.imap_url = EMAIL_CONFIG['gmail']['imap_server']
        elif provider.lower() == 'outlook':
            self.imap_url = EMAIL_CONFIG['outlook']['imap_server']
        else:
            raise ValueError("Proveedor no soportado.")

    def connect(self):
        try:
            self.server = imaplib.IMAP4_SSL(self.imap_url)
            self.server.login(self.email_user, self.email_pass)
            self.server.select("INBOX")
        except Exception as e:
            raise Exception(f"Error de conexión IMAP: {str(e)}")

    def _get_imap_date(self, date_obj):
        """Fuerza la fecha en inglés estricto para evitar errores de idioma del SO"""
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return f"{date_obj.day:02d}-{months[date_obj.month - 1]}-{date_obj.year}"

    def download_attachments(self, filters):
        attachments = []
        search_parts = []
        
        if filters.get('sender'):
            search_parts.append(f'FROM "{filters["sender"]}"')
        if filters.get('subject'):
            search_parts.append(f'SUBJECT "{filters["subject"]}"')
            
        if filters.get('date_from'):
            date_obj = datetime.strptime(filters['date_from'], "%d/%m/%Y")
            imap_date = self._get_imap_date(date_obj)
            search_parts.append(f'SINCE {imap_date}')
            
        if filters.get('date_to'):
            date_obj = datetime.strptime(filters['date_to'], "%d/%m/%Y")
            date_obj += timedelta(days=1) # IMAP BEFORE excluye el día exacto
            imap_date = self._get_imap_date(date_obj)
            search_parts.append(f'BEFORE {imap_date}')

        search_criteria = " ".join(search_parts) if search_parts else 'ALL'
        
        # Depuración: Ver en la terminal qué estamos buscando exactamente
        print(f"\n[DEBUG IMAP] Criterio de búsqueda: {search_criteria}")
        
        status, messages = self.server.search(None, search_criteria)
        if status != 'OK': 
            print(f"[DEBUG IMAP] Servidor rechazó la búsqueda. Status: {status}")
            return []

        msg_ids = messages[0].split()
        print(f"[DEBUG IMAP] Correos encontrados que coinciden con la fecha: {len(msg_ids)}")
        
        # Limitar a 1000 SOLO si el usuario no aplicó ningún filtro
        if not search_parts and len(msg_ids) > 1000:
            msg_ids = msg_ids[-1000:]

        # Normalizamos las extensiones del filtro para asegurar que tengan el punto
        valid_extensions = []
        if filters.get('extensions'):
            valid_extensions = [e.strip().lower() if e.strip().startswith('.') else f".{e.strip().lower()}" for e in filters['extensions']]

        for msg_id in reversed(msg_ids):
            status, data = self.server.fetch(msg_id, '(RFC822)')
            if status != 'OK': continue

            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            for part in msg.walk():
                if part.get_content_maintype() == 'multipart': continue
                
                filename = part.get_filename()
                if not filename: 
                    continue

                decoded_header = decode_header(filename)[0]
                decoded_name = decoded_header[0]
                charset = decoded_header[1]
                
                if isinstance(decoded_name, bytes):
                    charset = charset if charset else 'utf-8'
                    try:
                        filename = decoded_name.decode(charset)
                    except (LookupError, UnicodeDecodeError):
                        filename = decoded_name.decode('latin-1', errors='replace')
                else:
                    filename = decoded_name
                    
                filename = filename.replace('\r', '').replace('\n', '')
                ext = os.path.splitext(filename)[1].lower()
                
                # Revisar si coincide con las extensiones deseadas
                if not valid_extensions or ext in valid_extensions:
                    content = part.get_payload(decode=True)
                    attachments.append((filename, content))
                    
        return attachments

    def logout(self):
        if self.server:
            try:
                self.server.close()
            except:
                pass
            self.server.logout()