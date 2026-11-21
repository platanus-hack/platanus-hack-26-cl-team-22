#!/usr/bin/env python3
"""Descarga (con cache) y extrae la tabla de cumplimiento del PPDA RM.

Fuente: "Informe Final - Revision de las medidas del PPDA Region Metropolitana"
(ECOS-Chile, 2023; licitacion ID 608897-78-LE23), encargado por la SEREMI del
Medio Ambiente RM.

Que hace este script
--------------------
1. Descarga el PDF al cache local (data/raw/politicas/) si no esta o si el
   checksum no calza. No ejecuta nada del archivo descargado: solo lo lee con
   pypdf.
2. Extrae el texto pagina por pagina.
3. Verifica que la tabla resumen global (Tabla 18, pagina 67 del PDF) diga
   38 / 33 / 86 = 157 y que cada cifra por capitulo que usamos exista
   literalmente en la pagina citada. Si un fragmento no aparece, falla.
4. Escribe data/politicas/cumplimiento_ppda_capitulos.csv.

Por que el CSV es por capitulo y no por medida
----------------------------------------------
El PDF publicado no trae la tabla medida por medida. El informe dice que las
fichas por medida y la planilla de sistematizacion estan en documentos aparte
del repositorio digital (pagina 149) y solo muestra un ejemplo de ficha
(pagina 123). En 159 paginas aparecen seis codigos de medida en total. Por eso
el script escribe el nivel de detalle que si esta respaldado: conteos de
conformidad por capitulo del PPDA. Ver data/politicas/README.md.

Uso
---
    python build_credibilidad.py                # usa cache si es valido
    python build_credibilidad.py --forzar-descarga
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import re
import sys
import urllib.request
from pathlib import Path

# La consola de Windows suele ser cp1252: evita romper al imprimir acentos.
with contextlib.suppress(AttributeError, ValueError):  # solo cosmetico
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

URL = "https://airerm.mma.gob.cl/wp-content/uploads/2024/03/2023_Informe-Revision-PPDA.pdf"
SHA256_ESPERADO = "4a4446d21b58d026267a7d8274e2af641a7e8c96d5a5337eef99292847ed69fa"
FECHA_DESCARGA = "2026-11-21"

RAIZ = Path(__file__).resolve().parents[2]
PDF_PATH = RAIZ / "data" / "raw" / "politicas" / "2023_Informe-Revision-PPDA.pdf"
CSV_PATH = RAIZ / "data" / "politicas" / "cumplimiento_ppda_capitulos.csv"

# Cada capitulo declara los conteos y TODOS los fragmentos literales que los
# respaldan. El script verifica que cada fragmento exista en el PDF y usa la
# pagina donde aparece como evidencia.
CAPITULOS = [
    {
        "capitulo": "III",
        "tema": "Fuentes móviles",
        "fuente_objetivo": "transporte",
        "medidas_unicas": 18,
        "medidas_evaluadas": 31,
        "conformes": 7,
        "parciales": 19,
        "no_conformes": 5,
        "fragmentos": [
            "un total de 18 compromisos o medidas",
            "se analizan un total de 31 medidas distribuidas en 13 organismos sectoriales",
            "7 medidas Conformes (23% del total de medidas)",
            "19 medidas estuvieron Parcialmente Conforme (61% del total)",
            "5 medidas del tipo No Conformes (16% del total de medidas)",
        ],
        "citas": [
            "7 medidas Conformes (23% del total de medidas)",
            "19 medidas estuvieron Parcialmente Conforme (61% del total)",
            "5 medidas del tipo No Conformes (16% del total de medidas)",
        ],
    },
    {
        "capitulo": "IV",
        "tema": "Combustibles",
        "fuente_objetivo": "otra",
        "medidas_unicas": 11,
        "medidas_evaluadas": 12,
        "conformes": 0,
        "parciales": 0,
        "no_conformes": 12,
        "fragmentos": [
            "Considera un total de 11 medidas o compromisos",
            "se reconoce un total de 11 medidas bajo la autoría de la SEC y 1 medida bajo la autoría del MMA",
            "la totalidad de las medidas se encuentran No Conformes",
        ],
        "citas": ["la totalidad de las medidas se encuentran No Conformes"],
    },
    {
        "capitulo": "V",
        "tema": "Control de emisiones de COV asociado a la cadena de distribución de combustibles",
        "fuente_objetivo": "otra",
        "medidas_unicas": 5,
        "medidas_evaluadas": 5,
        "conformes": 0,
        "parciales": 1,
        "no_conformes": 4,
        "fragmentos": [
            "un total de 5 medidas a cargo del organismo sectorial Superintendencia de Electricidad y Combustibles",
            "1 medida (20%) se encuentra Parcialmente Conforme",
            "4 de las medidas (80%) se encuentran No conformes",
        ],
        "citas": [
            "1 medida (20%) se encuentra Parcialmente Conforme",
            "4 de las medidas (80%) se encuentran No conformes",
        ],
    },
    {
        "capitulo": "VI",
        "tema": "Fuentes estacionarias",
        "fuente_objetivo": "industria",
        "medidas_unicas": None,  # el informe no declara el total de codigos unicos
        "medidas_evaluadas": 58,
        "conformes": 10,
        "parciales": 5,
        "no_conformes": 43,
        "fragmentos": [
            "un total de 58 medidas distribuidas en 4 organismos sectoriales",
            "un 17% de medidas Conformes (10 medidas) y un 9% como Parcialmente Conforme (5 medidas)",
            "un 74% No Conformes (43 medidas)",
        ],
        "citas": [
            "un 17% de medidas Conformes (10 medidas) y un 9% como Parcialmente Conforme (5 medidas)",
            "un 74% No Conformes (43 medidas)",
        ],
    },
    {
        "capitulo": "VII",
        "tema": "Control de emisiones por uso de leña, pellet y derivados de la madera",
        "fuente_objetivo": "lena",
        "medidas_unicas": None,
        "medidas_evaluadas": 23,
        "conformes": 4,
        "parciales": 7,
        "no_conformes": 12,
        "fragmentos": [
            "se contemplan un total de 23 medidas",
            "4 de estas medidas se encontraron conformes",
            "parcialmente conforme (30% del total)",
            "12 de estas se encontraron como No conforme (52%)",
        ],
        "citas": [
            "4 de estas medidas se encontraron conformes",
            "parcialmente conforme (30% del total)",
            "12 de estas se encontraron como No conforme (52%)",
        ],
    },
    {
        "capitulo": "VIII",
        "tema": "Control de emisiones de quemas agrícolas, forestales y de residuos",
        "fuente_objetivo": "quemas",
        "medidas_unicas": 4,
        "medidas_evaluadas": 4,
        "conformes": 1,
        "parciales": 1,
        "no_conformes": 2,
        "fragmentos": [
            "abarcando un total de 4 medidas o compromisos distribuidos en 4 organismos sectoriales",
            "solamente la medida bajo la autoría de la SEREMI de Agricultura se encontró conforme",
            "la medida de carabineros que se encontró parcialmente conforme",
            "2 medidas No conformes",
        ],
        "citas": [
            "solamente la medida bajo la autoría de la SEREMI de Agricultura se encontró conforme",
            "la medida de carabineros que se encontró parcialmente conforme",
            "2 medidas No conformes",
        ],
    },
    {
        "capitulo": "IX",
        "tema": "Control del levantamiento de polvo y generación de áreas verdes",
        "fuente_objetivo": "otra",
        "medidas_unicas": 5,
        "medidas_evaluadas": 5,
        "conformes": 2,
        "parciales": 3,
        "no_conformes": 0,
        "fragmentos": [
            "a través de 5 medidas distribuidas",
            "un 60% de estas (3) se encuentran Parcialmente conformes",
            "un 40% de las medidas se encontraron conformes",
        ],
        "citas": [
            "un 60% de estas (3) se encuentran Parcialmente conformes",
            "un 40% de las medidas se encontraron conformes",
        ],
    },
    {
        "capitulo": "X",
        "tema": "Medidas de incentivo al cambio modal",
        "fuente_objetivo": "transporte",
        "medidas_unicas": 4,
        "medidas_evaluadas": 5,
        "conformes": 3,
        "parciales": 0,
        "no_conformes": 2,
        "fragmentos": [
            "un total de 4 medidas bajo la autoría de 3 organismos sectoriales",
            "aumenta el total de medidas a un total de 5",
            "el 60% de las medidas (3) se encontraron conformes",
            "solo el 40% (2) se encontraron como no conformes",
        ],
        "citas": [
            "el 60% de las medidas (3) se encontraron conformes",
            "solo el 40% (2) se encontraron como no conformes",
        ],
    },
    {
        "capitulo": "XI",
        "tema": "Educación ambiental y gestión ambiental local",
        "fuente_objetivo": "otra",
        "medidas_unicas": 9,
        "medidas_evaluadas": 10,
        "conformes": 3,
        "parciales": 7,
        "no_conformes": 0,
        "fragmentos": [
            "un total de 9 medidas distribuidas en 5 organismos sectoriales",
            "aumentaría la cantidad de medidas a",
            "un total de 10, debido a que la medida EAP-03",
            "el 30% de las medidas se encontraron conformes",
            "el 70% de las medidas (7) se encuentra parcialmente conforme",
        ],
        "citas": [
            "el 30% de las medidas se encontraron conformes",
            "el 70% de las medidas (7) se encuentra parcialmente conforme",
        ],
    },
    {
        "capitulo": "XII",
        "tema": "Plan operacional para la gestión de episodios críticos",
        "fuente_objetivo": "episodios",
        "medidas_unicas": None,
        "medidas_evaluadas": 33,
        "conformes": 12,
        "parciales": 5,
        "no_conformes": 16,
        "fragmentos": [
            "asciende a un total de 33 medidas",
            "un 36% de las medidas (12) se encontraron conformes",
            "un 15% de las medidas (5) se encontraron como Parcialmente conformes",
            "Respecto a las medidas No conformes un 48% de las medidas",
            "(16) se encuentran bajo esta tipología",
        ],
        "citas": [
            "un 36% de las medidas (12) se encontraron conformes",
            "un 15% de las medidas (5) se encontraron como Parcialmente conformes",
            "Respecto a las medidas No conformes un 48% de las medidas",
            "(16) se encuentran bajo esta tipología",
        ],
    },
]

# Tabla 18, pagina 67 del PDF: el unico total global que publica el informe.
TOTAL_GLOBAL_FRAGMENTO = "Total general 38 33 86 157"
TOTAL_GLOBAL = {"conformes": 38, "parciales": 33, "no_conformes": 86, "total": 157}

# Pruebas de que el detalle medida por medida NO esta en este PDF.
AUSENCIA_FRAGMENTOS = [
    "estas fichas de revisión se encuentran anexadas al presenten informe",
    "Fichas de revisión separadas por capítulos",
    "Matriz de Sistematización PPDA 2023",
]

CODIGO_MEDIDA = re.compile(r"\b[A-Z]{2,4}[-\u2013]\s?\d{1,2}\b")
# Filtra falsos positivos como "VI-7" (numero romano de capitulo + inciso).
SOLO_ROMANO = re.compile(r"^[IVXLCDM]+[-\u2013]\s?\d{1,2}$")


def normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


def asegurar_pdf(forzar: bool = False) -> Path:
    """Descarga el PDF al cache si hace falta. No ejecuta el contenido."""
    if PDF_PATH.exists() and not forzar:
        datos = PDF_PATH.read_bytes()
        if hashlib.sha256(datos).hexdigest() == SHA256_ESPERADO:
            print(f"[cache] {PDF_PATH} (sha256 ok, {len(datos)} bytes)")
            return PDF_PATH
        print("[cache] checksum distinto: se vuelve a descargar")

    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"[descarga] {URL}")
    peticion = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(peticion, timeout=180) as respuesta:
        datos = respuesta.read()

    if not datos.startswith(b"%PDF-"):
        raise SystemExit("ERROR: la descarga no es un PDF. No se escribe nada.")
    sha = hashlib.sha256(datos).hexdigest()
    if sha != SHA256_ESPERADO:
        print(f"[aviso] sha256 descargado {sha} distinto del esperado {SHA256_ESPERADO}")
    PDF_PATH.write_bytes(datos)
    print(f"[descarga] {len(datos)} bytes -> {PDF_PATH}")
    return PDF_PATH


def extraer_paginas(pdf_path: Path) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit(
            "ERROR: falta pypdf. Instalar con: python -m pip install pypdf"
        )

    lector = PdfReader(str(pdf_path))
    paginas = [(pagina.extract_text() or "") for pagina in lector.pages]
    if not any(p.strip() for p in paginas):
        raise SystemExit(
            "ERROR: el PDF no tiene capa de texto (seria un escaneo). "
            "No se puede extraer la tabla sin OCR."
        )
    return [normalizar(p) for p in paginas]


def buscar_fragmento(paginas: list[str], fragmento: str) -> list[int]:
    objetivo = normalizar(fragmento)
    return [i + 1 for i, pagina in enumerate(paginas) if objetivo in pagina]


def ubicar(fragmentos: list[str], paginas: list[str]) -> list[int]:
    """Devuelve las paginas (1-based) donde aparece cada fragmento."""
    encontradas = []
    faltantes = []
    for fragmento in fragmentos:
        hits = buscar_fragmento(paginas, fragmento)
        if not hits:
            faltantes.append(fragmento)
        else:
            encontradas.append(hits[0])
    if faltantes:
        detalle = "\n".join(f"  - {f!r}" for f in faltantes)
        raise SystemExit(
            "ERROR: el PDF no contiene estos fragmentos esperados:\n"
            f"{detalle}\n"
            "El documento cambio o la extraccion fallo. No se escribe el CSV."
        )
    return encontradas


def construir_filas(paginas: list[str]) -> list[dict]:
    filas = []
    for cap in CAPITULOS:
        suma = cap["conformes"] + cap["parciales"] + cap["no_conformes"]
        if suma != cap["medidas_evaluadas"]:
            raise SystemExit(
                f"ERROR interno: capitulo {cap['capitulo']} suma {suma} "
                f"y declara {cap['medidas_evaluadas']} medidas evaluadas."
            )

        paginas_evidencia = ubicar(cap["fragmentos"], paginas)
        primera, ultima = min(paginas_evidencia), max(paginas_evidencia)
        pagina_pdf = str(primera) if primera == ultima else f"{primera}-{ultima}"

        # Las citas tambien deben existir: si una cita no calza, es un error.
        ubicar(cap["citas"], paginas)

        evaluadas = cap["medidas_evaluadas"]
        filas.append(
            {
                "capitulo": cap["capitulo"],
                "tema": cap["tema"],
                "fuente_objetivo": cap["fuente_objetivo"],
                "medidas_unicas_declaradas": "" if cap["medidas_unicas"] is None else cap["medidas_unicas"],
                "medidas_evaluadas": evaluadas,
                "conformes": cap["conformes"],
                "parciales": cap["parciales"],
                "no_conformes": cap["no_conformes"],
                "tasa_conforme": f"{cap['conformes'] / evaluadas:.3f}",
                "tasa_conforme_o_parcial": f"{(cap['conformes'] + cap['parciales']) / evaluadas:.3f}",
                "pagina_pdf": pagina_pdf,
                "cita": " ... ".join(cap["citas"]),
            }
        )
    return filas


def verificar_total_global(paginas: list[str]) -> None:
    hits = buscar_fragmento(paginas, TOTAL_GLOBAL_FRAGMENTO)
    if not hits:
        raise SystemExit(
            f"ERROR: no se encontro la Tabla 18 ({TOTAL_GLOBAL_FRAGMENTO!r})."
        )


def diagnostico_sin_detalle(paginas: list[str], filas: list[dict]) -> None:
    """Deja constancia, en la salida, de que no hay tabla medida por medida."""
    texto = " ".join(paginas)
    codigos = sorted({c.strip() for c in CODIGO_MEDIDA.findall(texto) if not SOLO_ROMANO.match(c.strip())})
    print()
    print("Diagnostico: detalle medida por medida")
    print(f"  Paginas del PDF: {len(paginas)}")
    print(f"  Codigos de medida hallados en todo el PDF: {len(codigos)} -> {codigos}")
    for fragmento in AUSENCIA_FRAGMENTOS:
        hits = buscar_fragmento(paginas, fragmento)
        estado = f"pagina {hits[0]}" if hits else "NO ENCONTRADO"
        print(f"  {fragmento!r}: {estado}")
    print(
        "  Conclusion: el PDF solo publica conteos por capitulo (y un ejemplo de "
        "ficha). La tabla de 157 medidas esta en documentos aparte del repositorio "
        "digital que el informe no publica."
    )

    suma_evaluadas = sum(f["medidas_evaluadas"] for f in filas)
    suma_conf = sum(f["conformes"] for f in filas)
    suma_parc = sum(f["parciales"] for f in filas)
    suma_nc = sum(f["no_conformes"] for f in filas)
    print()
    print("Conteos")
    print(
        "  Tabla 18 (codigos unicos): "
        f"{TOTAL_GLOBAL['conformes']} conformes, {TOTAL_GLOBAL['parciales']} parciales, "
        f"{TOTAL_GLOBAL['no_conformes']} no conformes = {TOTAL_GLOBAL['total']}"
    )
    print(
        "  Suma de las filas por capitulo (una medida por organismo): "
        f"{suma_conf} conformes, {suma_parc} parciales, {suma_nc} no conformes = {suma_evaluadas}"
    )
    if suma_evaluadas != TOTAL_GLOBAL["total"]:
        print(
            "  Aviso: no calzan. La Tabla 18 (157) cuenta codigos unicos y, segun su\n"
            "  nota 11, excluye los registros 'No aplica'; los capitulos cuentan cada\n"
            "  medida una vez por organismo responsable."
        )


def escribir_csv(filas: list[dict]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    campos = [
        "capitulo",
        "tema",
        "fuente_objetivo",
        "medidas_unicas_declaradas",
        "medidas_evaluadas",
        "conformes",
        "parciales",
        "no_conformes",
        "tasa_conforme",
        "tasa_conforme_o_parcial",
        "pagina_pdf",
        "cita",
    ]
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(filas)
    print(f"\n[ok] {len(filas)} filas -> {CSV_PATH}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--forzar-descarga",
        action="store_true",
        help="ignora el cache y vuelve a descargar el PDF",
    )
    args = parser.parse_args()

    pdf = asegurar_pdf(forzar=args.forzar_descarga)
    paginas = extraer_paginas(pdf)
    verificar_total_global(paginas)
    filas = construir_filas(paginas)
    escribir_csv(filas)
    diagnostico_sin_detalle(paginas, filas)
    print(f"\nFecha de descarga registrada: {FECHA_DESCARGA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
