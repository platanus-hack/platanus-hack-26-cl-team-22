"""Prueba de riesgo: ¿las políticas de aire cambian la brecha entre comunas?

Pregunta que responde (ver docs/ideas.md, "riesgo principal en 2 h"):
si una política mueve a todas las comunas por igual, apagarla no reordena
nada y la demo de "ranking que cambia" no muestra nada. Aquí se mide cuánto
cambian la brecha y el orden entre comunas bajo medidas regionales y locales.

Modelo de tamizaje (no es el modelo final):

    C[r] = b + k * sum_c E[c] * exp(-d(r, c) / L)

- C[r]: PM2,5 medio anual en el receptor r (estación o comuna), en µg/m³.
- E[c]: emisiones primarias de PM2,5 de la comuna c, en t/año.
- d: distancia entre centroides, en km.  L: escala de mezcla en la cuenca.
- b: fondo regional (aerosol secundario, polvo, aporte externo).

b y k se ajustan por mínimos cuadrados no negativos contra las estaciones;
L se elige por error dejando una estación fuera. Con ~11 estaciones el
ajuste es grueso: sirve para ver el signo y el orden de magnitud del efecto,
no para proyectar.

Uso:  python -m experiments.prueba_brecha
"""

from __future__ import annotations

import csv
import math
import sys
import unicodedata
from pathlib import Path

import numpy as np
from scipy.optimize import nnls
from scipy.stats import spearmanr

RAIZ = Path(__file__).resolve().parent.parent
F_EMISIONES = RAIZ / "data" / "emisiones" / "pm25_por_comuna_fuente.csv"
F_COMUNAS = RAIZ / "data" / "comunas_rm.csv"
F_ESTACIONES = RAIZ / "data" / "aire" / "estaciones.csv"
F_ANUAL = RAIZ / "data" / "aire" / "pm25_anual.csv"
F_SALIDA = RAIZ / "results" / "prueba_brecha.csv"

FUENTES = ("lena", "transporte", "industria", "otras")
ESCALAS_KM = (3.0, 5.0, 8.0, 12.0, 18.0, 25.0, 40.0)


def _norm(texto: str) -> str:
    """Clave de comparación: sin tildes, minúsculas, sin espacios dobles."""
    plano = unicodedata.normalize("NFKD", texto or "")
    plano = "".join(ch for ch in plano if not unicodedata.combining(ch))
    return " ".join(plano.lower().replace("'", "").split())


def _num(valor: str | None) -> float | None:
    if valor is None:
        return None
    limpio = valor.strip().replace(",", ".")
    if not limpio:
        return None
    try:
        return float(limpio)
    except ValueError:
        return None


def _leer(ruta: Path) -> list[dict[str, str]]:
    if not ruta.exists():
        sys.exit(f"Falta el archivo de datos: {ruta}")
    with ruta.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia de círculo máximo (haversine)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def cargar_comunas() -> tuple[list[str], np.ndarray]:
    nombres, coords = [], []
    for fila in _leer(F_COMUNAS):
        lat, lon = _num(fila.get("lat")), _num(fila.get("lon"))
        if lat is None or lon is None:
            continue
        nombres.append(fila["comuna"].strip())
        coords.append((lat, lon))
    return nombres, np.array(coords)


def cargar_emisiones(comunas: list[str]) -> tuple[np.ndarray, int, list[str]]:
    """Matriz comuna x fuente (t/año) del año más reciente disponible."""
    filas = _leer(F_EMISIONES)
    anios = sorted({int(f["anio"]) for f in filas if (f.get("anio") or "").strip().isdigit()})
    if not anios:
        sys.exit("El archivo de emisiones no trae la columna anio con valores.")
    anio = anios[-1]
    indice = {_norm(c): i for i, c in enumerate(comunas)}
    matriz = np.zeros((len(comunas), len(FUENTES)))
    sin_calce: set[str] = set()
    for fila in filas:
        if int(fila["anio"]) != anio:
            continue
        valor = _num(fila.get("toneladas_anio"))
        fuente = _norm(fila.get("fuente", ""))
        if valor is None or fuente not in FUENTES:
            continue
        i = indice.get(_norm(fila["comuna"]))
        if i is None:
            sin_calce.add(fila["comuna"])
            continue
        matriz[i, FUENTES.index(fuente)] += valor
    return matriz, anio, sorted(sin_calce)


