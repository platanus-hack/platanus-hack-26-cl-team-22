# Estrategia de Seeding: Catálogo de Santiago y Almacenamiento

## 1. Estructura Inicial del Dataset (Santiago de Chile)

El seed de datos inicial es un **borrador de estimaciones, no datos verificados**: los montos, cuotas y tiempos son orientativos y deben validarse contra la fuente de cada opción antes de usarse. Mientras no se verifique, `last_verified_at` queda en `null`. Solo las restricciones de SIM y de identidad de WOM, Entel y Movistar vienen de las fuentes citadas en `context.md`. Los valores se expresan en Pesos Chilenos (CLP) con su equivalencia de referencia en USD utilizando una tasa fija estimada (`<PLACEHOLDER_USD_CLP_RATE>` = 950 CLP/USD).

### 1.1 Conectividad Móvil (Category: `CONNECTIVITY`)
- **WOM Plan Zero eSIM Prepago:**
  - `id`: `"scl-conn-wom-plan-zero-esim"`
  - `provider`: `"WOM"`
  - `sim_type`: `ESIM`
  - `cost_local_currency`: `<PLACEHOLDER_WOM_PLAN_ZERO_CLP>` (~10.000 CLP)
  - `cost_usd_reference`: ~10.50 USD
  - `data_quota_gb`: 100.0 (promoción prepago)
  - `validity_days`: 30
  - `requires_local_id`: `false` (acepta pasaporte extranjero en flujo web)
  - `setup_time_minutes`: 20
  - `paperwork_level`: 2 (requiere foto de pasaporte y validación de identidad)
  - `physical_presence_required`: `false` (envío de QR por email)
  - `last_verified_at`: `null` (sin verificar)
  - `verification_source_url`: `"https://www.wom.cl/centro-de-ayuda/como-activo-la-esim/"`

- **WOM Chip Prepago Físico:**
  - `id`: `"scl-conn-wom-chip-fisico"`
  - `provider`: `"WOM"`
  - `sim_type`: `PHYSICAL_SIM`
  - `cost_local_currency`: `<PLACEHOLDER_WOM_CHIP_CLP>` (~10.000 CLP con carga inicial)
  - `cost_usd_reference`: ~10.50 USD
  - `data_quota_gb`: 100.0
  - `validity_days`: 30
  - `requires_local_id`: `false`
  - `setup_time_minutes`: 45
  - `paperwork_level`: 1
  - `physical_presence_required`: `true` (sucursal o kiosco)
  - `last_verified_at`: `null` (sin verificar)
  - `verification_source_url`: `"https://www.wom.cl/centro-de-ayuda/como-activar-mi-chip-prepago/"`

- **Entel Chip Prepago Físico:**
  - `id`: `"scl-conn-entel-chip-fisico"`
  - `provider`: `"Entel"`
  - `sim_type`: `PHYSICAL_SIM`
  - `cost_local_currency`: `<PLACEHOLDER_ENTEL_CHIP_CLP>` (~10.000 CLP)
  - `cost_usd_reference`: ~10.50 USD
  - `data_quota_gb`: 15.0
  - `validity_days`: 30
  - `requires_local_id`: `false` (pero sucursales variables rechazan pasaporte)
  - `uncertainty_risk_level`: 2 (riesgo documentado de rechazo en tiendas)
  - `setup_time_minutes`: 60
  - `physical_presence_required`: `true`
  - `last_verified_at`: `null` (sin verificar)
  - `verification_source_url`: `"https://www.traveltomtom.net/destinations/south-america/chile/sim-card-chile"`

- **Airalo eSIM Global (Chile / Sudamérica):**
  - `id`: `"scl-conn-airalo-esim-1gb"`
  - `provider`: `"Airalo"`
  - `sim_type`: `ESIM`
  - `cost_local_currency`: `<PLACEHOLDER_AIRALO_CLP>` (~3.800 CLP)
  - `cost_usd_reference`: 4.00 USD
  - `data_quota_gb`: 1.0
  - `validity_days`: 7
  - `requires_local_id`: `false`
  - `setup_time_minutes`: 5
  - `paperwork_level`: 0
  - `physical_presence_required`: `false`
  - `last_verified_at`: `null` (sin verificar)
  - `verification_source_url`: `null` (URL sin verificar)

---

### 1.2 Transporte desde Aeropuerto (Category: `AIRPORT_TRANSFER`)
- **Autobús Centropuerto / Turbus Aeropuerto:**
  - `id`: `"scl-transfer-centropuerto-bus"`
  - `provider`: `"Centropuerto / Turbus"`
  - `cost_local_currency`: `<PLACEHOLDER_CENTROPUERTO_CLP>` (~2.000 CLP trayecto)
  - `cost_usd_reference`: ~2.10 USD
  - `setup_time_minutes`: 25 (espera de frecuencia y paradas)
  - `physical_presence_required`: `true` (parada exterior aeropuerto)
  - `last_verified_at`: `null` (sin verificar)

- **Taxi Oficial / Transfer Compartido (TransVIP):**
  - `id`: `"scl-transfer-transvip-shared"`
  - `provider`: `"TransVIP"`
  - `cost_local_currency`: `<PLACEHOLDER_TRANSVIP_CLP>` (~10.000 CLP por persona)
  - `cost_usd_reference`: ~10.50 USD
  - `setup_time_minutes`: 15
  - `last_verified_at`: `null` (sin verificar)

