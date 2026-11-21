# Especificación del Motor: Reglas, Escenarios y Auditoría de IA

## 1. Visión general del motor

El motor de simulación opera de forma **estrictamente determinista**, sin dependencias de modelos de lenguaje en su núcleo de cálculo. Dada una entrada de perfil de viajero y un catálogo de opciones pre-indexado, el motor ejecuta filtros booleanos (filtros duros), optimiza combinaciones según funciones objetivo discretas (filtros blandos) y proyecta tres escenarios comparativos.

---

## 2. Reglas de Filtrado

### 2.1 Filtros Duros (Hard Filters)
Excluyen opciones que son física, legal o técnicamente inviables para el viajero antes de iniciar la optimización:

1. **Restricción de hardware SIM:**
   - Si `option.category == CONNECTIVITY`:
     - Si `option.sim_type == PHYSICAL_SIM` y `traveler.device_profile.supports_physical_sim == false` $\implies$ **Descartar**.
     - Si `option.sim_type == ESIM` y `traveler.device_profile.supports_esim == false` $\implies$ **Descartar**.
2. **Restricción de documento nacional (RUT):**
   - Si `option.requires_local_id == true` y `traveler.has_local_id == false` $\implies$ **Descartar**.
3. **Restricción de método de pago:**
   - Si el viajero seleccionó `payment_method_preference == CASH_ONLY` y la opción exige tarjeta de crédito internacional (ej. apps de transporte sin cobro en efectivo habilitado) $\implies$ **Descartar**.
4. **Cumplimiento de cuota mínima de datos:**
   - Las opciones de conectividad cuya cuota total en el período sea menor a `traveler.target_data_gb` deben ser combinadas o multiplicadas en paquetes sucesivos; si el proveedor no permite recarga o acumulación $\implies$ **Descartar**.

### 2.2 Filtros Blandos y Scoring (Soft Filters)
Ponderan las opciones supervivientes para cada categoría según el objetivo del escenario:
- **Criterio Monetario ($C$):** Costo total normalizado en USD.
- **Criterio de Fricción ($F$):** `option_friction_score` calculado según la fórmula del modelo de datos.
- **Criterio de Tiempo Extra ($T$):** Minutos adicionales requeridos frente a la opción de mínima fricción.

---

## 3. Algoritmo de Construcción de Escenarios

Para cada categoría requerida en el viaje ($k \in \{\text{Conectividad, Aeropuerto, Tránsito, Escapadas, Comida, Divisas}\}$):

```
                   [ Opciones del Catálogo por Categoría ]
                                      │
                                      ▼
                           [ Filtros Duros ]
                                      │
               ┌──────────────────────┼──────────────────────┐
               ▼                      ▼                      ▼
      [ Cero Fricción ]         [ Balanceado ]       [ Optimizado Local ]
      Minimiza Fricción       Trade-off Dinámico        Minimiza Costo
```

### 3.1 Escenario 1: Cero Fricción (Zero Friction)
- **Objetivo:** Minimizar el esfuerzo cognitivo, el tiempo de espera y el riesgo de interacción.
- **Selección:** Para cada categoría $k$, seleccionar la opción $o_k^*$ tal que:
  $$o_k^* = \arg\min_{o \in \text{Validas}_k} \left( \text{friction\_score}(o) \times 1000 + \text{cost\_usd}(o) \right)$$
- **Perfil de selección esperado en Santiago:**
  - *Conectividad:* eSIM de viaje internacional (ej. Airalo/Holafly instalada antes de salir).
  - *Aeropuerto:* Transfer privado prepagado o Uber reservado con tarjeta de crédito.
  - *Tránsito urbano:* Apps de transporte privado (Uber/Cabify) sin interacción con transporte público en hora punta.
  - *Escapadas:* Tour organizado guiado con recogida en el hotel.
  - *Comida:* Restaurantes turísticos y casuales con menú en inglés y tarjeta de crédito.
  - *Divisas:* Pago íntegro con tarjeta de crédito internacional (asumiendo spread del banco emisor).

### 3.2 Escenario 2: Optimizado Local (Local Optimized)
- **Objetivo:** Minimizar el gasto total de bolsillo en USD/CLP, asumiendo la fricción operativa que sea necesaria siempre que supere los filtros duros.
- **Selección:** Para cada categoría $k$, seleccionar la opción $o_k^*$ tal que:
  $$o_k^* = \arg\min_{o \in \text{Validas}_k} \left( \text{cost\_usd}(o) \times 1000 + \text{friction\_score}(o) \right)$$
- **Perfil de selección esperado en Santiago:**
  - *Conectividad:* Chip prepago local (WOM Plan Zero eSIM si el teléfono lo soporta, o chip físico comprado y registrado en sucursal).
  - *Aeropuerto:* Autobús público Centropuerto o Turbus hasta estación de metro Pajaritos o Los Héroes.
  - *Tránsito urbano:* Red bip! (Metro de Santiago + buses urbanos).
  - *Escapadas:* Autobús interurbano de línea regular desde terminal de buses (ej. Turbus / Pullman Bus).
  - *Comida:* Menús del día / picadas tradicionales locales.
  - *Divisas:* Retiro en cajeros locales sin comisión fija o cambio de efectivo en casas de cambio del centro (calle Agustinas).