def cargar_estaciones(anio_objetivo: int) -> tuple[list[str], np.ndarray, np.ndarray, int]:
    """Estaciones con media anual válida; usa el año con datos más cercano."""
    est = {f["estacion_id"]: f for f in _leer(F_ESTACIONES)}
    anual = _leer(F_ANUAL)
    col_media = next(
        (c for c in ("pm25", "pm25_media", "media", "media_anual") if anual and c in anual[0]),
        None,
    )
    if col_media is None:
        sys.exit(f"No encuentro la columna de media anual en {F_ANUAL.name}: {list(anual[0])}")
    por_anio: dict[int, dict[str, float]] = {}
    for fila in anual:
        valor = _num(fila.get(col_media))
        anio_txt = (fila.get("anio") or "").strip()
        if valor is None or not anio_txt.isdigit():
            continue
        por_anio.setdefault(int(anio_txt), {})[fila["estacion_id"]] = valor
    if not por_anio:
        sys.exit("No hay medias anuales válidas de PM2,5.")
    anio = min(por_anio, key=lambda a: (abs(a - anio_objetivo), -len(por_anio[a])))
    nombres, coords, valores = [], [], []
    for eid, valor in por_anio[anio].items():
        meta = est.get(eid)
        lat = _num(meta.get("lat")) if meta else None
        lon = _num(meta.get("lon")) if meta else None
        if lat is None or lon is None:
            continue
        nombres.append(meta["estacion"])
        coords.append((lat, lon))
        valores.append(valor)
    return nombres, np.array(coords), np.array(valores), anio


def nucleo(receptores: np.ndarray, fuentes: np.ndarray, escala_km: float) -> np.ndarray:
    """Matriz receptor x comuna de pesos exp(-d/L)."""
    k = np.empty((len(receptores), len(fuentes)))
    for i, (la, lo) in enumerate(receptores):
        for j, (lb, lob) in enumerate(fuentes):
            k[i, j] = math.exp(-distancia_km(la, lo, lb, lob) / escala_km)
    return k


def ajustar(senal: np.ndarray, observado: np.ndarray) -> tuple[float, float]:
    """Mínimos cuadrados no negativos de observado = b + k * senal."""
    diseno = np.column_stack([np.ones_like(senal), senal])
    coef, _ = nnls(diseno, observado)
    return float(coef[0]), float(coef[1])


def error_dejando_una(senal: np.ndarray, observado: np.ndarray) -> float:
    errores = []
    for i in range(len(observado)):
        resto = np.arange(len(observado)) != i
        b, k = ajustar(senal[resto], observado[resto])
        errores.append(b + k * senal[i] - observado[i])
    return float(np.sqrt(np.mean(np.square(errores))))


def resumen_cambio(base: np.ndarray, escenario: np.ndarray) -> dict[str, float]:
    orden_base = (-base).argsort().argsort()
    orden_esc = (-escenario).argsort().argsort()
    rho = spearmanr(base, escenario).statistic
    delta = escenario - base
    return {
        "cambio_medio": float(delta.mean()),
        "cambio_min": float(delta.min()),
        "cambio_max": float(delta.max()),
        "brecha_base": float(base.max() - base.min()),
        "brecha_escenario": float(escenario.max() - escenario.min()),
        "desv_base": float(base.std()),
        "desv_escenario": float(escenario.std()),
        "spearman": float(rho),
        "comunas_que_cambian_puesto": int((orden_base != orden_esc).sum()),
        "mayor_salto_puestos": int(np.abs(orden_base - orden_esc).max()),
    }


