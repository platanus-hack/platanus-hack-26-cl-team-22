# Centrales y subestaciones eléctricas en la Región Metropolitana

Descarga realizada el 2026-11-21 con `.venv/bin/python -m datos.energia.fetch_coordinador`.
Fuente: Coordinador Eléctrico Nacional, Infotécnica (https://infotecnica.coordinador.cl),
API pública sin clave `https://api-infotecnica.coordinador.cl/v1/` (no documentada; es la que
usa su sitio web). `manifest.json` guarda URL, fecha y SHA-256.

| Archivo | Filas | Contenido |
|---|---|---|
| `centrales_rm.csv` | 170 | Tipo (solar, hidro, termo), potencia máxima (MW), propietario, inicio de operación, coordenadas |
| `subestaciones_rm.csv` | 150 | Tensión (kV), capacidad (MVA), inicio de operación, coordenadas |

Ambas tablas traen `fecha_inicio_operacion` tal como la escribe la API y `anio_inicio_operacion`
con el año cuando se puede leer.

- Potencia instalada en la RM: solar 1.168,6 MW, hidroeléctrica 909,9 MW, termoeléctrica
  520,9 MW. 144 centrales son PMGD (generación distribuida): llevan "PMGD" en el nombre.
- Es una foto del 2026-11-21: solo activos en operación, sin historia ni proyectos en
  construcción.
- 3 centrales solares no traen comuna en la API; quedan con `codigo_comuna` vacío y con sus
  coordenadas (zona de Talagante y Peñaflor).
- `tension_kv`: la API la entrega vacía en las 1.278 subestaciones del país. Se completa con la
  mayor tensión escrita en el nombre de sus barras (`/v1/barras/`, por ejemplo
  "BA S/E CENTRAL ALFALFAL 12KV BP1"). Así quedan 132 de 150; las otras 18 no tienen barras con
  tensión en el nombre y quedan vacías.
- `fecha_inicio_operacion` mezcla ocho formatos y texto libre ("2011", "24-09-10",
  "01/01/1997 12:00:00 a.m.", "pendiente"). `anio_inicio_operacion` falta en 7 subestaciones y
  1 central (dice "en pruebas").
- Coordenadas fuera de la RM en filas cuya comuna sí es de la RM son errores de la fuente y se
  dejan vacías: "PMGD PFV EL MONTE AMPLIACIÓN" (estaba en la Antártica) y "PMGD PFV EL RACO"
  (estaba en el Biobío, con comuna Tiltil). Con las que ya venían sin coordenadas, quedan 4
  centrales y 2 subestaciones sin ubicación.
- `comuna` usa los nombres del repo (`data/comunas_rm.csv`): "Tiltil", no "Til-Til".
- Energía Abierta (CNE) se intentó primero y no se pudo descargar: su API no respondió y el
  archivo de capacidad pide inicio de sesión de Microsoft.
