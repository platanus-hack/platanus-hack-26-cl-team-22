# Simulación: los 4 indicadores dentro del índice

Generado con `npm run evaluar -- simular-indicadores` (viz/scripts/simular-indicadores.eval.ts) el 2026-11-22. Sin llamadas al modelo.
Compara, por perfil, el top 5 con las 3 variables simuladas (pesos aprobados antes) contra el índice de 7 variables con 3 activas, en el primer y el último año.
Sequía futura cambia por año (ARClim, ssp245); escasez hídrica, red eléctrica e inversión evaluada son datos fijos.

## Cobertura

- 2026: Sequía futura: 52 comunas, 27 valores distintos; Escasez hídrica: 52 comunas, 9 valores distintos; Red eléctrica: 52 comunas, 39 valores distintos; Inversión evaluada: 52 comunas, 32 valores distintos.
- 2036: Sequía futura: 52 comunas, 23 valores distintos; Escasez hídrica: 52 comunas, 9 valores distintos; Red eléctrica: 52 comunas, 39 valores distintos; Inversión evaluada: 52 comunas, 32 valores distintos.

### Familia con niños

Activos: pm25_anual 10, seguridad 8, crecimiento_poblacion 3.

| Cálculo | Top 5 de menor riesgo |
|---|---|
| 2026, 3 variables (antes) | María Pinto, Alhué, El Monte, San Pedro, Colina |
| 2026, 7 variables | María Pinto, Alhué, El Monte, San Pedro, Colina |
| 2036, 3 variables (antes) | Alhué, María Pinto, San Pedro, El Monte, Colina |
| 2036, 7 variables | Alhué, María Pinto, San Pedro, El Monte, Colina |

### Adulto mayor

Activos: pm25_anual 10, seguridad 8, escasez_hidrica 5.

| Cálculo | Top 5 de menor riesgo |
|---|---|
| 2026, 3 variables (antes) | María Pinto, Alhué, San Pedro, El Monte, Lo Barnechea |
| 2026, 7 variables | El Monte, Peñalolén, María Pinto, Lo Barnechea, Alhué |
| 2036, 3 variables (antes) | Alhué, San Pedro, María Pinto, Lo Barnechea, El Monte |
| 2036, 7 variables | El Monte, Alhué, Peñalolén, Lo Barnechea, María Pinto |

### Joven que arrienda

Activos: pm25_anual 3, seguridad 8, crecimiento_poblacion 5.

| Cálculo | Top 5 de menor riesgo |
|---|---|
| 2026, 3 variables (antes) | María Pinto, Pirque, El Monte, Colina, Peñaflor |
| 2026, 7 variables | María Pinto, Pirque, El Monte, Colina, Peñaflor |
| 2036, 3 variables (antes) | María Pinto, Pirque, El Monte, Isla de Maipo, Alhué |
| 2036, 7 variables | María Pinto, Pirque, El Monte, Isla de Maipo, Alhué |

### Inversionista inmobiliario

Activos: seguridad 5, crecimiento_poblacion 10, inversion_evaluada 8.

| Cálculo | Top 5 de menor riesgo |
|---|---|
| 2026, 3 variables (antes) | Pirque, Colina, María Pinto, Lampa, Paine |
| 2026, 7 variables | Lampa, Colina, Buin, Padre Hurtado, Paine |
| 2036, 3 variables (antes) | Pirque, María Pinto, Colina, Lampa, Paine |
| 2036, 7 variables | Lampa, Colina, Buin, Padre Hurtado, Tiltil |

### Emprendedor o comercio

Activos: seguridad 8, crecimiento_poblacion 10, inversion_evaluada 5.

| Cálculo | Top 5 de menor riesgo |
|---|---|
| 2026, 3 variables (antes) | Pirque, María Pinto, Colina, Paine, El Monte |
| 2026, 7 variables | Lampa, Colina, Pirque, Paine, Padre Hurtado |
| 2036, 3 variables (antes) | Pirque, María Pinto, Colina, Isla de Maipo, Padre Hurtado |
| 2036, 7 variables | Colina, Lampa, Padre Hurtado, Pirque, Paine |

### Empresario joven u oficina

Activos: seguridad 5, crecimiento_poblacion 8, red_electrica 5.

| Cálculo | Top 5 de menor riesgo |
|---|---|
| 2026, 3 variables (antes) | María Pinto, Pirque, Colina, Paine, Lampa |
| 2026, 7 variables | Colina, Buin, Lampa, Paine, Pirque |
| 2036, 3 variables (antes) | María Pinto, Pirque, Colina, Paine, El Monte |
| 2036, 7 variables | Colina, Buin, Tiltil, Lampa, Paine |

### Industria y logística

Activos: seguridad 5, crecimiento_poblacion 8, red_electrica 10.

| Cálculo | Top 5 de menor riesgo |
|---|---|
| 2026, 3 variables (antes) | Pirque, María Pinto, Colina, Paine, Lampa |
| 2026, 7 variables | Buin, Colina, Tiltil, Lampa, Paine |
| 2036, 3 variables (antes) | Pirque, María Pinto, Colina, Paine, Padre Hurtado |
| 2036, 7 variables | Buin, Colina, Tiltil, Lampa, Lo Barnechea |

### Energía

Activos: seguridad 5, crecimiento_poblacion 8, red_electrica 10.

| Cálculo | Top 5 de menor riesgo |
|---|---|
| 2026, 3 variables (antes) | Pirque, María Pinto, Colina, Paine, Lampa |
| 2026, 7 variables | Buin, Colina, Tiltil, Lampa, Paine |
| 2036, 3 variables (antes) | Pirque, María Pinto, Colina, Paine, Padre Hurtado |
| 2036, 7 variables | Buin, Colina, Tiltil, Lampa, Lo Barnechea |

### Evaluación general

Activos: pm25_anual 5, seguridad 5, crecimiento_poblacion 5.

| Cálculo | Top 5 de menor riesgo |
|---|---|
| 2026, 3 variables (antes) | María Pinto, Colina, El Monte, Pirque, Paine |
| 2026, 7 variables | María Pinto, Colina, El Monte, Pirque, Paine |
| 2036, 3 variables (antes) | María Pinto, Colina, Alhué, Pirque, El Monte |
| 2036, 7 variables | María Pinto, Colina, Alhué, Pirque, El Monte |
