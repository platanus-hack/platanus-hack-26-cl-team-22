---
version: 1
slug: "viz-src-app-tsx"
primary_target: "viz/src/App.tsx"
related_targets: []
---

# Surface brief: pantalla de simulación de root

Scope: `viz/` (pantalla única). Visitor mode: Experience. Se muestra en un televisor o pantalla LED en una sala iluminada, manejada con teclado por quien presenta, unos tres minutos. Solo escritorio 16:9 y 16:10 (1920×1080, 1440×900, 1280×720).

Audience and job: jurado técnico que debe ver que hay una simulación con modelo detrás; equipo municipal que ensaya una medida; persona que elige comuna.

Confirmed with the team (21 nov 2026): los cuatro momentos (la cuenca, el plan que falla, la leña, mi comuna) deben estar disponibles sin acumularse en pantalla; no debe parecer informe público ni sala de control. El equipo eligió la dirección «Capas de papel» sobre su boceto (`.impeccable/mocks/decision/challenger-papercut.html`), después de ver también «Episodio» y «Maqueta de la cuenca».

Content: `simulacion.json` (contrato en `docs/plan-comunas.md`), polígonos oficiales y, para la vista de leña, las emisiones del RETC 2023 y la zona A o B de cada comuna. Hoy los datos del modelo son de ejemplo y la pantalla lo dice siempre.

Unresolved: cortes de los cinco niveles de PM2,5 (se usa la norma anual de 20 µg/m³ como referencia, por confirmar); nombre con o sin mayúscula.

## Direction contract

THESIS: Cada política pública es una hoja de papel pegada sobre la región; apagarla es despegarla y ver qué había debajo. La simulación se entiende por lo que se superpone. Rechaza el tablero de paneles alrededor de un mapa y el mapa 3D con sombras.

OWN-WORLD: Recorte de papel en capas. Papel blanco de fondo, tinta negra, papeles de color plano sin mezclar: una familia cálida de cinco pasos para el nivel de contaminación y una familia fría para las políticas. La profundidad sale solo de la superposición de capas recortadas, nunca de degradados. Bordes de tijera, un borde festoneado para la incertidumbre, rótulos gruesos de una sola familia. Reconocible sin contenido: formas recortadas apiladas con un filo de papel blanco entre ellas.

STORY: Quien mira entiende que cada color pegado es una medida, cree en el modelo porque al despegar una hoja cambia lo de abajo y cada número trae su banda, y recorre cuatro hojas con las teclas 1 a 4.

FIRST VIEWPORT: Dos zonas. Izquierda, cinco octavos del ancho: la región como recorte en capas sobre papel blanco, enfocada en el Gran Santiago. Derecha, tres octavos: arriba el nombre root en letras muy gruesas; debajo las políticas como tiras de papel de color levemente giradas; abajo un numeral enorme dentro de un rodel festoneado del color del nivel, con su banda. Al pie, a todo el ancho, los años 2026 a 2036 como pestañas de papel. Las cuatro vistas son pestañas en el borde derecho.

SIGNATURE: Despegar. Apagar una medida levanta su hoja de todas las comunas donde estaba pegada y el color de abajo cambia en el mismo gesto. Cambiar de vista pega una hoja nueva sobre la columna derecha. Todo movimiento es una capa que se asienta o se levanta; sin rebotes ni brillos. Sin uso, la pantalla se demuestra sola.

FORM: Recorte de papel en capas de Lowicz, retador que el equipo eligió sobre la dirección asignada; seed:bd3f94c637e48b8c.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
