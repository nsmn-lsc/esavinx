# GUÍA PASO A PASO: DESPLIEGUE EN PRODUCCIÓN (HETZNER 3-NODE CLUSTER)

Este procedimiento describe el reemplazo de `esavi-xl.service` por **Sistema ESAVI v2** en la infraestructura Hetzner.

---

## 1. NODO 3: `db-node` (`10.0.0.3`) — Base de Datos y Backups

Conéctate vía SSH a `db-node`:

### A. Inicializar Base de Datos PostgreSQL 16
1. Conéctate a PostgreSQL como superusuario:
   ```bash
   sudo -u postgres psql
   ```
2. Ejecuta el script de inicialización [`scripts/init_db.sql`](file:///home/najera/dev/projects/esavi_dos/scripts/init_db.sql):
   - Cambia la contraseña por una segura:
   ```sql
   CREATE DATABASE esavi_db;
   CREATE USER esavi_user WITH ENCRYPTED PASSWORD 'TU_PASSWORD_SEGURA_DB_2026!';
   GRANT ALL PRIVILEGES ON DATABASE esavi_db TO esavi_user;
   \c esavi_db
   GRANT ALL ON SCHEMA public TO esavi_user;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO esavi_user;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO esavi_user;
   CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
   CREATE EXTENSION IF NOT EXISTS "pgcrypto";
   ```
3. Verifica que PostgreSQL escuche en la interfaz privada `10.0.0.3` (`/etc/postgresql/16/main/postgresql.conf`) y permita conexiones desde `10.0.0.2` en `/etc/postgresql/16/main/pg_hba.conf`:
   ```text
   host    esavi_db        esavi_user      10.0.0.2/32             scram-sha-256
   ```
   Recarga si modificaste: `sudo systemctl reload postgresql`.

### B. Configurar Backup Automatizado Diario (03:00 AM)
1. Copia el script [`deploy/backup/db_backup.sh`](file:///home/najera/dev/projects/esavi_dos/deploy/backup/db_backup.sh) a `/usr/local/bin/db_backup.sh`:
   ```bash
   sudo cp deploy/backup/db_backup.sh /usr/local/bin/db_backup.sh
   sudo chmod +x /usr/local/bin/db_backup.sh
   ```
2. Copia los archivos de Systemd:
   ```bash
   sudo cp deploy/backup/esavi-backup.service /etc/systemd/system/
   sudo cp deploy/backup/esavi-backup.timer /etc/systemd/system/
   ```
3. Ajusta la contraseña en `/etc/systemd/system/esavi-backup.service` en la variable `PGPASSWORD`.
4. Habilita y arranca el timer:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now esavi-backup.timer
   sudo systemctl list-timers --all | grep esavi
   ```

---

## 2. NODO 2: `app-node` (`10.0.0.2`) — Aplicación FastAPI y Systemd

Conéctate vía SSH a `app-node`:

### A. Preparación del Código y Entorno
1. Detén el servicio anterior para liberar el puerto 8006:
   ```bash
   sudo systemctl stop esavi-xl.service
   ```
2. Clona o actualiza el repositorio en `/home/najera/dev/projects/esavi_dos` (o la ruta de despliegue definida):
   ```bash
   cd /home/najera/dev/projects/esavi_dos
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. Crea el archivo de variables de entorno de producción `.env.production` (basado en `.env.production.example`):
   ```bash
   cp .env.production.example .env.production
   nano .env.production
   ```
   - Configura la contraseña real de PostgreSQL (`10.0.0.3:5432`).
   - Genera un `SECRET_KEY` seguro: `openssl rand -hex 32`.
   - Establece `COOKIE_SECURE=True`.

### B. Configurar e Iniciar el Servicio Systemd
1. Instala el archivo de servicio [`deploy/systemd/esavi-xl.service`](file:///home/najera/dev/projects/esavi_dos/deploy/systemd/esavi-xl.service):
   ```bash
   sudo cp deploy/systemd/esavi-xl.service /etc/systemd/system/esavi-xl.service
   sudo systemctl daemon-reload
   ```
2. Habilita y arranca el servicio:
   ```bash
   sudo systemctl enable esavi-xl.service
   sudo systemctl start esavi-xl.service
   ```
3. Verifica el estado y los logs:
   ```bash
   sudo systemctl status esavi-xl.service
   journalctl -u esavi-xl.service -f -n 50
   ```
4. Prueba que el puerto responda localmente en la red interna:
   ```bash
   curl -I http://10.0.0.2:8006/login
   ```

---

## 3. NODO 1: `file-node` (`10.0.0.4`) — Ingress Gateway Caddy

Conéctate vía SSH a `file-node`:

1. Edita el Caddyfile maestro:
   ```bash
   sudo nano /etc/caddy/Caddyfile
   ```
2. Asegúrate de que el bloque `esavi.filenode.dev` apunte a `10.0.0.2:8006` con la configuración de [`deploy/caddy/Caddyfile`](file:///home/najera/dev/projects/esavi_dos/deploy/caddy/Caddyfile):
   ```caddy
   esavi.filenode.dev {
       request_body {
           max_size 50MB
       }
       encode gzip zstd

       header {
           Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
           X-Content-Type-Options "nosniff"
           X-Frame-Options "DENY"
           Referrer-Policy "strict-origin-when-cross-origin"
           -Server
       }

       reverse_proxy 10.0.0.2:8006 {
           header_up Host {host}
           header_up X-Real-IP {remote_host}
           header_up X-Forwarded-For {remote_host}
           header_up X-Forwarded-Proto {scheme}
           transport http {
               read_timeout 120s
               write_timeout 120s
           }
       }

       log {
           output file /var/log/caddy/esavi_access.log {
               roll_size 10MB
               roll_keep 10
           }
       }
   }
   ```
3. Valida la sintaxis y recarga Caddy sin caída de servicio:
   ```bash
   sudo caddy validate --config /etc/caddy/Caddyfile
   sudo caddy reload --config /etc/caddy/Caddyfile
   ```

---

## 4. Verificación Final en Producción

Desde un navegador o terminal externa:
1. Accede a **`https://esavi.filenode.dev/login`**
2. Verifica que el certificado TLS (Let's Encrypt / ZeroSSL) esté activo y válido.
3. Inicia sesión con el usuario administrador configurado en `.env.production`.
4. Realiza una prueba de carga de archivo batch Excel para verificar que el límite de 50MB y los timeouts de 120s operen correctamente sin interrupciones.
