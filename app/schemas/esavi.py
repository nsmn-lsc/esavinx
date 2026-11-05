from typing import Optional, Dict, Any, List
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict


class ESAVIRecordBase(BaseModel):
    curp: str
    nombre_completo: Optional[str] = None
    edad_anios: Optional[int] = None
    edad_meses: Optional[int] = None
    edad_dias: Optional[int] = None
    sexo: Optional[int] = None
    entidad_fed: Optional[str] = None
    municipio: Optional[str] = None
    jurisdiccion: Optional[str] = None
    sem_epi: Optional[int] = None
    vacuna_1: Optional[str] = None
    dosis_1: Optional[str] = None
    fecha_aplicacion_1: Optional[date] = None
    estado_actual: Optional[str] = None
    archivo_fuente: Optional[str] = None


class ESAVIRecordResponse(ESAVIRecordBase):
    id: str
    datos_completos: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UploadFileResult(BaseModel):
    filename: str
    status: str  # "success", "skipped_duplicate", "updated_duplicate", "error"
    message: str
    curp: Optional[str] = None
    vacuna: Optional[str] = None
    fecha_aplicacion: Optional[str] = None


class BatchUploadSummary(BaseModel):
    total_files: int
    success_count: int
    skipped_count: int
    updated_count: int
    error_count: int
    results: List[UploadFileResult]


class KPIsSummary(BaseModel):
    total_records: int
    total_mujeres: int
    total_hombres: int
    total_graves: int
    total_recuperados: int
    total_defunciones: int
    top_vacunas: List[Dict[str, Any]]
    distribucion_semanal: List[Dict[str, Any]]
    distribucion_edad: List[Dict[str, Any]]
