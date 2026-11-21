# Centrales y subestaciones eléctricas en la Región Metropolitana

Descarga realizada el 2026-11-21 con `.venv/bin/python -m datos.energia.fetch_coordinador`.
Fuente: Coordinador Eléctrico Nacional, Infotécnica (https://infotecnica.coordinador.cl),
API pública sin clave `https://api-infotecnica.coordinador.cl/v1/` (no documentada; es la que
usa su sitio web). `manifest.json` guarda URL, fecha y SHA-256.

| Archivo | Filas | Contenido |
|---|---|---|
| `centrales_rm.csv` | 170 | Tipo (solar, hidro, termo), potencia máxima (MW), propietario, inicio de operación, coordenadas |
| `subestaciones_rm.csv` | 150 | Tensión (kV), capacidad (MVA), inicio de operación, coordenadas |

- Potencia instalada en la RM: solar 1.168,6 MW, hidroeléctrica 909,9 MW, termoeléctrica
  520,9 MW. 141 centrales son PMGD (generación distribuida).
- Es una foto del 2026-11-21: solo activos en operación, sin historia ni proyectos en
  construcción.
- 3 centrales solares no traen comuna en la API; quedan con `codigo_comuna` vacío y con sus
  coordenadas (zona de Talagante y Peñaflor).
- Energía Abierta (CNE) se intentó primero y no se pudo descargar: su API no respondió y el
  archivo de capacidad pide inicio de sesión de Microsoft.
