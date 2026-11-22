# servidor-guia

Intermediario entre el simulador (`viz/`) y la API de Claude. **La clave de la API vive solo aquí**: nunca en la
página ni en una variable `VITE_*`, porque Vite las copia al código que descarga el navegador.

| Ruta | Pedido | Respuesta | Para qué |
|---|---|---|---|
| `POST /interpretar` | `{ caso, perfil, prioridades }` | `{ perfil, ajustes, indicadores, no_medido }` | Lee el caso y propone ajustes de prioridad, sin hacer preguntas: el propósito y lo demás los infiere del caso y del perfil. Elige además uno de los nueve perfiles (`PERFILES`), que fija los pesos de partida. En comercio, industria y energía no sube el aire |
| `POST /guia` | `PedidoGuia` (`viz/src/lib/guia.ts`) | `{ texto }` | Redacta la explicación de las comunas que quedaron primeras |
| `GET /salud` | — | `{ ok, clave, ip, proxies, cadena, directa }` | Saber si hay clave y cómo ve el límite a quien consulta (`cadena` es `X-Forwarded-For` tal como llegó) |

## Cómo decide

1. La persona escribe su caso («mi hijo tiene asma») al final de la entrada guiada.
2. Claude (`claude-sonnet-5-5`, esfuerzo bajo, salida estructurada estricta) solo puede devolver valores de un
   **catálogo cerrado** (`viz/src/lib/caso.ts`): una de las siete variables, uno de los cinco grados, indicadores
   y temas no medidos de una lista fija. Cada ajuste trae la frase del caso que lo justifica.
3. El servidor y la página descartan todo lo que no está en el catálogo y todo ajuste cuya frase **no aparece en
   el caso**, para que el modelo no invente motivos.
4. El índice de riesgo ordena las comunas con las prioridades ajustadas, igual que siempre. Claude nunca escribe
   números sobre comunas.
5. La persona ve cada ajuste («Aire: Clave») y puede apagarlo; el orden se recalcula al instante.

Si no hay clave, el modelo rechaza la consulta o algo falla, la página sigue sin ajustes y con su explicación propia.

Protecciones del servidor:
- Cada pedido se valida antes de llamar a Claude (`/interpretar` y `/guia`). Uno inválido responde 400 sin gastar
  la clave; uno de más de 8 KB responde 413.
- Respuestas en memoria: un pedido idéntico a uno ya respondido (los ejemplos, una recarga) sale de la memoria
  por 6 horas sin llamar a Claude y sin contar para el límite. Pedidos idénticos simultáneos comparten una sola
  llamada. Los fallos no se guardan.
- Hay un límite de 20 llamadas por minuto por dirección (429 si se pasa). Detrás de un proxy (Render) la dirección
  sale de `X-Forwarded-For` según `PROXIES_CONFIABLES` (saltos de proxy confiables; 0 = la conexión directa). Si
  está mal, todos comparten un límite: `GET /salud` debe mostrar tu propia dirección en `ip`. CORS no basta, porque solo frena a los
  navegadores. Antes de publicarlo, conviene además ponerlo detrás de un límite del proveedor.
- Las llamadas a Claude esperan como máximo 20 s, con un reintento. Si la página se va (espera 12 a 15 s), la
  llamada se corta para no gastar tokens.
- Tope global diario (`TOPE_DIARIO`, llamadas a Claude por día UTC para todo el servicio; 0 = sin tope): al
  pasarlo responde 429 y la página sigue sin IA. El límite por dirección no frena a quien usa muchas direcciones.
  Las respuestas en memoria siguen saliendo aunque se haya agotado el cupo.
- El caso va entre comillas triples; tres o más comillas dentro del texto se reducen a una, para que nadie pueda
  cerrar ese bloque y escribir instrucciones.
- Cada llamada deja una línea de log con sus tokens (`entrada`, `salida`, `cache_leida`, `cache_escrita`), sin el
  texto de la persona, para medir el costo real antes de tocar el esfuerzo o el modelo.
Ante un rechazo por política, la API reintenta sola con un modelo de respaldo (`fallbacks: "default"`).

## Cómo correrlo

Necesita Node 23.6 o más (ejecuta TypeScript sin compilar).

```bash
cd servidor-guia
npm install
ANTHROPIC_API_KEY=... npm start          # http://localhost:8787
npm test                                 # pruebas con un Claude simulado, sin clave
```

