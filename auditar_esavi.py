#!/usr/bin/env python3
"""
Script de Auditoría e Inspección de Coordenadas para Archivos Clínicos ESAVI.

Permite cargar cualquier archivo Excel (.xlsx / .xlsm) y verificar celda por celda:
- Hoja detectada
- Coordenada interna (fila, columna)
- Celda exacta en Excel (ej. E8, E10, C83, J154)
- Valor crudo en la plantilla vs Valor sanitizado por el motor
- Agrupación por categorías clínicas (Demografía, Vacunas, Síntomas, Hospitalización, Desenlace)

Uso:
    python auditar_esavi.py
    python auditar_esavi.py ruta/al/archivo.xlsm
    python auditar_esavi.py ruta/al/archivo.xlsm --csv
    python auditar_esavi.py ruta/al/archivo.xlsm --search vacuna
"""

import os
import sys
import argparse
import glob
from typing import Dict, Any, Tuple, Optional
import openpyxl
from openpyxl.utils import get_column_letter
import pandas as pd

# Añadir raíz del proyecto al sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.extractor.engine import ESAVIExtractor
from app.extractor.coordenadas import COORDENADAS_ESAVI, PARTES_NOMBRE

# Categorización de variables para inspección estructurada
CATEGORIAS = {
    "1. DATOS GENERALES Y DEMOGRÁFICOS": [
        "CURP", "Nombre", "Sem_Epi", "Edad_Anios", "Edad_Meses", "Edad_Dias", "Sexo",
        "Entidad_Fed", "Municipio", "indigena?", "habla_lengua_indigena", "Migrante?",
        "Unidad_notificante", "Institucion_adscripcion", "CLUES_notificante",
        "Estado_2", "Jurisdiccion_2", "Municipio_2", "Fecha_notificacion_jur",
        "Fecha_notif_estatal", "Fecha_ini_estudio", "Nombre_unidad_vacunadora",
        "Insititucion_vacunadora", "CLUES_vacunadora", "Nombre_vacunador", "Escolaridad",
        "antiguedad_en_el_puesto_del_vacunador", "mujer_embarazada", "semana_gestacion",
        "padece_alguna_enfermedad_infecciosa_15_dias_antes_de_la_vacunacion",
        "se_encontraba_sano_antes_de_la_vacunacion", "padece_alguna_alergia"
    ],
    "2. BIOLÓGICOS Y VACUNACIÓN (VACUNA 1, 2, 3)": [
        "vacuna", "dosis", "fecha_aplicacion_dia_mes_ano", "denominacion_distintiva",
        "laboratorio_productor", "numero_de_lote_vacuna", "fecha_de_caducidad_vacuna_1",
        "numero_de_lote_diluyente_1", "fecha_de_caducidad_diluyente_1", "presentacion_de_la_vacuna_1",
        "vacuna_2", "dosis2", "fecha_de_aplicacion_dia_mes_ano_2", "numero_de_lote_vacuna_2",
        "vacuna_3", "dosis3", "fecha_de_aplicacion_dia_mes_ano_3", "numero_de_lote_vacuna_3",
        "sitio_de_la_vacunacion", "fecha_de_apertura_del_frasco_multidosis", "error_en_aplicacion_de_la_vacuna"
    ],
    "3. CUADRO CLÍNICO Y SÍNTOMAS": [
        "fecha_de_primer_contacto_con_los_ss", "Hora de inicio de primer signo o síntoma",
        "fecha_de_inicio_de_primer_signo_o_sintoma-apartado_cuadro_clinico ",
        "intervalo_entre_la_vacunacion_y_el_signo_o_sintoma", "fiebre_mayor_38c", "cefalea",
        "astenia_fatiga", "adinamia", "llanto_persistente", "irritabilidad_SEPARADO_DE_LLANTO_PERSISTENTE",
        "escalofrios", "induracion_nodulo", "dolor_sensibilidad", "eritema_enrojecimiento",
        "edema_general", "celulitis", "prurito_general_descripcion_del_esavi", "absceso",
        "aumento_de_temperatura", "mareo", "exantema", "linfadenopatia", "nausea", "vomito",
        "dolor_abdominal", "diarrea", "taquicardia", "tos", "disnea_dificultad_respiratoria",
        "mialgia", "artralgia", "crisis_convulsivas_afebril", "crisis_convulsivas_febril",
        "sindrome_de_guillain_barre", "choque_anfilactico_anafilaxia", "sincope", "otro", "especifique",
        "descripcion_cuadro_clinico", "tratamiento_administrado"
    ],
    "4. HOSPITALIZACIÓN, CLASIFICACIÓN Y CAUSALIDAD": [
        "tipo_de_esavi", "biologico_atribuible_al_esavi", "evento_relacionado_vacuna",
        "indeterminado", "evento_relacionado_defecto_vacuna", "asociacion_causal_coincidente ",
        "nombre_de_la_unidad10", "institucion10", "clave_clues_de_la_unidad10",
        "requirio_hospitalizacion", "fecha_de_hospitalizacion", "diagnostico_de_ingreso",
        "fecha_de_egreso", "diagnostico_de_egreso"
    ],
    "5. DESENLACE Y ESTADO FINAL": [
        "estado_actual", "recuperacion", "causa_de_la_defuncion", "presenta_secuelas"
    ]
}


