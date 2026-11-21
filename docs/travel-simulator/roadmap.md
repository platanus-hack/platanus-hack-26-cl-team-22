# Hoja de Ruta de Implementación (Roadmap) y Arquitectura

## 1. Arquitectura de Capas (Clean Architecture)

El proyecto adopta rigurosamente el patrón de **Clean Architecture** (Arquitectura Limpia) en cuatro capas concéntricas, donde las dependencias siempre apuntan hacia adentro:

```
                  ┌─────────────────────────────────────┐
                  │           Infrastructure            │
                  │  (SQLite, RecordReplayLLMGateway)   │
                  │   ┌─────────────────────────────┐   │
                  │   │     Interface Adapters      │   │
                  │   │    (CLI, Presenters, DTOs)  │   │
                  │   │   ┌─────────────────────┐   │   │
                  │   │   │     Application     │   │   │
                  │   │   │     (Use Cases)     │   │   │
                  │   │   │   ┌─────────────┐   │   │   │
                  │   │   │   │   Domain    │   │   │   │
                  │   │   │   │  (Entities) │   │   │   │
                  │   │   │   └─────────────┘   │   │   │
                  │   │   └─────────────────────┘   │   │
                  │   └─────────────────────────────┘   │
                  └─────────────────────────────────────┘
```

### 1.1 Capa Domain (`src/domain/`)
Núcleo del negocio sin ninguna dependencia externa, frameworks o librerías de infraestructura:
- **Entidades y Value Objects:**
  - `TravelerProfile`, `DeviceProfile`, `SimType`
  - `ServiceOption`, `ServiceCategory`
  - `SimulationScenario`, `ScenarioType` (`ZERO_FRICTION`, `BALANCED`, `LOCAL_OPTIMIZED`)
  - `FrictionScore`, `Money`
- **Servicios de Dominio:**
  - `ScenarioCalculationEngine`: Implementación pura de fórmulas de normalización, costos y friction score.
- **Puertos de Dominio (Interfaces):**
  - `IServiceOptionRepository`: Contrato de persistencia (`findByCityAndCategory`, `findEligibleOptions`).
  - `IAIAuditGateway`: Contrato para consultar y obtener recomendaciones de asistentes de IA.

### 1.2 Capa Application (`src/application/`)
Orquesta las operaciones de negocio y casos de uso:
- **Casos de Uso (`src/application/use-cases/`):**
  - `RunSimulationUseCase`: Recibe `SimulationRequestDto`, aplica filtros duros, construye los 3 escenarios y devuelve `SimulationResultDto`.
  - `AuditAIAssistantsUseCase`: Ejecuta el perfil en el gateway de IA, parsea respuestas, evalúa sobrecosto y emite el reporte de auditoría.
- **DTOs (`src/application/dtos/`):**
  - `SimulationRequestDto`, `SimulationResultDto`, `AIAuditReportDto`.

### 1.3 Capa Interface Adapters (`src/adapters/`)
Conecta el mundo exterior con los casos de uso:
- **Controladores / CLI Handlers:**
  - `SimulationCliController`: Parsea argumentos de línea de comandos y los entrega a `RunSimulationUseCase`.
- **Presenters / Formatters:**
  - `ConsoleSimulationPresenter`: Formatea tablas comparativas en terminal (USD, CLP, Fricción).
  - `JsonSimulationPresenter`: Serializa resultados estructurados para exportación o visualización.

### 1.4 Capa Infrastructure (`src/infrastructure/`)
Implementación concreta de puertos y herramientas:
- **Persistencia:**
  - `SqliteServiceOptionRepository`: Implementación sobre SQLite embebido.
  - `JsonFileSeedLoader`: Carga de fixtures declarativos en memoria/disco.
- **AI Gateway & Tooling:**
  - `RecordReplayLLMGateway` (`core/llm_gateway.py`): Implementa `IAIAuditGateway` con soporte para reproducir trazas cacheadas sin conexión a internet.
  - Clientes oficiales de LLMs para el modo de captura (`AnthropicClient`, etc.).

