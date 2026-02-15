import base64
import json
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from config import LICENSE_FOLDER, SECRET_KEY


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_filename(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "sin_nombre"
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", s)
    return s[:60] if len(s) > 60 else s


@dataclass
class LicenseRecord:
    key: str
    name: str
    email: str
    notes: str
    issued_at: str
    revoked: bool = False
    revoked_at: Optional[str] = None
    revoked_reason: str = ""


class MasterPasswordManager:
    """
    Protege la pestaña/acciones de licencias.
    Guarda SOLO hash+salt (no se puede recuperar la contraseña).
    """
    def __init__(self, folder: str):
        self.folder = folder
        os.makedirs(self.folder, exist_ok=True)
        self.path = os.path.join(self.folder, "admin_auth.json")

    def is_set(self) -> bool:
        return os.path.exists(self.path)

    def set_password(self, master_password: str) -> None:
        salt = secrets.token_bytes(16)
        dk = self._derive(master_password, salt)
        payload = {
            "kdf": "pbkdf2_sha256",
            "iterations": 200_000,
            "salt_b64": base64.b64encode(salt).decode("utf-8"),
            "hash_b64": base64.b64encode(dk).decode("utf-8"),
            "created_at": _now_iso(),
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def verify(self, master_password: str) -> bool:
        if not self.is_set():
            return False
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            salt = base64.b64decode(payload["salt_b64"])
            expected = base64.b64decode(payload["hash_b64"])
            dk = self._derive(master_password, salt)
            return secrets.compare_digest(dk, expected)
        except Exception:
            return False

    def _derive(self, master_password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=200_000,
        )
        return kdf.derive(master_password.encode("utf-8"))


class LicenseManager:
    def __init__(self):
        self.folder = LICENSE_FOLDER
        os.makedirs(self.folder, exist_ok=True)

        self.issued_folder = os.path.join(self.folder, "issued")
        os.makedirs(self.issued_folder, exist_ok=True)

        self.history_path = os.path.join(self.folder, "license_history.jsonl")
        self.db_enc_path = os.path.join(self.folder, "licenses_db.json.enc")

        self._fernet = Fernet(SECRET_KEY)

        self.master = MasterPasswordManager(self.folder)

    # ---------- DB ----------
    def _load_db(self) -> dict:
        if not os.path.exists(self.db_enc_path):
            return {"version": 1, "licenses": []}
        with open(self.db_enc_path, "rb") as f:
            enc = f.read()
        raw = self._fernet.decrypt(enc)
        data = json.loads(raw.decode("utf-8"))
        if "licenses" not in data:
            data["licenses"] = []
        return data

    def _save_db(self, db: dict) -> None:
        raw = json.dumps(db, ensure_ascii=False, indent=2).encode("utf-8")
        enc = self._fernet.encrypt(raw)
        with open(self.db_enc_path, "wb") as f:
            f.write(enc)

    def _log(self, action: str, data: dict) -> None:
        entry = {"ts": _now_iso(), "action": action, **data}
        with open(self.history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ---------- Licenses ----------
    def _new_key(self) -> str:
        # formato fácil de dictar / copiar
        token = secrets.token_hex(16).upper()
        return f"DTE-{token[0:8]}-{token[8:16]}-{token[16:24]}-{token[24:32]}"

    def generate_license(self, name: str, email: str = "", notes: str = "") -> Tuple[str, str]:
        db = self._load_db()

        key = self._new_key()
        rec = LicenseRecord(
            key=key,
            name=(name or "").strip(),
            email=(email or "").strip(),
            notes=(notes or "").strip(),
            issued_at=_now_iso(),
            revoked=False,
            revoked_at=None,
            revoked_reason="",
        )

        db["licenses"].append(rec.__dict__)
        self._save_db(db)

        lic_file = self.export_license_file(key)  # crea archivo con nombre/historial
        self._log("GENERATE", {"key": key, "name": rec.name, "email": rec.email, "notes": rec.notes, "file": lic_file})
        return key, lic_file

    def export_license_file(self, key: str) -> str:
        rec = self.get_license(key)
        if not rec:
            raise ValueError("Licencia no encontrada.")

        safe = _safe_filename(rec["name"] or "sin_nombre")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        short = re.sub(r"[^A-F0-9]", "", key.upper())[-6:]
        filename = f"LIC_{safe}_{ts}_{short}.lic.json"
        path = os.path.join(self.issued_folder, filename)

        payload = {
            "license_key": rec["key"],
            "name": rec.get("name", ""),
            "email": rec.get("email", ""),
            "issued_at": rec.get("issued_at", ""),
            "notes": rec.get("notes", ""),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return path

    def get_license(self, key: str) -> Optional[dict]:
        db = self._load_db()
        for r in db.get("licenses", []):
            if (r.get("key") or "").strip() == (key or "").strip():
                return r
        return None

    def list_licenses(self, include_revoked: bool = True) -> List[dict]:
        db = self._load_db()
        lic = db.get("licenses", [])
        if include_revoked:
            return lic
        return [r for r in lic if not r.get("revoked")]

    def revoke_license(self, key: str, reason: str = "") -> bool:
        db = self._load_db()
        changed = False
        for r in db.get("licenses", []):
            if (r.get("key") or "").strip() == (key or "").strip():
                if not r.get("revoked"):
                    r["revoked"] = True
                    r["revoked_at"] = _now_iso()
                    r["revoked_reason"] = (reason or "").strip()
                    changed = True
        if changed:
            self._save_db(db)
            self._log("REVOKE", {"key": key, "reason": reason})
        return changed

    def validate_license(self, key: str) -> Tuple[bool, str]:
        rec = self.get_license(key)
        if not rec:
            return False, "Licencia no existe."
        if rec.get("revoked"):
            return False, f"Licencia revocada. {rec.get('revoked_reason','')}".strip()
        return True, "Licencia válida."