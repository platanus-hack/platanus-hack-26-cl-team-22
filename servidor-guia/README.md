# servidor-guia

Intermediario entre el simulador (`viz/`) y la API de Claude. **La clave de la API vive solo aquí**: nunca en la
página ni en una variable `VITE_*`, porque Vite las copia al código que descarga el navegador.

| Ruta | Pedido | Respuesta | Para qué |
|---|---|---|---|
| `POST /interpretar` | `{ caso, perfil, prioridades }` | `{ ajustes, indicadores, no_medido }` | Lee el caso de la persona y propone ajustes de prioridad |
| `POST /guia` | `PedidoGuia` (`viz/src/lib/guia.ts`) | `{ texto }` | Redacta la explicación de las comunas que quedaron primeras |
| `GET /salud` | — | `{ ok, clave }` | Saber si el servidor tiene clave |

## Cómo decide

1. La persona escribe su caso («mi hijo tiene asma») al final de la entrada guiada.
2. Claude (`claude-sonnet-5-5`, esfuerzo bajo, salida estructurada estricta) solo puede devolver valores de un
   **catálogo cerrado** (`viz/src/lib/caso.ts`): una de las tres variables, uno de los cinco grados, indicadores
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
- Hay un límite de 20 llamadas por minuto por dirección (429 si se pasa). CORS no basta, porque solo frena a los
  navegadores. Antes de publicarlo, conviene además ponerlo detrás de un límite del proveedor.
- Las llamadas a Claude esperan como máximo 20 s, con un reintento. Si la página se va (espera 12 a 15 s), la
  llamada se corta para no gastar tokens.
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

Variables del servidor: `ANTHROPIC_API_KEY` (obligatoria para llamar a Claude), `PORT` (8787) y `ORIGENES`
(orígenes permitidos por CORS, separados por coma; por defecto `http://localhost:5173,http://localhost:4173`).

## Privacidad

El caso que escribe la persona sale de la página solo si se configuró `VITE_CASO_URL` o `VITE_GUIA_URL`, y va a
este servidor y de ahí a la API de Claude. No se guarda.

## Pendiente

- Probarlo con la clave real y medir la interpretación con un conjunto de casos de ejemplo antes de publicarlo.
- Desplegarlo (por ejemplo, como servicio web en Render) y fijar `ORIGENES` al dominio del sitio.