def main() -> None:
    comunas, xy_comunas = cargar_comunas()
    emis, anio_emis, sin_calce = cargar_emisiones(comunas)
    estaciones, xy_est, obs, anio_obs = cargar_estaciones(anio_emis)
    total = emis.sum(axis=1)

    print(f"Comunas con coordenadas: {len(comunas)} | emisiones {anio_emis} | "
          f"estaciones con media anual {anio_obs}: {len(estaciones)}")
    if sin_calce:
        print(f"AVISO: comunas del inventario sin calce en la tabla: {sin_calce}")
    print("Emisiones regionales por fuente (t/año):",
          {f: round(float(v), 1) for f, v in zip(FUENTES, emis.sum(axis=0))})
    if len(estaciones) < 5:
        sys.exit("Menos de 5 estaciones con datos: no alcanza para ajustar.")

    # --- Ajuste: elegir L por error dejando una estación fuera ---
    mejor = None
    print("\nEscala L (km) | RMSE dejando una fuera (µg/m³)")
    for escala in ESCALAS_KM:
        senal = nucleo(xy_est, xy_comunas, escala) @ total
        rmse = error_dejando_una(senal, obs)
        print(f"{escala:>13.0f} | {rmse:.2f}")
        if mejor is None or rmse < mejor[1]:
            mejor = (escala, rmse)
    escala, rmse = mejor
    senal_est = nucleo(xy_est, xy_comunas, escala) @ total
    fondo, k = ajustar(senal_est, obs)
    rmse_media = float(np.sqrt(np.mean(np.square(
        [obs[np.arange(len(obs)) != i].mean() - obs[i] for i in range(len(obs))]))))
    pred = fondo + k * senal_est
    r2 = 1 - np.sum((obs - pred) ** 2) / np.sum((obs - obs.mean()) ** 2)
    print(f"\nElegido L = {escala:.0f} km | fondo b = {fondo:.1f} µg/m³ | k = {k:.4g}")
    print(f"R² en las estaciones = {r2:.2f} | RMSE dejando una fuera = {rmse:.2f} "
          f"| alternativa simple (media de las otras) = {rmse_media:.2f}")
    if k == 0:
        print("AVISO: k = 0. Las emisiones no explican la diferencia entre estaciones; "
              "los escenarios de abajo no dirán nada.")

    # --- Línea base por comuna y cuánto es propio versus importado ---
    pesos = nucleo(xy_comunas, xy_comunas, escala)

    def concentracion(matriz_emis: np.ndarray) -> np.ndarray:
        return fondo + k * (pesos @ matriz_emis.sum(axis=1))

    base = concentracion(emis)
    propio = k * np.diag(pesos) * total
    aporte = base - fondo
    importado = np.divide(aporte - propio, aporte, out=np.zeros_like(aporte), where=aporte > 0)
    print(f"\nLínea base por comuna: min {base.min():.1f}, max {base.max():.1f} µg/m³")
    print(f"Parte del aporte local que viene de otras comunas: mediana "
          f"{np.median(importado):.0%}, rango {importado.min():.0%} a {importado.max():.0%}")

    # --- Escenarios ---
    i_lena, i_trans, i_ind = (FUENTES.index(f) for f in ("lena", "transporte", "industria"))
    escenarios: dict[str, np.ndarray] = {}

    e = emis.copy()
    e[:, i_lena] *= 0.5
    escenarios["Regional: leña -50 % en toda la región"] = e

    e = emis.copy()
    e[:, i_trans] *= 0.8
    escenarios["Regional: transporte -20 % en toda la región"] = e

    e = emis.copy()
    e *= 0.8
    escenarios["Regional: todas las fuentes -20 %"] = e

    mayor_ind = int(emis[:, i_ind].argmax())
    e = emis.copy()
    e[mayor_ind, i_ind] = 0.0
    escenarios[f"Local: cierra la industria de {comunas[mayor_ind]}"] = e

    mediana = int(np.argsort(total)[len(total) // 2])
    proyecto = 0.02 * float(total.sum())
    e = emis.copy()
    e[mediana, i_ind] += proyecto
    escenarios[f"Local: proyecto nuevo de {proyecto:.0f} t/año en {comunas[mediana]}"] = e

    top5_lena = np.argsort(-emis[:, i_lena])[:5]
    e = emis.copy()
    e[top5_lena, i_lena] = 0.0
    escenarios["Local: sin leña en las 5 comunas que más emiten por leña"] = e

    filas = []
    print("\nEscenario | cambio medio | brecha base -> escenario | Spearman | "
          "comunas que cambian de puesto | mayor salto")
    for nombre, matriz in escenarios.items():
        res = resumen_cambio(base, concentracion(matriz))
        filas.append({"escenario": nombre, **res})
        print(f"{nombre} | {res['cambio_medio']:+.2f} | "
              f"{res['brecha_base']:.2f} -> {res['brecha_escenario']:.2f} | "
              f"{res['spearman']:.3f} | {res['comunas_que_cambian_puesto']} | "
              f"{res['mayor_salto_puestos']}")

    F_SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with F_SALIDA.open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)
    print(f"\nResultados en {F_SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
