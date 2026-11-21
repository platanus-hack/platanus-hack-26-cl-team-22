---
version: 1
slug: "viz-src-app-tsx"
primary_target: "viz/src/App.tsx"
related_targets: []
---

# Surface brief: pantalla de simulación de root

Scope: `viz/` (pantalla única). Visitor mode: Experience. Se muestra en un televisor o pantalla LED en una sala iluminada, manejada con teclado por quien presenta, unos tres minutos. Solo escritorio 16:9 y 16:10 (1920×1080, 1440×900, 1280×720).

Audience and job: jurado técnico que debe ver que hay una simulación con modelo detrás; equipo municipal que ensaya una medida; persona que elige comuna.

Confirmed with the team (21 nov 2026): los cuatro momentos deben estar disponibles sin acumularse en pantalla; no debe parecer informe público ni sala de control.

Content: `simulacion.json` (contrato en `docs/plan-comunas.md`), polígonos oficiales, y para la vista de leña las emisiones del RETC y la zona A/B de cada comuna. Hoy los datos del modelo son de ejemplo y la pantalla lo dice siempre.

Unresolved: norma de referencia para los cinco niveles (se usa la norma anual de 20 µg/m³ como referencia, por confirmar con el equipo); nombre con o sin mayúscula.

## Direction contract

THESIS: La contaminación proyectada de cada comuna se lee como un aviso público: un nivel, un color y un número con su banda, del mismo modo en que Santiago ya lee sus episodios de aire. Rechaza el tablero de paneles alrededor de un mapa y el mapa 3D inclinado.

OWN-WORLD: Señal vial y aviso de episodio. Fondo blanco de señal, tinta negra, cinco campos planos y saturados (verde, amarillo, naranja, rojo, morado) que ocupan regiones enteras, nunca acentos. Numerales condensados gigantes; texto en la familia de la señalética de carretera. Mapa plano, sin relieve ni sombras. La incertidumbre son franjas diagonales de dos niveles vecinos. Una retícula fija de celdas gobierna todo; bordes rectos, sin esquinas redondeadas ni tarjetas.

STORY: Quien mira entiende en segundos en qué nivel está cada comuna, cree que el número viene de un modelo porque cambia entero cuando se apaga una medida y siempre trae su banda, y recorre cuatro vistas con las teclas 1 a 4.

FIRST VIEWPORT: Tres zonas en la retícula. Izquierda angosta: el nombre root y las cuatro vistas como señales numeradas. Centro: el mapa plano de la región coloreado por nivel, ocupando más de la mitad del ancho. Derecha, un tercio del ancho y toda la altura: el campo, inundado del color del nivel de la comuna elegida, con un numeral de un cuarto de la altura de pantalla y su banda debajo. Abajo, a todo el ancho: los años 2026 a 2036 como una fila de celdas.

SIGNATURE: El corte. Apagar una medida barre toda la pantalla con franjas diagonales y deja el escenario nuevo: mapa, campo y numeral cambian de una vez. Movimiento en cortes y barridos rectos, sin rebotes. Sin uso, la pantalla se demuestra sola.

FORM: Sistema de episodios de aire y señalética vial chilena; candidato 3 de 7 de la lista propia; seed:bd3f94c637e48b8c.

RAISES: un gesto transforma el campo entero (capa de cordón); demostración automática en reposo (arcades); cada vista con tecla y dirección propia (pila de tarjetas); un numeral gigante manda (inicial iluminada); retícula rígida (teletexto).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
