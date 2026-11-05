FROM python:3.11-slim

# Evitar escritura de archivos .pyc y buffer de stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias del sistema y utilidades de red
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY . .

# Exponer el puerto del contenedor
EXPOSE 8000

# Comando de ejecución con Uvicorn:
# - workers: 2 para concurrencia eficiente
# - proxy-headers: reconoce cabeceras X-Forwarded-* de Caddy
# - forwarded-allow-ips: confía en el gateway Caddy y la red privada de Hetzner
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "10.0.0.0/16,127.0.0.1,10.0.0.1"]
