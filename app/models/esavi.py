import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Date, DateTime, UniqueConstraint, JSON
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base


class ESAVIRecord(Base):
    __tablename__ = "esavi_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    curp = Column(String(20), index=True, nullable=False)
    nombre_completo = Column(String(255), nullable=True)
    edad_anios = Column(Integer, nullable=True)
    edad_meses = Column(Integer, nullable=True)
    edad_dias = Column(Integer, nullable=True)
    sexo = Column(Integer, nullable=True)  # 1: Hombre, 2: Mujer, etc.
    entidad_fed = Column(String(100), nullable=True)
    municipio = Column(String(150), nullable=True)
    jurisdiccion = Column(String(100), nullable=True, index=True)
    sem_epi = Column(Integer, nullable=True, index=True)
    vacuna_1 = Column(String(150), nullable=True)
    dosis_1 = Column(String(50), nullable=True)
    fecha_aplicacion_1 = Column(Date, nullable=True, index=True)
    requirio_hospitalizacion = Column(Integer, nullable=True)  # 1=Si, 2=No
    recuperacion = Column(Integer, nullable=True)  # 1=Si, 2=No
    estado_actual = Column(String(100), nullable=True)
    archivo_fuente = Column(String(255), nullable=True)

    # Almacenamiento híbrido: todos los ~100 campos extraídos en JSONB
    datos_completos = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("curp", "fecha_aplicacion_1", "vacuna_1", name="uq_esavi_curp_fecha_vacuna"),
    )

    def __repr__(self):
        return f"<ESAVIRecord {self.curp} - {self.fecha_aplicacion_1} - {self.vacuna_1}>"
