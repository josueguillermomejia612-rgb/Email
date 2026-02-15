from license_manager import LicenseManager

# Crear instancia del gestor de licencias
lm = LicenseManager()

# Generar licencia (sin días, ahora son permanentes hasta revocar)
nombre = "Insys"
email = "tu_email@ejemplo.com"  # Opcional
notas = "Licencia principal de administrador"  # Opcional

license_key, archivo = lm.generate_license(nombre, email, notas)

print("=" * 60)
print("✓ LICENCIA GENERADA EXITOSAMENTE")
print("=" * 60)
print(f"\n🔑 Clave de Licencia:\n{license_key}\n")
print(f"📁 Archivo guardado en:\n{archivo}\n")
print("=" * 60)
print("\n💡 Copia esta clave y úsala al iniciar la aplicación.")
print("=" * 60)