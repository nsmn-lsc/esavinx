# SYSTEM ARCHITECTURE CONTEXT & RUNBOOK (HETZNER 3-NODE CLUSTER)

> **Rol del Documento:** Archivo de contexto operativo e instrucciones de arquitectura para agentes de programación y automatización asistida por IA (Cursor, Aider, Claude Code, Copilot, etc.).
> **Instrucción Mandataria:** Cada vez que propongas un script, archivo de Docker Compose, servicio de systemd, regla de red o variable de entorno, **debes respetar estrictamente la distribución física y lógica descrita en este documento**.

---

## 1. Topología del Cluster Hetzner

El entorno se compone de 3 instancias en Hetzner Cloud interconectadas mediante una red privada vSwitch / Cloud Network (`10.0.0.0/24` en interfaz `enp7s0`).

| Hostname | Rol | IP Privada (LAN) | IP Pública (eth0) | Estrategia de Firewall |
| :--- | :--- | :--- | :--- | :--- |
| **`app-node`** | Compute: Django, FastAPI, Next.js, n8n | `10.0.0.2` | `91.98.117.255` | Hetzner FW + UFW local |
| **`db-node`** | Bases de Datos: PostgreSQL 16 & MySQL 8 | `10.0.0.3` | `116.203.20.174` | Hetzner Cloud FW (Perimetral) |
| **`file-node`** | Ingress Gateway, Caddy TLS, Next.js, Storage | `10.0.0.4` | `46.224.194.173` | Hetzner Cloud FW (Puertos 80/443) |

---

## 2. Mapa Actual de Puertos y Servicios Activos

### A. Servicios en Producción (`app-node` - `10.0.0.2`)
* `8000/tcp` -> **`healtics.service`** (Django / Gunicorn) -> LAN `10.0.0.0/24`
* `8100/tcp` -> **`healtics-staging.service`** (Django / Gunicorn) -> Proxy: `staging-healtics.filenode.dev`
* `8010/tcp` -> **`sigevz.service`** (Django / Gunicorn) -> Proxy: `sigevz.filenode.dev`
* `8014/tcp` -> **`ataraxia.service`** (Django / Gunicorn) -> Proxy: `ataraxia.filenode.dev`
* `8020/tcp` -> **`ventas.service`** (Django / Gunicorn) -> Proxy: `http://46.224.194.173`
* `8006/tcp` -> **`esavi-xl.service`** (FastAPI / Uvicorn) -> Proxy: `esavi.filenode.dev`
* `5678/tcp` -> **`n8n_nexus`** (Podman / Node.js) -> Proxy: `ops.filenode.dev`
* `3000/tcp` -> **`pm2-root`** (Next.js MARO Hub) -> Proxy: `maro-hub.filenode.dev`
* `4173/tcp` -> **`caddy` local** (mapa_inf estático) -> Proxy: `mapainf.filenode.dev`
* `4175/tcp` -> **`caddy` local** (mapa_riesgos estático) -> Proxy: `mapariesgos.filenode.dev`
* `4176/tcp` -> **`caddy` local** (SIMESA estático) -> Consumo LAN privada

### B. Servicios en Desarrollo / Evaluación (`app-node`)
* `8005/tcp` -> **`argusops.service`** (FastAPI / WebSockets) -> Proxy: `argos.filenode.dev` *(En desarrollo / pendiente de terminar)*.
* `8080/tcp` -> **`nexus-core.service`** (FastAPI / Uvicorn) -> Webhook interno `10.0.0.0/24`.

### C. Servicios Desactivados / Retirados (¡NO UTILIZAR NI REUTILIZAR PUERTOS SIN AUTORIZACIÓN!)
* `8002/tcp` -> `nexus.service` (**DESACTIVADO**). Subdominios `app-nexus` y `nexus.filenode.dev` retirados.
* `8004/tcp` -> `mapas-zoonosis.service` (**DESACTIVADO**). Subdominio `mapas-zoonosis.filenode.dev` retirado.
* `8085/tcp` -> `fixops.service` (**DESACTIVADO**).

---

## 3. Servicios en `db-node` (`10.0.0.3`) y `file-node` (`10.0.0.4`)

### `db-node` (`10.0.0.3`)
* **PostgreSQL 16:** Puerto `5432` escuchando para aplicaciones de `10.0.0.2`.
* **MySQL 8:** Puerto `3306` (X-Plugin en `33060`) para aplicaciones de `10.0.0.2`.
* **Seguridad:** Aislado perimetralmente con Hetzner Firewall. Las apps en `10.0.0.2` se conectan por la IP privada `10.0.0.3`.

### `file-node` (`10.0.0.4`)
* **Caddy Server:** Ingress público en puertos `80` (HTTP) y `443` (HTTPS / HTTP3 QUIC).
* **Next.js Local:** Puerto `3000` gestionado internamente en este nodo.
* **Docker Proxy:** Puerto `3001` activo para contenedor local.
* **MariaDB Local:** Puerto `127.0.0.1:3306` (aislado solo para el host).

---

## 4. Reglas de Implementación Obligatorias para Agentes IA

1. **Direccionamiento de Bases de Datos:**
   ```env
   # PostgreSQL en db-node
   DATABASE_URL=postgresql://[usuario]:[password]@10.0.0.3:5432/[nombre_db]

   # MySQL en db-node
   MYSQL_URL=mysql://[usuario]:[password]@tcp(10.0.0.3:3306)/[nombre_db]
   ```
   *Bajo ninguna circunstancia intentes instalar motores de base de datos relacionales en `app-node`.*

2. **Binding de Servicios Nuevos:**
   * Al crear un nuevo servicio en `app-node`, haz el bind a `10.0.0.2:<puerto>` o `127.0.0.1:<puerto>`.
   * **NUNCA** hagas bind a `0.0.0.0` público a menos que sea un requerimiento explícito.

3. **Exposición Vía Reverse Proxy (Caddy en `file-node`):**
   * Cualquier aplicación web que deba salir a internet debe configurarse en `/etc/caddy/Caddyfile` de `file-node` con el formato:
   ```caddy
   subdominio.filenode.dev {
       reverse_proxy 10.0.0.2:<puerto> {
           header_up Host {host}
           header_up X-Real-IP {remote_host}
           header_up X-Forwarded-For {remote_host}
           header_up X-Forwarded-Proto {scheme}
       }
   }
   ```