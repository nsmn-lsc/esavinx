from datetime import datetime, date
from io import BytesIO
from typing import Dict, Tuple, Union, Optional, Any
import math
import openpyxl
import pandas as pd
import numpy as np

from app.extractor.coordenadas import COORDENADAS_ESAVI, PARTES_NOMBRE


def sanitizar_valor(val: Any) -> Any:
    """Convierte tipos de pandas/numpy a tipos nativos de Python serializables a JSON."""
    if val is None:
        return None
    if isinstance(val, (float, np.floating)):
        if math.isnan(val) or math.isinf(val):
            return None
        # Si es un número entero exacto con representación float (ej: 5.0), lo dejamos como float o int según contexto
        if val.is_integer():
            return int(val)
        return float(val)
    if isinstance(val, (int, np.integer)):
        return int(val)
    if isinstance(val, (pd.Timestamp, datetime)):
        if pd.isna(val):
            return None
        return val.strftime("%Y-%m-%d")
    if isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    if pd.isna(val):
        return None
    
    val_str = str(val).strip()
    if val_str == "" or val_str.lower() == "nan" or val_str.lower() == "nat":
        return None
    return val_str


def parse_date_safe(val: Any) -> Optional[date]:
    """Parsea de forma segura una fecha desde string, Timestamp, datetime o int."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, pd.Timestamp):
        return val.date()
    if isinstance(val, str):
        val_clean = val.strip()
        if not val_clean or val_clean.lower() in ["nan", "nat", "none"]:
            return None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(val_clean.split(" ")[0], fmt).date()
            except ValueError:
                continue
    return None


def parse_int_safe(val: Any) -> Optional[int]:
    """Parsea un entero de forma segura."""
    if val is None or pd.isna(val):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


class ESAVIExtractor:
    """
    Extractor de registros clínicos ESAVI a partir de plantillas Excel (.xlsx / .xlsm).
    """

    def __init__(
        self,
        coordenadas: Optional[Dict[str, Tuple[int, int]]] = None,
        sheet_name: str = "Registro",
        skiprows: int = 7,
    ):
        self.coordenadas = coordenadas or COORDENADAS_ESAVI
        self.sheet_name = sheet_name
        self.skiprows = skiprows

    def _find_target_sheet(self, source: Union[str, bytes, BytesIO]) -> str:
        """Encuentra la hoja adecuada ('Registro', 'Registo', etc.) dinámicamente."""
        try:
            if isinstance(source, bytes):
                src_buf = BytesIO(source)
            elif isinstance(source, BytesIO):
                src_buf = BytesIO(source.getvalue())
            else:
                src_buf = source

            wb = openpyxl.load_workbook(src_buf, read_only=True)
            sheet_names = wb.sheetnames
            wb.close()

            # 1. Buscar coincidencia exacta o por variante común
            for s in sheet_names:
                s_lower = s.lower().strip()
                if s_lower in ["registro", "registo", "esavi", "datos", "hoja1"]:
                    return s
            
            # 2. Buscar si contiene 'regist'
            for s in sheet_names:
                if "regist" in s.lower():
                    return s

            # 3. Fallback a la primera hoja
            return sheet_names[0] if sheet_names else self.sheet_name
        except Exception:
            return self.sheet_name

    @staticmethod
    def validar_curp_basica(valor: str) -> bool:
        """Valida que la celda de la CURP/Identificador no esté vacía y tenga texto válido."""
        if not isinstance(valor, str):
            return False
        valor = valor.strip()
        if not valor or valor.lower() in ["nan", "nat", "none", "null"]:
            return False
        # Válido si tiene al menos 2 caracteres alfanuméricos
        return len(valor) >= 2 and any(c.isalnum() for c in valor)

    def extraer_dict(self, source: Union[str, bytes, BytesIO]) -> Dict[str, Any]:
        """
        Extrae todos los campos definidos en las coordenadas en un diccionario sanitizado.
        """
        if isinstance(source, bytes):
            source_bytes = source
            source = BytesIO(source_bytes)
        elif isinstance(source, BytesIO):
            source_bytes = source.getvalue()
            source = BytesIO(source_bytes)
        else:
            source_bytes = None

        target_sheet = self._find_target_sheet(source_bytes if source_bytes is not None else source)
        if source_bytes is not None:
            source = BytesIO(source_bytes)

        df_raw = pd.read_excel(source, sheet_name=target_sheet, skiprows=self.skiprows, engine="openpyxl")

        # 1. Validación de posicionamiento por CURP
        fila_curp, col_curp = self.coordenadas.get("CURP", (0, 4))
        if fila_curp >= df_raw.shape[0] or col_curp >= df_raw.shape[1]:
            raise ValueError("Estructura de Excel no coincide con el formato esperado (CURP fuera de rango).")

        valor_curp = df_raw.iloc[fila_curp, col_curp]
        if pd.isna(valor_curp) or not self.validar_curp_basica(str(valor_curp)):
            raise ValueError(
                f"El archivo no tiene una CURP válida en la posición ({fila_curp}, {col_curp}). "
                f"Valor encontrado: '{valor_curp}'"
            )

        # 2. Extracción de coordenadas
        datos: Dict[str, Any] = {}
        max_filas, max_cols = df_raw.shape
        for campo, (fila, col) in self.coordenadas.items():
            if (fila == 0 and col == 0 and campo != "CURP") or fila >= max_filas or col >= max_cols:
                datos[campo] = None
            else:
                val = df_raw.iloc[fila, col]
                datos[campo] = sanitizar_valor(val)

        # 3. Concatenación de partes del nombre completo
        partes_nombre = []
        for r, c in PARTES_NOMBRE:
            if r < max_filas and c < max_cols:
                val = df_raw.iat[r, c]
                if pd.notna(val) and str(val).strip():
                    partes_nombre.append(str(val).strip())

        if partes_nombre:
            datos["Nombre"] = " ".join(partes_nombre)

        return datos

    def extraer_registro_normalizado(
        self, source: Union[str, bytes, BytesIO], archivo_fuente: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extrae y normaliza los datos separando las columnas indexadas del diccionario completo.
        """
        raw_dict = self.extraer_dict(source)

        curp = str(raw_dict.get("CURP", "")).strip().upper()
        nombre_completo = raw_dict.get("Nombre")
        edad_anios = parse_int_safe(raw_dict.get("Edad_Anios"))
        edad_meses = parse_int_safe(raw_dict.get("Edad_Meses"))
        edad_dias = parse_int_safe(raw_dict.get("Edad_Dias"))
        sexo = parse_int_safe(raw_dict.get("Sexo"))
        entidad_fed = raw_dict.get("Entidad_Fed")
        municipio = raw_dict.get("Municipio")
        jurisdiccion = raw_dict.get("Jurisdiccion_2") or raw_dict.get("Jurisdiccion_3") or raw_dict.get("jurisdiccion_sanitaria10")
        sem_epi = parse_int_safe(raw_dict.get("Sem_Epi"))
        vacuna_1 = raw_dict.get("vacuna")
        dosis_1 = str(raw_dict.get("dosis")) if raw_dict.get("dosis") is not None else None
        fecha_aplicacion_1 = parse_date_safe(raw_dict.get("fecha_aplicacion_dia_mes_ano"))
        requirio_hospitalizacion = parse_int_safe(raw_dict.get("requirio_hospitalizacion"))
        recuperacion = parse_int_safe(raw_dict.get("recuperacion"))
        estado_actual = raw_dict.get("estado_actual")

        return {
            "curp": curp,
            "nombre_completo": nombre_completo,
            "edad_anios": edad_anios,
            "edad_meses": edad_meses,
            "edad_dias": edad_dias,
            "sexo": sexo,
            "entidad_fed": entidad_fed,
            "municipio": municipio,
            "jurisdiccion": jurisdiccion,
            "sem_epi": sem_epi,
            "vacuna_1": vacuna_1,
            "dosis_1": dosis_1,
            "fecha_aplicacion_1": fecha_aplicacion_1,
            "requirio_hospitalizacion": requirio_hospitalizacion,
            "recuperacion": recuperacion,
            "estado_actual": estado_actual,
            "archivo_fuente": archivo_fuente,
            "datos_completos": raw_dict,
        }
