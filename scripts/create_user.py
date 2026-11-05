#!/usr/bin/env python3
"""
Script CLI para administración y creación de usuarios en Sistema ESAVI v2.
Compatible tanto con entornos locales (.env / SQLite) como producción (.env.production / PostgreSQL).
"""

import sys
import os
import argparse
import getpass

# Agregar el directorio raíz al path para importar módulos de la app
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app.core.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash


def create_user(username: str, password: str, full_name: str = None, email: str = None, is_superuser: bool = False):
    username = username.strip()
    if not username:
        print("❌ Error: El nombre de usuario no puede estar vacío.")
        sys.exit(1)

    if len(password) < 8:
        print("❌ Error: La contraseña debe tener al menos 8 caracteres.")
        sys.exit(1)

    db = SessionLocal()
    try:
        # Verificar si el usuario ya existe
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"⚠️  El usuario '{username}' ya existe en la base de datos.")
            actualizar = input("¿Deseas actualizar su contraseña y datos? [s/N]: ").strip().lower()
            if actualizar in ("s", "si", "y", "yes"):
                existing.hashed_password = get_password_hash(password)
                if full_name:
                    existing.full_name = full_name
                if email:
                    existing.email = email
                existing.is_superuser = is_superuser
                existing.is_active = True
                db.commit()
                print(f"✅ Usuario '{username}' actualizado correctamente.")
            else:
                print("Operación cancelada.")
            return

        # Crear nuevo usuario
        hashed_pwd = get_password_hash(password)
        new_user = User(
            username=username,
            hashed_password=hashed_pwd,
            full_name=full_name,
            email=email,
            is_active=True,
            is_superuser=is_superuser,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        rol = "Superusuario (Admin)" if is_superuser else "Usuario Estándar"
        print("\n" + "=" * 50)
        print("✅ USUARIO CREADO EXITOSAMENTE")
        print("=" * 50)
        print(f"  ID:          {new_user.id}")
        print(f"  Usuario:     {new_user.username}")
        print(f"  Nombre:      {new_user.full_name or 'N/A'}")
        print(f"  Email:       {new_user.email or 'N/A'}")
        print(f"  Rol:         {rol}")
        print(f"  Estado:      {'Activo' if new_user.is_active else 'Inactivo'}")
        print("=" * 50 + "\n")

    except Exception as e:
        db.rollback()
        print(f"❌ Error al crear usuario en la base de datos: {e}")
        sys.exit(1)
    finally:
        db.close()


def list_users():
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.created_at.desc()).all()
        if not users:
            print("ℹ️  No hay usuarios registrados en el sistema.")
            return

        print("\n" + "=" * 70)
        print(f"{'USUARIO':<20} | {'NOMBRE':<25} | {'ROL':<10} | {'ESTADO':<8}")
        print("-" * 70)
        for u in users:
            rol = "Superuser" if u.is_superuser else "User"
            estado = "Activo" if u.is_active else "Inactivo"
            nombre = (u.full_name or "-")[:24]
            print(f"{u.username:<20} | {nombre:<25} | {rol:<10} | {estado:<8}")
        print("=" * 70 + "\n")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Gestión y creación de usuarios para Sistema ESAVI v2"
    )
    parser.add_argument("-u", "--username", help="Nombre de usuario único para login")
    parser.add_argument("-p", "--password", help="Contraseña (si se omite, se solicitará de forma oculta)")
    parser.add_argument("-n", "--name", help="Nombre completo de la persona", default=None)
    parser.add_argument("-e", "--email", help="Correo electrónico institucional", default=None)
    parser.add_argument("--admin", action="store_true", help="Otorga privilegios de superusuario")
    parser.add_argument("-l", "--list", action="store_true", help="Lista todos los usuarios registrados")

    args = parser.parse_args()

    if args.list:
        list_users()
        return

    # Si se pasan parámetros directos por argumentos
    if args.username:
        username = args.username
        password = args.password
        if not password:
            password = getpass.getpass(f"Ingrese la contraseña para '{username}': ")
            password_confirm = getpass.getpass("Confirme la contraseña: ")
            if password != password_confirm:
                print("❌ Las contraseñas no coinciden.")
                sys.exit(1)
        create_user(
            username=username,
            password=password,
            full_name=args.name,
            email=args.email,
            is_superuser=args.admin
        )
        return

    # Modo interactivo por consola
    print("\n--- CREACIÓN INTERACTIVA DE USUARIO (ESAVI v2) ---")
    try:
        username = input("Nombre de usuario (ej. jgarcia): ").strip()
        if not username:
            print("El usuario es obligatorio.")
            sys.exit(1)

        full_name = input("Nombre completo (opcional): ").strip() or None
        email = input("Correo electrónico (opcional): ").strip() or None

        password = getpass.getpass("Contraseña (mínimo 8 caracteres): ")
        password_confirm = getpass.getpass("Confirme la contraseña: ")

        if password != password_confirm:
            print("❌ Las contraseñas no coinciden.")
            sys.exit(1)

        is_admin_input = input("¿Es superusuario administrador? [s/N]: ").strip().lower()
        is_superuser = is_admin_input in ("s", "si", "y", "yes")

        create_user(
            username=username,
            password=password,
            full_name=full_name,
            email=email,
            is_superuser=is_superuser
        )

    except KeyboardInterrupt:
        print("\nOperación cancelada por el usuario.")
        sys.exit(0)


if __name__ == "__main__":
    main()
