import json
import os
from typing import Optional

try:
    import keyring  # seguro (recomendado)
except Exception:
    keyring = None

from cryptography.fernet import Fernet, InvalidToken

from config import APP_DATA_FOLDER, SETTINGS_FILE, SECRET_KEY

_SERVICE_NAME = "dte_json_app"


class SettingsManager:
    """
    settings.json guarda cosas no críticas (provider, email, filtros, llave).
    Password:
      - Preferible: keyring
      - Fallback: cifrado con Fernet (SECRET_KEY) dentro de settings.json
    """

    def __init__(self):
        os.makedirs(APP_DATA_FOLDER, exist_ok=True)
        self._fernet = Fernet(SECRET_KEY)

    def load(self) -> dict:
        if not os.path.exists(SETTINGS_FILE):
            return self._defaults()
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            d = self._defaults()
            d.update(data if isinstance(data, dict) else {})
            return d
        except Exception:
            return self._defaults()

    def save(self, settings: dict) -> None:
        os.makedirs(APP_DATA_FOLDER, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

    def _defaults(self) -> dict:
        return {
            "provider": "gmail",
            "email": "",
            "remember_email": True,
            "remember_password": True,
            "remember_license": True,
            "license_key": "",
            "filters": {
                "from_email": "",
                "subject": "",
                "date_from": "",
                "date_to": "",
                "file_exts": [".json"],
            },
            # fallback cifrado si keyring no existe
            "password_enc": "",
        }

    def set_password(self, email: str, password: str) -> None:
        if not email:
            return

        if keyring is not None:
            keyring.set_password(_SERVICE_NAME, email, password)
            return

        # Fallback cifrado en settings.json
        s = self.load()
        token = self._fernet.encrypt(password.encode("utf-8")).decode("utf-8")
        s["password_enc"] = token
        self.save(s)

    def get_password(self, email: str) -> Optional[str]:
        if not email:
            return None

        if keyring is not None:
            try:
                return keyring.get_password(_SERVICE_NAME, email)
            except Exception:
                return None

        s = self.load()
        token = (s.get("password_enc") or "").strip()
        if not token:
            return None
        try:
            return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            return None
        except Exception:
            return None

    def clear_password(self, email: str) -> None:
        if not email:
            return

        if keyring is not None:
            try:
                keyring.delete_password(_SERVICE_NAME, email)
            except Exception:
                pass
            return

        s = self.load()
        s["password_enc"] = ""
        self.save(s)