# Modelo de Datos: Simulador de Viajes (Costos vs. Fricción)

## 1. Visión general y principios

El modelo de datos está diseñado para ser **agnóstico a la ciudad**, permitiendo que Santiago de Chile funcione como el primer *seed* sin acoplar entidades a reglas locales. Toda opción de servicio separa estrictamente el **costo monetario** (normalizado en moneda local y USD) de la **fricción operativa** (tiempo, burocracia, barrera idiomática y esfuerzo físico).

---

## 2. Definición de Entidades

### 2.1 `City`
Representa la ciudad o región destino.
- `id`: `string` (ej. `"scl"`)
- `name`: `string` (ej. `"Santiago"`)
- `country_code`: `string` (ISO 3166-1 alfa-2, ej. `"CL"`)
- `local_currency`: `string` (ISO 4217, ej. `"CLP"`)
- `default_usd_exchange_rate`: `float` (ej. `<PLACEHOLDER_USD_CLP_RATE>` ej. 950.0)
- `last_verified_at`: `string` (ISO 8601 UTC)

### 2.2 `DeviceProfile` (Value Object)
Especificación de conectividad del dispositivo del viajero.
- `supports_physical_sim`: `boolean`
- `supports_esim`: `boolean`

### 2.3 `SimType` (Enum)
- `PHYSICAL_SIM`: Chip plástico extraíble (nano/micro SIM).
- `ESIM`: Perfil digital descargable vía QR / app.
- `NOT_APPLICABLE`: Servicios que no son de conectividad.

### 2.4 `TravelerProfile` (Entidad)
Perfil de entrada para la simulación.
- `id`: `string` (UUID)
- `destination_city_id`: `string` (referencia a `City.id`)
- `trip_duration_days`: `integer` (mínimo 1)
- `has_local_id`: `boolean` (ej. si el viajero posee RUT en Chile)
- `target_data_gb`: `float` (requerimiento total de datos para el viaje)
- `friction_tolerance`: `enum` (`LOW`, `MEDIUM`, `HIGH`) o `float` (0.0 a 1.0)
- `device_profile`: `DeviceProfile`
- `include_day_trips`: `boolean`
- `dining_preference`: `enum` (`BUDGET_LOCAL`, `CASUAL`, `TOURIST`)
- `payment_method_preference`: `enum` (`INTERNATIONAL_CARD`, `CASH`, `MIXED`)

### 2.5 `ServiceCategory` (Enum)
- `CONNECTIVITY`: Planes de datos, eSIMs globales, chips locales.
- `AIRPORT_TRANSFER`: Transporte entre aeropuerto y centro urbano.
- `URBAN_TRANSIT`: Movilidad dentro de la ciudad (metro, buses, apps).
- `DAY_TRIP`: Escapadas o excursiones de un día.
- `DINING`: Alimentación y gastronomía según tier.
- `CURRENCY_EXCHANGE`: Conversión de efectivo y comisiones de tarjeta.

### 2.6 `ServiceOption` (Entidad)
Opción concreta disponible en el catálogo pre-indexado.
- `id`: `string` (identificador único, ej. `"wom-prepago-zero-esim"`)
- `city_id`: `string`
- `category`: `ServiceCategory`
- `provider`: `string` (ej. `"WOM"`, `"Airalo"`, `"Centropuerto"`, `"Metro de Santiago"`)
- `name`: `string` (ej. `"Plan Zero Prepago eSIM"`)
- `cost_local_currency`: `float` (costo nominal en moneda local, ej. `<PLACEHOLDER_CLP_COST>`)
- `cost_usd_reference`: `float` (costo de referencia en USD, ej. `<PLACEHOLDER_USD_COST>`)
- `pricing_model`: `enum` (`ONE_TIME_PACKAGE`, `PER_DAY`, `PER_TRIP`, `VARIABLE_USAGE`)
- `validity_days`: `integer` (duración del paquete, ej. 30 días)
- `data_quota_gb`: `float` (null si no aplica a conectividad)
- `setup_time_minutes`: `integer` (tiempo estimado de adquisición/activación)
- `paperwork_level`: `integer` (escala 0-3: 0=ninguno, 1=email/app, 2=pasaporte/foto, 3=registro estricto/presencial)
- `language_barrier_level`: `integer` (escala 0-2: 0=inglés/app global, 1=español interfaz local, 2=interacción verbal requerida)
- `physical_presence_required`: `boolean` (si exige ir a una tienda física o punto de venta)
- `uncertainty_risk_level`: `integer` (escala 0-2: 0=garantizado, 1=demora posible, 2=riesgo de rechazo a turistas en tienda)
- `requires_local_id`: `boolean` (filtro duro: true si exige RUT chileno o documento nacional)
- `sim_type`: `SimType` (filtro duro para conectividad)
- `is_tourist_friendly`: `boolean`
- `last_verified_at`: `string` (ISO 8601 UTC)
- `verification_source_url`: `string`
- `notes`: `string`

---

## 3. Filtro Duro: `device_profile` y `sim_type`

El motor descarta de forma binaria antes de cualquier scoring toda opción incompatible:

1. **Incompatibilidad SIM Física:**
   Si `ServiceOption.category == CONNECTIVITY` y `ServiceOption.sim_type == PHYSICAL_SIM`:
   `device_profile.supports_physical_sim == false` $\implies$ **RECHAZADO**.
2. **Incompatibilidad eSIM:**
   Si `ServiceOption.category == CONNECTIVITY` and `ServiceOption.sim_type == ESIM`:
   `device_profile.supports_esim == false` $\implies$ **RECHAZADO**.
3. **Incompatibilidad de Identificación:**
   Si `ServiceOption.requires_local_id == true` y `TravelerProfile.has_local_id == false` $\implies$ **RECHAZADO**.

*Efecto de negocio:* Un turista con smartphone solo-eSIM (ej. modelos de EE.UU.) no puede calificar para chips prepago físicos locales, forzando al motor a evaluar eSIM prepago local (ej. WOM) o eSIM de viaje internacional (ej. Airalo).

---

## 4. Normalización de Unidades

Para comparar opciones con diferentes horizontes temporales y paquetes:

### 4.1 Costo total imputado
Para opciones empaquetadas (ej. bolsa de conectividad válida por 30 días):
$$\text{packages\_needed} = \lceil \frac{\text{trip\_duration\_days}}{\text{validity\_days}} \rceil$$
$$\text{total\_cost\_local} = \text{packages\_needed} \times \text{cost\_local\_currency}$$
$$\text{total\_cost\_usd} = \text{packages\_needed} \times \text{cost\_usd\_reference}$$

### 4.2 Costo real por día
$$\text{daily\_cost\_usd} = \frac{\text{total\_cost\_usd}}{\text{trip\_duration\_days}}$$

### 4.3 Costo efectivo por GB
Para opciones de conectividad con cuota $\text{data\_quota\_gb}$:
$$\text{effective\_cost\_per\_gb\_usd} = \frac{\text{total\_cost\_usd}}{\min(\text{target\_data\_gb}, \text{data\_quota\_gb} \times \text{packages\_needed})}$$

---

## 5. Definición y Fórmula de `friction_score`

El `friction_score` cuantifica el estrés, tiempo perdido y sobrecarga operativa del viajero en una escala de **0 a 100** (0 = fricción nula / autoservicio instantáneo, 100 = máxima fricción).

### 5.1 Factores evaluados por opción ($f_i$)
1. **Tiempo de espera/configuración ($S_t$):** $\min(60, \text{setup\_time\_minutes}) / 60 \times 30$ (Máx: 30 pts).
2. **Burocracia y validación ($P_w$):** $(\text{paperwork\_level} / 3) \times 25$ (Máx: 25 pts).
3. **Presencia física obligatoria ($M_p$):** $(1 \text{ si } \text{physical\_presence\_required} \text{ sino } 0) \times 20$ (Máx: 20 pts).
4. **Barrera idiomática ($L_b$):** $(\text{language\_barrier\_level} / 2) \times 15$ (Máx: 15 pts).
5. **Riesgo de rechazo o incertidumbre ($U_r$):** $(\text{uncertainty\_risk\_level} / 2) \times 10$ (Máx: 10 pts).

### 5.2 Fórmula por opción
$$\text{option\_friction\_score} = \min(100, S_t + P_w + M_p + L_b + U_r)$$

### 5.3 Agregación del escenario
Para un escenario compuesto por el conjunto de opciones seleccionadas $O$:
$$\text{scenario\_friction\_score} = \frac{1}{|O|} \sum_{o \in O} \text{option\_friction\_score}(o) + \text{penalty\_handoff}$$
Donde $\text{penalty\_handoff}$ penaliza coordinaciones cruzadas (ej. recargas manuales repetidas en el viaje).

---

## 6. Metadatos de Frescura (`last_verified_at`)

Cada registro en la base de datos debe almacenar:
- `last_verified_at`: Marca temporal ISO 8601 UTC de la última verificación humana o por lote.
- `verification_source_url`: URL oficial o fuente primaria auditada.
- `freshness_status`: Calculado en tiempo de lectura:
  - `FRESH`: verificado hace $\le 60$ días.
  - `STALE`: verificado hace entre 61 y 180 días.
  - `EXPIRED`: verificado hace $> 180$ días (requiere re-verificación obligatoria antes de simulaciones oficiales).

---

## 7. Preguntas abiertas

1. **Prorrateo de remanentes:** Si un chip prepago de 100 GB por 30 días sobra al final de un viaje de 5 días, ¿se imputa el costo de adquisición completo ($100\%$) o se calcula una amortización teórica? (Actualmente se imputa el gasto de bolsillo real).
2. **Variabilidad de sucursales físicas:** En tiendas de telecomunicaciones donde la venta a turistas con pasaporte depende del criterio del vendedor de turno, ¿cómo parametrizar la desviación estándar del `uncertainty_risk_level`?
3. **Tarifas dinámicas en transporte urbano:** El sistema Red/Metro tiene tarifas diferenciadas (Horario Punta, Valle, Bajo); se requiere definir si el modelo usará un promedio ponderado o si solicitará franjas horarias al perfil del viajero.
