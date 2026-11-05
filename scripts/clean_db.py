#!/usr/bin/env bash
"""true" '''\'
exec "$(dirname "$0")/../.venv/bin/python" "$0" "$@"
'''
"""
# ==============================================================================
# SCRIPT PARA LIMPIEZA / RESET DE BASE DE DATOS - SISTEMA ESAVI V2
# ==============================================================================
# Compatible con SQLite y PostgreSQL.
# Por defecto elimina todos los registros clínicos (esavi_records) manteniendo
# la tabla de usuarios y el administrador para poder iniciar sesión de inmediato.
#
# Uso:
#   python scripts/clean_db.py             # Limpia registros y conserva admin
#   python scripts/clean_db.py --all       # Limpieza total y reinicializa admin
#   python scripts/clean_db.py --force     # Sin confirmación interactiva
# ==============================================================================

import os
import sys
import argparse

# Asegurar path al proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import engine, SessionLocal, Base
from app.models.esavi import ESAVIRecord
from app.models.user import User
from app.services.auth_service import AuthService
from app.core.config import settings


def clean_database(records_only: bool = True, force: bool = False):
    print("=" * 70)
    print("🧹 LIMPIEZA DE BASE DE DATOS - SISTEMA ESAVI V2")
    print("=" * 70)
    print(f"Target DB URL: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")

    db = SessionLocal()
    try:
        # Migración segura si la tabla users fue creada antes de agregar username
        try:
            db.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(100)"))
            db.commit()
        except Exception:
            db.rollback()

        total_records = db.query(ESAVIRecord).count()
        total_users = db.query(User).count()
        print(f"Estado actual en base de datos:")
        print(f"  - Registros clínicos (esavi_records): {total_records}")
        print(f"  - Usuarios registrados (users):       {total_users}")

        if not force:
            modo = "TODOS los registros clínicos (conservando usuarios)" if records_only else "TODAS las tablas y registros"
            confirmacion = input(f"\n⚠️  ¿Seguro que deseas eliminar {modo}? (s/N): ").strip().lower()
            if confirmacion not in ["s", "si", "y", "yes"]:
                print("Operación cancelada por el usuario.")
                return

        print("\nEjecutando limpieza...")

        if records_only:
            # Eliminar registros clínicos únicamente
            deleted = db.query(ESAVIRecord).delete()
            db.commit()
            print(f"✅ Se eliminaron {deleted} registros clínicos de 'esavi_records'.")
        else:
            # Limpieza total
            db.query(ESAVIRecord).delete()
            db.query(User).delete()
            db.commit()
            print("✅ Se eliminaron todos los registros de 'esavi_records' y 'users'.")

        # Asegurar que las tablas existan y el usuario admin esté inicializado
        Base.metadata.create_all(bind=engine)
        admin = AuthService.init_first_superuser(db)
        print(f"👤 Superusuario administrador verificado/creado:")
        print(f"  - Usuario: {admin.username}")
        print(f"  - Contraseña por defecto: {settings.FIRST_SUPERUSER_PASSWORD}")

        print("=" * 70)
        print("✨ ¡Base de datos limpia y lista para demostración en blanco!")
        print("=" * 70)

    except Exception as e:
        db.rollback()
        print(f"❌ Error durante la limpieza: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Limpieza de base de datos ESAVI v2.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Elimina también los usuarios antes de recrear el admin inicial."
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Ejecuta la limpieza sin solicitar confirmación interactiva."
    )

    args = parser.parse_args()
    clean_database(records_only=not args.all, force=args.force)