En otra terminal, el simulador apuntando al servidor:

```bash
cd viz
VITE_CASO_URL=http://localhost:8787/interpretar VITE_GUIA_URL=http://localhost:8787/guia npm run dev
```

Variables del servidor:

| Variable | Por defecto | Para qué |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Obligatoria para llamar a Claude |
| `PORT` | `8787` | Puerto |
| `ORIGENES` | `http://localhost:5173,http://localhost:4173` | Orígenes permitidos por CORS, separados por coma |
| `PROXIES_CONFIABLES` | `0` | Saltos de proxy delante del servicio, para leer la IP de cada visitante (ver «Operación») |
| `TOPE_DIARIO` | `0` (sin tope) | Llamadas a Claude por día UTC para todo el servicio |

## Privacidad

El caso que escribe la persona sale de la página solo si se configuró `VITE_CASO_URL` o `VITE_GUIA_URL`, y va a
este servidor y de ahí a la API de Claude. No se escribe en disco ni en los logs (el log de cada llamada solo trae
contadores de tokens). Sí queda **en la memoria del proceso hasta 6 horas**, como parte de la caché de respuestas,
y se borra al reiniciar o desplegar.

## Operación

### Fijar `PROXIES_CONFIABLES` (después de cada cambio de infraestructura)

La documentación de Render dice que su balanceador (con Cloudflare delante) reenvía los pedidos al servicio, pero
no dice cuántas entradas agrega a `X-Forwarded-For`. Por eso se fija con evidencia, no a ojo:

1. Averigua tu IP pública (por ejemplo, `curl https://ifconfig.me`).
2. Consulta el servicio con una entrada falsa al inicio:
   `curl -H 'X-Forwarded-For: 1.2.3.4' https://<servicio>/salud`
3. En `cadena`, ubica tu IP. `PROXIES_CONFIABLES` = cuántas entradas hay desde tu IP hasta el final, contándola
   (si es la última, 1; si es la penúltima, 2). `1.2.3.4` nunca debe salir en `ip`.
4. Si tu IP no aparece en `cadena`, Render no la está pasando por esa cabecera: deja `0` y avisa, porque entonces
   todos los visitantes comparten un solo límite.

Un valor mal puesto nunca deja esquivar el límite: en el peor caso varios visitantes comparten uno.

### Dimensionar `TOPE_DIARIO`

Cada caso nuevo cuesta hasta 2 llamadas (lectura del caso y guía); lo que sale
de la caché no cuenta. Con el costo real por llamada (sale de los logs, abajo):
`TOPE_DIARIO ≈ presupuesto diario / costo por llamada`. `render.yaml` parte en 1000.

### Leer el costo real

Cada llamada deja una línea JSON: `{"llamada":"interpretar","stop":"end_turn","entrada":…,"salida":…,"cache_leida":…,"cache_escrita":…}`.
En Render, filtra los logs por `"llamada"`. `salida` incluye los tokens de razonamiento, que en una clasificación
suelen ser la mayor parte del costo.

### Estado en memoria

La caché, el límite por dirección y el tope diario viven en la memoria del proceso: se reinician al desplegar y no
se comparten entre instancias. Con más de una instancia, cada una tiene su propio tope (el gasto máximo se
multiplica). Para varias instancias habría que llevarlos a un almacén compartido (por ejemplo, Redis).

## Pendiente

- Medir con la clave real un conjunto de casos de ejemplo (una evaluación mínima: caso → ajustes
  esperados) antes de cambiar modelo o esfuerzo.
- **Bajar el costo del razonamiento**, solo con esa evaluación en mano y unos días de logs:
  - `thinking: { type: 'between_tools' }` en `/interpretar` (en Sonnet 5.5 apaga el razonamiento; acepta esfuerzo
    `high` o menor).
  - O pasar `/interpretar` a `claude-haiku-5-5`, mucho más barato; la salida estructurada y el catálogo cerrado
    limitan el daño si clasifica peor.
  - La caché de prompts de la API no ayuda hoy: las instrucciones (unos 300 tokens) no llegan al mínimo cacheable
    de Sonnet 5.5 (512), y no conviene inflarlas para alcanzarlo.
- Autenticación: las rutas son públicas. Las protegen la validación, el límite por dirección, el tope diario y
  CORS (que solo frena navegadores). Si el tope se agota por abuso, el siguiente paso es un token por sesión o un
  desafío como Turnstile.
