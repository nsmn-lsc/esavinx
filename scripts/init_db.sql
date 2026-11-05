-- ==============================================================================
-- SISTEMA ESAVI V2 - SCRIPT DE INICIALIZACIÓN, PERMISOS Y DDL POSTGRESQL 16
-- ==============================================================================
-- Este script debe ejecutarse conectado como superusuario ('postgres').
-- Corrige permisos del esquema 'public' para PostgreSQL 15/16 y crea la estructura base.

-- 1. CREACIÓN DE BASE DE DATOS Y USUARIO
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'esavi_user') THEN
        CREATE ROLE esavi_user WITH LOGIN ENCRYPTED PASSWORD 'Cambiar_Password_Segura_2026!';
    END IF;
END
$$;

-- Crear base de datos si no existe
SELECT 'CREATE DATABASE esavi_db OWNER esavi_user ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'esavi_db')\gexec

-- Conectarse a la base de datos esavi_db
\connect esavi_db

-- 2. EXTENSIONES NECESARIAS
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- 3. PERMISOS EN POSTGRESQL 15/16 (ESQUEMA PUBLIC)
-- En Postgres 15+, los permisos CREATE en 'public' fueron revocados por defecto.
GRANT CONNECT ON DATABASE esavi_db TO esavi_user;
GRANT USAGE, CREATE ON SCHEMA public TO esavi_user;
ALTER SCHEMA public OWNER TO esavi_user;

-- Permisos por defecto para futuras tablas, secuencias y funciones
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO esavi_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO esavi_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO esavi_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TYPES TO esavi_user;

-- 4. DDL: TABLA DE USUARIOS Y AUTENTICACIÓN
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255),
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- 5. DDL: TABLA PRINCIPAL ESAVI_RECORDS (MODELO HÍBRIDO)
CREATE TABLE IF NOT EXISTS esavi_records (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    curp VARCHAR(20) NOT NULL,
    nombre_completo VARCHAR(255),
    edad_anios INTEGER,
    edad_meses INTEGER,
    edad_dias INTEGER,
    sexo INTEGER, -- 1: Hombre, 2: Mujer
    entidad_fed VARCHAR(100),
    municipio VARCHAR(150),
    jurisdiccion VARCHAR(100),
    sem_epi INTEGER,
    vacuna_1 VARCHAR(150),
    dosis_1 VARCHAR(50),
    fecha_aplicacion_1 DATE,
    requirio_hospitalizacion INTEGER, -- 1: Sí, 2: No
    recuperacion INTEGER, -- 1: Sí, 2: No
    estado_actual VARCHAR(100),
    archivo_fuente VARCHAR(255),
    
    -- Columna semiestructurada para los ~100 campos clínicos
    datos_completos JSONB,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Restricción de unicidad compuesta contra duplicados
    CONSTRAINT uq_esavi_curp_fecha_vacuna UNIQUE (curp, fecha_aplicacion_1, vacuna_1)
);

-- 6. ÍNDICES DE ALTO RENDIMIENTO
-- Índices B-Tree para filtros analíticos y búsquedas frecuentes
CREATE INDEX IF NOT EXISTS idx_esavi_curp ON esavi_records(curp);
CREATE INDEX IF NOT EXISTS idx_esavi_sem_epi ON esavi_records(sem_epi);
CREATE INDEX IF NOT EXISTS idx_esavi_fecha_apl ON esavi_records(fecha_aplicacion_1);
CREATE INDEX IF NOT EXISTS idx_esavi_vacuna_1 ON esavi_records(vacuna_1);
CREATE INDEX IF NOT EXISTS idx_esavi_jurisdiccion ON esavi_records(jurisdiccion);
CREATE INDEX IF NOT EXISTS idx_esavi_municipio ON esavi_records(municipio);
CREATE INDEX IF NOT EXISTS idx_esavi_created_at ON esavi_records(created_at DESC);

-- Índice GIN optimizado (jsonb_path_ops) para consultas aceleradas sobre el payload clínico
CREATE INDEX IF NOT EXISTS idx_esavi_datos_completos_gin ON esavi_records USING GIN (datos_completos jsonb_path_ops);

-- Otorgar permisos finales a todas las tablas del esquema al usuario
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO esavi_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO esavi_user;
