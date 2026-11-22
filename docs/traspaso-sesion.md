# Traspaso de sesión · 21 nov 2026

Estado para retomar el trabajo en otra sesión. Todo lo de abajo está en main.

## Hecho y en main

| PR | Qué |
|---|---|
| #13 | ADR 0001–0005 en `docs/adr/`: shock de la demo (leña del PPDA, Zona A y Zona B), hogares como flujos agregados, municipio simula y ciudadano lee con perfiles, métrica de personas sobre la norma, 52 comunas en el motor y 5 destacadas |
| #22 | Datos reales por comuna RM, cada uno con script, manifiesto (URL, fecha, SHA-256), README y tests: ARClim (`data/arclim`, series por corrida de modelo climático 1970–2069, SSP2-4,5 y SSP5-8,5), DGA (decretos de escasez), Coordinador Eléctrico (centrales y subestaciones), SMA (sancionatorios), SEIA (5.236 proyectos), ChileCompra 2024 (Git LFS). Incluye la corrección de los commits de agy |
| #24 | `servidor-guia` usa `claude-sonnet-5-5` y `max_tokens` 16.000 |
| #27 | Credibilidad municipal de las políticas de seguridad actualizada con la tasa de adjudicación 2024 de ChileCompra (`politicas[].credibilidad_por_comuna`) |
| #30 | `make validate`: cada mecanismo contra «sin cambio» y «tendencia» fuera de muestra. El modelo gana en aire (1,91 contra 2,40 y 4,24), hogares y seguridad a 2 años; pierde en población y seguridad a 1 año. **El patrón de aire entre comunas no está validado** (repartir el mismo cambio da 1,94) |
| #31 | La interfaz muestra la validación unificada de `make validate` |
| #32 | Riesgo climático (`core/clima.py`, `docs/modelo-clima.md`, `odd/tasks/riesgo-climatico.md`): cada réplica sortea una corrida de ARClim y el motor calcula riesgo hídrico, de inundación y de calor por comuna y año (2026-2060), bloque `clima` de `simulacion.json` |
| #33 | ADR 0006: **el usuario principal es el inversionista** (reemplaza al ADR 0003 en ese punto). Justifica el riesgo institucional: es el riesgo de que un proyecto no se apruebe, no una regulación del equipo |

## Pendiente

Ordenado según el ADR 0006 (el producto ordena comunas por el riesgo de invertir en ellas).

1. **Riesgo institucional / permisología** con SEIA y SMA. Cerca de 2.050 de 5.236 proyectos
   del SEIA no llegaron a aprobarse. El SEIA no trae fecha de calificación ni sector, así que
   no se puede medir cuánto demora un permiso. «Desistido» no siempre es fracaso, y una multa
   de la SMA no siempre es firme.
2. **Exposición para el riesgo hídrico.** La prueba contra los decretos de la DGA no pasa:
   AUC 0,61 (p 0,09, no se distingue del azar) contra 0,92 de «fuera de la provincia de
   Santiago». Los decretos parecen seguir a la exposición (comunas rurales, riego).
3. **Interfaz para el inversionista.** La interfaz todavía no lee el bloque `clima`. Los
   perfiles de `tipos_hogar` sirven para elegir dónde vivir, y `servidor-guia` y `caso.ts`
   interpretan casos personales. Si `clima` no se muestra, moverlo a su propio archivo:
   `simulacion.json` pasó de 1,50 a 2,63 MB (gzip 208 → 324 KB).
4. Acoplar los grados-día de calefacción al modelo de aire (cambia salidas ya validadas).
5. `servidor-guia`, mejoras menores: límite de pedidos por IP detrás de un proxy, y tipos del
   SDK en vez de `any` en `ClienteClaude`.

## Cuidados

- **No delegar trabajo a agy.** Sus commits traían datos corruptos (reclamos) y números sin
  fuente. Hay una sesión interactiva de agy abierta en la carpeta del repo que commiteó en una
  rama de trabajo: cerrarla antes de seguir.
- El SEIA responde ráfagas con un desafío anti-bot: el script espera y reintenta, nunca lo evita.
- La tasa de adjudicación de ChileCompra es un **proxy** de capacidad de ejecución, no prueba de
  que un plan se cumpla. Solo el 9 % de las filas de ChileCompra son compras municipales de la RM.
- ARClim no cubre todo: sequía combinada en 9 de 52 comunas, inundación en 41.
- El modo automático de Claude Code bloquea `gh pr merge` hasta que se pide explícitamente.
- `claude doctor`: sin problemas de instalación; la última actualización automática falló
  (reintentar con `claude update`).

## Cómo retomar

```bash
git checkout main && git pull
make test        # 291 pruebas
make simulate    # regenera viz/datos/simulacion.json
make validate    # tabla fuera de muestra y riesgo hídrico contra la DGA
```