---

## 2. Plan de Implementación por Fases (MVP Step-by-Step)

El desarrollo sigue una secuencia estricta: **motor determinista y dataset de prueba primero, interfaz de usuario al final**.

```
Fase 1: Dominio Puro ──► Fase 2: Dataset y Repo ──► Fase 3: Motor y Escenarios
                                                                   │
                                                                   ▼
Fase 6: UI Mínima    ◄── Fase 5: CLI y Tests    ◄── Fase 4: Auditoría IA
```

### Fase 1: Núcleo de Dominio y Contratos
- **Objetivo:** Modelar entidades base, value objects y reglas de cálculo en TypeScript/Python sin dependencias.
- **Entregables:**
  - Clases `TravelerProfile`, `ServiceOption`, `FrictionScore`.
  - Lógica pura de `friction_score` y normalización de costos por día y por GB.
  - Pruebas unitarias de dominio con cobertura 100% en fórmulas matemáticas.

### Fase 2: Dataset de Pruebas y Repositorio de Seeding
- **Objetivo:** Cargar el catálogo validado de Santiago de Chile en un repositorio determinista.
- **Entregables:**
  - Archivo maestro `data/seeds/santiago_seed.json` con las opciones de conectividad, transporte y escapadas.
  - Implementación de `SqliteServiceOptionRepository` o `InMemoryServiceOptionRepository`.
  - Test de carga y validación de tipos e integridad de datos.

### Fase 3: Motor Determinista y Generador de Escenarios
- **Objetivo:** Implementar los casos de uso de simulación y las reglas de optimización de escenarios.
- **Entregables:**
  - Filtros duros: hardware SIM (`device_profile`), requerimiento de RUT y métodos de pago.
  - Algoritmo de resolución para los tres escenarios (`Cero Fricción`, `Balanceado`, `Optimizado Local`).
  - Pruebas de integración comprobando que un dispositivo solo-eSIM descarta correctamente chips físicos.

### Fase 4: Pipeline de Auditoría de Asistentes de IA
- **Objetivo:** Construir el extractor de recomendaciones de LLM y el conector Record/Replay.
- **Entregables:**
  - Prompts estandarizados para asistentes de viaje.
  - Parser determinista de recomendaciones a IDs de catálogo.
  - Adaptador `RecordReplayLLMGateway` con fixtures grabados para demostración offline.
  - Caso de uso `AuditAIAssistantsUseCase` calculando el índice de sobrecosto y sesgo de afiliados.

### Fase 5: Harness CLI y Pruebas End-to-End
- **Objetivo:** Ejecutar simulaciones completas desde terminal para validar el modelo y generar reportes.
- **Entregables:**
  - Comando CLI `travel-sim run --duration=7 --esim-only --budget=balanced`.
  - Comando CLI `travel-sim audit --profile=standard_tourist`.
  - Suite de pruebas de regresión deterministas.

### Fase 6: Capa de Presentación / UI
- **Objetivo:** Visualización gráfica e interactiva para la presentación del proyecto.
- **Entregables:**
  - Panel comparativo visual (Web dashboard ligero o Terminal UI interactivo).
  - Selector de dispositivos móviles, control deslizante de días de viaje y visualización de gráficos de ahorro vs fricción.

---

## 3. Preguntas abiertas

1. **Lenguaje principal del backend:** ¿Se implementará en Python (para aprovechar directamente `core/llm_gateway.py` existente) o en TypeScript/Node (para interoperar con el stack web moderno)?
2. **Formato de la UI final:** ¿Será una aplicación web completa (Next.js / Vite) o una interfaz de terminal interactiva (TUI con Rich/Textual o Bubbletea) para priorizar el desarrollo del motor?
3. **Mecanismo de fallback en el parser de IA:** Si un LLM inventa una opción de transporte inexistente (ej. "Metro directo desde el aeropuerto a Bellavista"), ¿cómo clasifica el motor la anomalía en el reporte de auditoría?
