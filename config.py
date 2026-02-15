import os

# Configuración de Servidores de Correo
EMAIL_CONFIG = {
    'gmail': {
        'imap_server': 'imap.gmail.com',
        'smtp_server': 'smtp.gmail.com'
    },
    'outlook': {
        'imap_server': 'outlook.office365.com',
        'smtp_server': 'smtp.office365.com'
    }
}

APP_DATA_FOLDER = os.path.join(os.path.expanduser("~"), ".dte_json_app")
SETTINGS_FILE = os.path.join(APP_DATA_FOLDER, "settings.json")
# Configuración de Seguridad (Licencias)
SECRET_KEY = b'xK8vN2pQ5wR9tY6uI3oP0aS4dF7gH1jK2lZ5xC8vB6n='
# Esta es la variable que faltaba:
LICENSE_FOLDER = os.path.join(os.path.expanduser("~"), ".dte_app_licenses")

# Configuración de la Aplicación nxow wajm gocy jejl pzE.dXmgQ8?V5CV
APP_NAME = "DTE Email Processor"
VERSION = "1.0.0"