# Sistema ESAVI v2.0

Plataforma integral de **Vigilancia Epidemiológica de Eventos Supuestamente Atribuibles a la Vacunación o Inmunización (ESAVI)**.

Permite la ingesta por lotes de formatos clínicos oficiales en formato Excel (`.xlsx`/`.xlsm`), persistencia en modelo híbrido relacional + `JSONB`, analítica interactiva mediante Chart.js, autenticación segura con bcrypt/JWT y exportación del concentrado acumulativo con orden de columnas configurable en Excel vía XlsxWriter.

---

## 🚀 Arquitectura y Stack

- **Backend**: FastAPI 0.115, Uvicorn, SQLAlchemy 2.0, Pydantic v2.
- **Frontend**: Jinja2 + Tailwind CSS (CDN) + HTMX 2.0 + Dropzone/AJAX + Chart.js (Cero dependencias de Node.js).
- **Seguridad**: Autenticación con Bcrypt (hash rounds=12), Tokens JWT, Cookies `HttpOnly` y `SameSite=Lax`.
- **Motor de Extracción**: OpenPyXL + Pandas con validación posicional de CURP `(0, 4)` y concatenación de nombre.
- **Motor de Exportación**: XlsxWriter con ordenamiento por `config/concentrado_columns.json`.
- **Despliegue**: Docker y Docker Compose para Hetzner Cloud (3 Nodos: Caddy -> FastAPI -> PostgreSQL 16).

---

## 📂 Estructura del Proyecto

```text
esavi_dos/
├── app/
│   ├── api/
│   │   ├── routes_auth.py       # Autenticación, login/logout, tokens
│   │   ├── routes_upload.py     # Endpoint POST /api/upload (batch 1 a N)
│   │   ├── routes_analytics.py  # Endpoint GET /api/analytics/metrics
│   │   └── routes_export.py     # Concentrado GET /api/export/excel y /records
│   ├── core/
│   │   ├── config.py            # Pydantic BaseSettings (.env)
│   │   ├── database.py          # SQLAlchemy Session & Engine
│   │   └── security.py          # Bcrypt hashing, JWT, cookies y dependencias
│   ├── extractor/
│   │   ├── coordenadas.py       # Diccionario de ~100 celdas clínicas
│   │   └── engine.py            # Clase ESAVIExtractor con sanitización de tipos
│   ├── models/
│   │   ├── user.py              # Modelo de Usuario
│   │   └── esavi.py             # Modelo ESAVIRecord (Indexado + JSONB)
│   ├── schemas/
│   │   ├── auth.py              # Schemas Pydantic para Auth/Users
│   │   └── esavi.py             # Schemas Pydantic para ESAVI y Lotes
│   ├── services/
│   │   ├── auth_service.py      # Autenticación y creación de admin inicial
│   │   ├── ingestion_service.py # Ingesta batch y resolución de duplicados
│   │   ├── analytics_service.py # KPIs y agregaciones para Chart.js
│   │   └── export_service.py    # Generador de Excel con XlsxWriter
│   ├── templates/
│   │   ├── base.html            # Layout maestro con Navbar y Lucide icons
│   │   ├── login.html           # Vista de inicio de sesión segura
│   │   ├── dashboard.html       # Dashboard con 4 gráficos interactivos
│   │   ├── upload.html          # Drag and Drop para carga múltiple
│   │   ├── records.html         # Concentrado con filtros y modal JSONB
│   │   └── partials/
│   │       └── records_table.html # Partial HTMX para filtrado reactivo
│   ├── static/
│   │   ├── js/
│   │   │   ├── dashboard.js     # Carga de métricas y render Chart.js
│   │   │   └── uploader.js      # Manejador de subidas y barra de estado
│   └── main.py                  # Entrypoint FastAPI con lifespan y vistas web
├── config/
│   └── concentrado_columns.json # Definición del orden de columnas de exportación
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 🔐 Credenciales Iniciales por Defecto

Al arrancar por primera vez, el sistema crea automáticamente el usuario administrador inicial si no existe:

- **Usuario**: `admin@esavi.salud.gob.mx`
- **Contraseña**: `AdminEsavi2026!`

*(Puedes cambiar estos valores en tu archivo `.env` mediante `FIRST_SUPERUSER_EMAIL` y `FIRST_SUPERUSER_PASSWORD`)*.

---

## 💻 Instalación y Ejecución Local

### 1. Entorno Virtual e Instalación de Dependencias

```bash
# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configuración de Variables de Entorno

```bash
cp .env.example .env
```

### 3. Ejecutar la Aplicación

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Accede desde tu navegador:
- **Aplicación Web**: [http://localhost:8000](http://localhost:8000)
- **Documentación Interactiva (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🐳 Despliegue con Docker Compose (Hetzner Cloud)

```bash
docker compose up -d --build
```

---

## 📋 Reglas de Ingesta y Extracción

1. **Validación de Anclaje**: Todo archivo debe tener una CURP válida en la celda `(0, 4)` de la hoja `"Registro"` (después de saltar 7 filas).
2. **Control de Duplicados**:
   - Clave única: `(CURP, Fecha de Aplicación, Vacuna)`.
   - Modos disponibles en la interfaz:
     - **Ignorar duplicados** (`skip`): No altera los registros previos.
     - **Actualizar / Sobrescribir** (`update`): Reemplaza los datos con la información del archivo más reciente.
