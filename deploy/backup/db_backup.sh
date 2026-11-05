#!/usr/bin/env bash
# ==============================================================================
# SISTEMA ESAVI V2 - SCRIPT DE RESPALDO AUTOMATIZADO POSTGRESQL 16 (NODO 3)
# ==============================================================================
# Uso: Ejecutado periódicamente por esavi-backup.timer vía Systemd.

set -euo pipefail

# 1. CONFIGURACIÓN DE RESPALDO
DB_NAME="${DB_NAME:-esavi_db}"
DB_USER="${DB_USER:-esavi_user}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/esavi}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP="$(date +'%Y%m%d_%H%M%S')"
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_backup_${TIMESTAMP}.sql.gz"
LOG_FILE="${BACKUP_DIR}/backup.log"

# Asegurar que el directorio de respaldos exista y tenga permisos restringidos
mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}"

log_msg() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

log_msg "Iniciando respaldo de base de datos '${DB_NAME}'..."

# 2. EJECUCIÓN DEL RESPALDO CON PG_DUMP Y COMPRESIÓN GZIP
# Se utiliza pg_dump exportando el esquema completo y datos
if pg_dump -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" --clean --if-exists --no-owner --no-privileges | gzip -9 > "${BACKUP_FILE}"; then
    BACKUP_SIZE="$(du -h "${BACKUP_FILE}" | cut -f1)"
    log_msg "✅ Respaldo completado exitosamente: ${BACKUP_FILE} (Tamaño: ${BACKUP_SIZE})"
else
    log_msg "❌ ERROR: Falló la generación del respaldo de ${DB_NAME}."
    exit 1
fi

# 3. VERIFICACIÓN DE INTEGRIDAD BÁSICA (El archivo no debe estar vacío)
if [ ! -s "${BACKUP_FILE}" ]; then
    log_msg "❌ ERROR: El archivo de respaldo generado está vacío."
    rm -f "${BACKUP_FILE}"
    exit 1
fi

# 4. ROTACIÓN Y PURGA DE RESPALDOS ANTIGUOS (> RETENTION_DAYS DÍAS)
log_msg "Purgando respaldos con antigüedad mayor a ${RETENTION_DAYS} días..."
DELETED_COUNT=$(find "${BACKUP_DIR}" -name "${DB_NAME}_backup_*.sql.gz" -type f -mtime +"${RETENTION_DAYS}" -print -delete | wc -l)
log_msg "🧹 Se eliminaron ${DELETED_COUNT} archivos de respaldo antiguos."

log_msg "Proceso de respaldo finalizado satisfactoriamente."