### 3.3 Escenario 3: Balanceado (Balanced)
- **Objetivo:** Maximizar el retorno por cada punto de fricción añadido frente a Cero Fricción.
- **Regla de sustitución:** Parte del Escenario Cero Fricción y evalúa categoría por categoría si cambiar a la opción local genera un ahorro significativo con un costo de fricción aceptable:
  - Se define el umbral de eficiencia marginal $\theta = \text{US\$ } 0.75 \text{ por punto de fricción}$ (configurable según `traveler.friction_tolerance`).
  - Para una categoría $k$, si:
    $$\frac{\text{cost\_usd}(o_{\text{cero}}) - \text{cost\_usd}(o_{\text{local}})}{\text{friction\_score}(o_{\text{local}}) - \text{friction\_score}(o_{\text{cero}})} \ge \theta$$
    y $\text{friction\_score}(o_{\text{local}}) \le \text{umbral\_max\_friccion}$ (ej. 50 pts):
    $\implies$ Se adopta la opción local o intermedia; de lo contrario, se mantiene la opción cero fricción.

---

## 4. Cálculo de Ahorro y Trade-off

Para cada escenario evaluado $E \in \{\text{Balanceado}, \text{Optimizado Local}\}$ frente a $E_{\text{cero}}$:

### 4.1 Ahorro Monetario Absoluto y Porcentual
$$\Delta \text{Cost}_{\text{USD}} = \text{Cost}_{\text{USD}}(E_{\text{cero}}) - \text{Cost}_{\text{USD}}(E)$$
$$\Delta \text{Cost}_{\text{CLP}} = \text{Cost}_{\text{CLP}}(E_{\text{cero}}) - \text{Cost}_{\text{CLP}}(E)$$
$$\% \text{ Ahorro} = \frac{\Delta \text{Cost}_{\text{USD}}}{\text{Cost}_{\text{USD}}(E_{\text{cero}})} \times 100$$

### 4.2 Incremento de Fricción y Ratio de Eficiencia
$$\Delta \text{Friction} = \text{FrictionScore}(E) - \text{FrictionScore}(E_{\text{cero}})$$
$$\text{Efficiency Ratio} = \frac{\Delta \text{Cost}_{\text{USD}}}{\max(1, \Delta \text{Friction})} \quad (\text{USD ahorrados por unidad de fricción extra})$$

---

## 5. Pipeline de Auditoría de Asistentes de IA

Este pipeline permite medir empíricamente el sesgo y sobrecosto de las recomendaciones generadas por LLMs comerciales (Claude, ChatGPT, Gemini, etc.).

```
[ TravelerProfile ] ──► [ Prompt Estandarizado ] ──► [ LLM Gateway (Record/Replay) ]
                                                              │
                                                              ▼
                                                   [ Parser Estructurado ]
                                                              │
                                                              ▼
                                                  [ Mapeo a ServiceOptions ]
                                                              │
                                                              ▼
                                                  [ Motor Determinista ]
                                                              │
                                                              ▼
                                               [ Métrica: AI Tourist Overcharge ]
```

### 5.1 Especificación del Prompt
Se envía un prompt sin mención de marcas comerciales de afiliados, fijando el perfil del viajero (días, falta de RUT, capacidades de su teléfono y presupuesto).

### 5.2 Mapeo y Normalización Determinista
El módulo extractor parsea la respuesta no estructurada del LLM y la mapea contra el catálogo de `ServiceOption.id`:
- Si recomienda "Airalo / Holafly" $\implies$ asigna la opción correspondiente de eSIM global.
- Si recomienda "Comprar chip prepago en el aeropuerto" $\implies$ valida si existe stock verificable en el catálogo o penaliza por recomendación de alta fricción/falsa disponibilidad.
- Si no es clasificable $\implies$ asigna flag `UNMAPPED_RECOMMENDATION` con costo promedio de la categoría.

### 5.3 Métricas de Evaluación del Asistente
1. **Índice de Sobrecosto Turístico (Tourist Overcharge Gap):**
   $$\text{Overcharge}_{\text{LLM vs Local}} = \frac{\text{Cost}_{\text{USD}}(\text{LLM}) - \text{Cost}_{\text{USD}}(E_{\text{local}})}{\text{Cost}_{\text{USD}}(E_{\text{local}})} \times 100$$
2. **Sesgo de Afiliado (Affiliate Bias Score):** Proporción de categorías donde el LLM prioriza proveedores con programas de comisiones agresivos frente al óptimo local equivalente.
3. **Viabilidad Técnica:** Porcentaje de recomendaciones que violan los filtros duros (ej. recomendar chip físico a un usuario con teléfono solo-eSIM).

### 5.4 Aislamiento y Reproducibilidad (`core/llm_gateway.py`)
- El pipeline implementa el patrón **Record/Replay**.
- Durante las pruebas y demostraciones en vivo, las llamadas a APIs de LLM se leen desde grabaciones serializadas en disco (fixtures JSON), eliminando latencia, cuotas de red y respuestas no deterministas durante la evaluación del hackathon.

---

## 6. Preguntas abiertas

1. **Gestión de recomendaciones ambiguas:** ¿Cómo debe puntuar el motor cuando un asistente recomienda opciones genéricas (ej. "toma un taxi o un bus") sin elegir una? (Propuesta: evaluar el escenario promedio de las opciones mencionadas).
2. **Ponderación del tiempo de viaje vs dinero:** ¿Debe incluirse el costo de oportunidad del tiempo ($\text{USD}/\text{hora}$) como parte del costo directo o debe mantenerse estrictamente como parte del `friction_score`?
3. **Tamaño de muestra de réplicas de IA:** Definir cuántas ejecuciones independientes por modelo ($N=3, 5, 10$) se requieren para calcular intervalos de confianza válidos en el track de simulaciones.