def obtener_celda_excel(fila_df: int, col_df: int, skiprows: int = 7) -> str:
    """Convierte coordenadas 0-indexed con skiprows a referencia Excel (ej. E8, C83)."""
    if fila_df == 0 and col_df == 0:
        return "N/A"
    col_letter = get_column_letter(col_df + 1)
    row_number = fila_df + skiprows + 1
    return f"{col_letter}{row_number}"


def seleccionar_archivo_interactivo() -> Optional[str]:
    """Permite al usuario seleccionar un archivo de muestra si no se pasa por argumento."""
    rutas_posibles = [
        "/home/najera/dev/documentacion/esavis",
        os.path.join(os.path.dirname(__file__), "muestras"),
        "."
    ]
    archivos = []
    for r in rutas_posibles:
        if os.path.exists(r):
            archivos.extend(glob.glob(os.path.join(r, "*.xlsm")))
            archivos.extend(glob.glob(os.path.join(r, "*.xlsx")))

    archivos = sorted(list(set(archivos)))
    if not archivos:
        print("❌ No se encontraron archivos Excel (.xlsm / .xlsx) para auditar.")
        return None

    print("\n📁 Archivos encontrados disponibles para auditar:")
    for idx, f in enumerate(archivos[:25], 1):
        print(f"  [{idx:02d}] {os.path.basename(f)}")
    
    if len(archivos) > 25:
        print(f"  ... y {len(archivos) - 25} archivos más.")

    try:
        seleccion = input(f"\nSelecciona un número (1 - {min(len(archivos), 25)}) o presiona Enter para el [1]: ").strip()
        idx_elegido = int(seleccion) - 1 if seleccion else 0
        if 0 <= idx_elegido < len(archivos):
            return archivos[idx_elegido]
        return archivos[0]
    except Exception:
        return archivos[0]


