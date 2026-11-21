# Proyectos del SEIA en la Región Metropolitana, 1993–2026

Descarga realizada el 2026-11-21 con `.venv/bin/python -m datos.seia.fetch_seia`.
Fuente: Servicio de Evaluación Ambiental (https://seia.sea.gob.cl), endpoint JSON del buscador
de proyectos (`buscarProyectoResumenAction.php`, región 13). `manifest.json` guarda URL,
formulario enviado, fecha y SHA-256 de cada página.

`proyectos_rm.csv`: 5.236 proyectos, uno por fila. Columnas: `expediente_id`, `nombre`,
`tipo_presentacion` (DIA/EIA), `codigos_comuna` (CUT separados por `;`), `comunas`,
`tipologia`, `descripcion_tipologia`, `titular`, `inversion_musd` (millones de USD),
`fecha_presentacion` (ISO), `estado` y `url_ficha`.

| Estado | Proyectos |
|---|---|
| Aprobado | 3.126 |
| Desistido | 1.097 |
| No admitido a tramitación | 646 |
| No calificado | 147 |
| Rechazado | 124 |
| En calificación | 53 |
| Otros (caducado, abandonado, renuncia, revocado) | 43 |

- Inversión total: 145.111 millones de USD (coincide con el total del sitio). 85 proyectos no
  informan inversión.
- 253 proyectos nombran varias comunas; un gasoducto interregional nombra además 28 comunas
  de otras regiones, que quedan en `comunas` sin CUT.
- **No sumar `inversion_musd` por comuna.** Esos 253 proyectos multicomunales (26.605 millones
  de USD, como las líneas 7, 8 y 9 del Metro) llevan la inversión completa en cada fila; sumar
  por comuna los cuenta una vez por cada comuna que nombran.
- **Montos de inversión tal como los declara el titular, sin depurar.** 270 proyectos dicen 0
  y 75 dicen menos de 10.000 USD; en el otro extremo hay montos difíciles de creer, como
  "REGULARIZACIÓN PLANTA CIC S.A." (Maipú, 4.200 millones de USD) o "Nuevo Edificio Clínico"
  (Vitacura, 2.770). Para comparar comunas conviene usar conteos de proyectos o medianas, no
  sumas.
- **No trae fecha de calificación ni sector económico.** La tipología (D.S. 40, art. 3) sirve
  como aproximación del sector.
- El sitio responde ráfagas con un desafío anti-bot. El script no lo evita: pide 100 filas
  cada 10 s y, si llega el desafío, espera un minuto y reintenta (máximo 3 veces).