- **Uber / Cabify Privado:**
  - `id`: `"scl-transfer-uber-private"`
  - `provider`: `"Uber"`
  - `cost_local_currency`: `<PLACEHOLDER_UBER_AEROPUERTO_CLP>` (~22.000 CLP)
  - `cost_usd_reference`: ~23.00 USD
  - `setup_time_minutes`: 10 (coordinación en estacionamiento techado)
  - `last_verified_at`: `null` (sin verificar)

---

### 1.3 Movilidad Urbana (Category: `URBAN_TRANSIT`)
- **Red Movilidad / Metro de Santiago (Tarjeta bip!):**
  - `id`: `"scl-transit-metro-bip"`
  - `cost_local_currency`: Costo tarjeta `<PLACEHOLDER_BIP_CARD_CLP>` (~1.550 CLP) + pasaje medio `<PLACEHOLDER_METRO_TICKET_CLP>` (~830 CLP/viaje)
  - `paperwork_level`: 0
  - `setup_time_minutes`: 15 (compra física de tarjeta en estación)
  - `last_verified_at`: `null` (sin verificar)

- **Apps de Movilidad (Uber/Cabify diario):**
  - `id`: `"scl-transit-uber-daily"`
  - `cost_local_currency`: `<PLACEHOLDER_UBER_TRIP_CLP>` (~6.000 CLP por viaje medio)
  - `setup_time_minutes`: 5
  - `last_verified_at`: `null` (sin verificar)

---

### 1.4 Escapadas de un Día (Category: `DAY_TRIP`)
- **Bus interurbano a Valparaíso / Viña del Mar (Terminal Pajaritos):**
  - `id`: `"scl-daytrip-bus-valpo"`
  - `provider`: `"Turbus / Pullman"`
  - `cost_local_currency`: `<PLACEHOLDER_BUS_VALPO_CLP>` (~6.000 CLP ida)
  - `cost_usd_reference`: ~6.30 USD
  - `setup_time_minutes`: 30
  - `last_verified_at`: `null` (sin verificar)

- **Tour organizado a Viña/Valparaíso (GetYourGuide / Agencia):**
  - `id`: `"scl-daytrip-tour-valpo"`
  - `provider`: `"Tour Operador Turístico"`
  - `cost_local_currency`: `<PLACEHOLDER_TOUR_VALPO_CLP>` (~45.000 CLP)
  - `cost_usd_reference`: ~47.00 USD
  - `setup_time_minutes`: 5 (reserva web previa)
  - `last_verified_at`: `null` (sin verificar)

---

## 2. Análisis de Trade-offs: Formato de Almacenamiento

| Dimensión | JSON / YAML en Disco | SQLite embebido | PostgreSQL relacional |
|---|---|---|---|
| **Dependencias de Infraestructura** | Cero (archivos en Git) | Cero (librería nativa embebida) | Alta (servidor Docker / Daemon activo) |
| **Consultas y Filtrado Complejo** | Manual en código (map/filter) | SQL estructurado, rápido y tipado | SQL completo, concurrente |
| **Portabilidad y Demos Offline** | Perfecta | Perfecta (archivo único binario) | Mala (depende de host de BD) |
| **Auditoría y Trazabilidad Git** | Difícil si el archivo crece mucho | Binario (requiere export a dump) | Requiere dump SQL |
| **Adecuación al MVP** | Ideal para definición declarativa | **Ideal para motor y repositorio** | Sobredimensionado para MVP |

### Recomendación de Arquitectura de Datos
**Enfoque Híbrido Declarativo-Embebido:**
1. **Definición y Control de Versiones:** El dataset maestro se almacena como fixtures versionados en archivos JSON/YAML dentro de `data/seeds/scl_seed.json` para facilitar diffs legibles en Git y revisión por humanos.
2. **Capa de Persistencia de la Aplicación:** Durante el arranque o build, el repositorio (`SqliteServiceOptionRepository`) hidrata una base SQLite embebida (`travel_simulator.db` o `:memory:` durante tests), aprovechando el filtrado determinista mediante sentencias SQL indexadas.

---

## 3. Proceso de Actualización por Lotes y Frescura

El proyecto descarta de forma categórica el *scraping* en tiempo real para evitar fragilidad en ejecuciones. Toda actualización sigue un flujo por lotes:

```
[ Fuente Primaria / Auditoría ] ──► [ Schema Validator ] ──► [ JSON Seed ] ──► [ DB Hydrator ]
                                             │
                                             ▼
                                  [ last_verified_at ]
```

1. **Protocolo de verificación:** Cada cambio en tarifas o requisitos exige registrar la fecha exacta y la URL de auditoría en `last_verified_at` y `verification_source_url`.
2. **Ciclo de refresco programado:**
   - Servicios de telefonía/conectividad: Revisión trimestral.
   - Transporte y escapadas: Revisión semestral.
   - Tipo de cambio: Parámetro dinámico de entrada en la simulación o actualización diaria de referencia.
3. **Validación de Integridad:** Un script en la capa de Infrastructure valida el JSON contra el esquema TypeScript/Zod antes de actualizar la base de datos de producción o pruebas.

---

## 4. Preguntas abiertas

1. **Frecuencia de desactualización aceptable en demos:** ¿Debe el motor bloquear simulaciones si un registro del seed tiene `last_verified_at` superior a 90 días, o solo emitir una advertencia (*warning*) de frescura?
2. **Disponibilidad estacional:** ¿Cómo estructurar en el seed tarifas de alta temporada (diciembre-febrero) frente a baja temporada en escapadas y transporte interurbano?
3. **Precios en divisas extranjeras directas:** Algunas eSIMs globales cobran en USD y tours cobran en EUR; ¿debe el seed permitir moneda nativa de cobro y convertirla al vuelo a CLP usando el tipo de cambio oficial de la fecha de verificación?