def auditar_archivo(ruta_archivo: str, filtro_busqueda: Optional[str] = None, exportar_csv: bool = False):
    print("=" * 80)
    print(f"🔬 AUDITORÍA DE EXTRACCIÓN ESAVI: {os.path.basename(ruta_archivo)}")
    print(f"📂 Ruta completa: {ruta_archivo}")
    print("=" * 80)

    if not os.path.exists(ruta_archivo):
        print(f"❌ Error: El archivo '{ruta_archivo}' no existe.")
        return

    extractor = ESAVIExtractor()
    with open(ruta_archivo, "rb") as f:
        contenido = f.read()

    # 1. Detectar Hoja
    hoja_detectada = extractor._find_target_sheet(contenido)
    print(f"\n📑 Hoja identificada en Excel: '{hoja_detectada}'")

    # 2. Extracción directa del diccionario y registro normalizado
    try:
        datos_extraidos = extractor.extraer_dict(contenido)
        norm = extractor.extraer_registro_normalizado(contenido, archivo_fuente=os.path.basename(ruta_archivo))
    except Exception as e:
        print(f"❌ Error al procesar el archivo con el extractor: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. Inspección especial de partes del Nombre
    print("\n👤 INSPECCIÓN DE COMPOSICIÓN DEL NOMBRE COMPLETO:")
    try:
        df_raw = pd.read_excel(ruta_archivo, sheet_name=hoja_detectada, skiprows=7, engine="openpyxl")
        max_r, max_c = df_raw.shape
        print(f"  Dimensiones de la matriz útil: {max_r} filas x {max_c} columnas")
        
        nombres_partes = []
        for r, c in PARTES_NOMBRE:
            celda = obtener_celda_excel(r, c)
            val = df_raw.iat[r, c] if r < max_r and c < max_c else None
            nombres_partes.append((celda, val))
            print(f"  - Celda [{celda}]: '{val}'")
        print(f"  ➡️  Nombre Resultante Concatenado: '{datos_extraidos.get('Nombre')}'")
    except Exception as e:
        print(f"  ⚠️ No se pudo inspeccionar el desglose del nombre: {e}")

    # 4. Desglose de variables por Categorías
    campos_mostrados = set()
    total_con_valor = 0
    filas_para_csv = []

    print("\n" + "=" * 80)
    print(f"{'VARIABLE / CAMPO':<40} | {'CELDA':<6} | {'VALOR EXTRAÍDO':<28}")
    print("=" * 80)

    for cat_nombre, lista_campos in CATEGORIAS.items():
        print(f"\n🔷 {cat_nombre}")
        print("-" * 80)

        for campo in lista_campos:
            if filtro_busqueda and filtro_busqueda.lower() not in campo.lower():
                continue

            r, c = COORDENADAS_ESAVI.get(campo, (0, 0))
            celda = obtener_celda_excel(r, c)
            val = datos_extraidos.get(campo)
            campos_mostrados.add(campo)

            # Formateo visual
            if val is not None and str(val).strip() != "":
                total_con_valor += 1
                val_str = str(val)
                # Resaltar valores clave como requirio_hospitalizacion y recuperacion
                if campo == "requirio_hospitalizacion":
                    val_str += f" ({'1=SÍ' if val in [1, '1', 1.0] else '2=NO'})"
                elif campo == "recuperacion":
                    val_str += f" ({'1=SÍ' if val in [1, '1', 1.0] else '2=NO'})"
                elif campo == "sexo":
                    val_str += f" ({'Hombre' if val == 1 else ('Mujer' if val == 2 else 'ND')})"

                print(f"  ✅ {campo:<37} | {celda:<6} | \033[1;32m{val_str[:28]:<28}\033[0m")
            else:
                print(f"  ⚪ {campo:<37} | {celda:<6} | \033[90mNone / Vacío\033[0m")

            filas_para_csv.append({
                "Categoria": cat_nombre,
                "Campo": campo,
                "Fila_DF": r,
                "Columna_DF": c,
                "Celda_Excel": celda,
                "Valor_Extraido": val,
                "Tiene_Valor": "SÍ" if val is not None and str(val).strip() != "" else "NO"
            })

    # Campos restantes no categorizados explícitamente
    restantes = [k for k in COORDENADAS_ESAVI.keys() if k not in campos_mostrados]
    if restantes and not filtro_busqueda:
        print("\n🔷 6. OTROS CAMPOS Y VARIABLES ADICIONALES")
        print("-" * 80)
        for campo in restantes:
            r, c = COORDENADAS_ESAVI.get(campo, (0, 0))
            celda = obtener_celda_excel(r, c)
            val = datos_extraidos.get(campo)
            if val is not None and str(val).strip() != "":
                total_con_valor += 1
                print(f"  ✅ {campo:<37} | {celda:<6} | \033[1;32m{str(val)[:28]:<28}\033[0m")
            else:
                print(f"  ⚪ {campo:<37} | {celda:<6} | \033[90mNone / Vacío\033[0m")

            filas_para_csv.append({
                "Categoria": "OTROS",
                "Campo": campo,
                "Fila_DF": r,
                "Columna_DF": c,
                "Celda_Excel": celda,
                "Valor_Extraido": val,
                "Tiene_Valor": "SÍ" if val is not None and str(val).strip() != "" else "NO"
            })

    print("\n" + "=" * 80)
    print("📊 RESUMEN DE AUDITORÍA:")
    print(f"  - Total de variables mapeadas: {len(COORDENADAS_ESAVI)}")
    print(f"  - Variables con datos capturados: {total_con_valor}")
    print(f"  - Variables vacías / no aplicables: {len(COORDENADAS_ESAVI) - total_con_valor}")
    print(f"  - CURP Identificada: {norm.get('curp')}")
    print(f"  - Paciente: {norm.get('nombre_completo')}")
    print(f"  - Vacuna / Dosis: {norm.get('vacuna_1')} ({norm.get('dosis_1')})")
    print(f"  - Fecha de Aplicación: {norm.get('fecha_aplicacion_1')}")
    print(f"  - Requirió Hospitalización (1=Sí, 2=No): {norm.get('requirio_hospitalizacion')}")
    print(f"  - Recuperación / Alta (1=Sí, 2=No): {norm.get('recuperacion')}")
    print(f"  - Jurisdicción / Región: {norm.get('jurisdiccion')}")
    print("=" * 80)

    # 5. Exportar a CSV si se solicita
    if exportar_csv:
        nombre_base = os.path.splitext(os.path.basename(ruta_archivo))[0]
        csv_salida = f"auditoria_{nombre_base}.csv"
        pd.DataFrame(filas_para_csv).to_csv(csv_salida, index=False, encoding="utf-8-sig")
        print(f"\n💾 Archivo de auditoría guardado exitosamente en: {csv_salida}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auditoría de celdas y variables de formatos clínicos ESAVI.")
    parser.add_argument("archivo", nargs="?", help="Ruta al archivo Excel (.xlsx / .xlsm) a auditar.")
    parser.add_argument("--search", "-s", help="Filtrar variables por término de búsqueda (ej. --search vacuna).")
    parser.add_argument("--csv", action="store_true", help="Exportar reporte detallado en archivo CSV.")

    args = parser.parse_args()

    archivo_a_auditar = args.archivo
    if not archivo_a_auditar:
        archivo_a_auditar = seleccionar_archivo_interactivo()

    if archivo_a_auditar:
        auditar_archivo(archivo_a_auditar, filtro_busqueda=args.search, exportar_csv=args.csv)
