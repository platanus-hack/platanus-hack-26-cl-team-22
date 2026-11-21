#!/usr/bin/env node
/**
 * Descarga el paquete de mapas para presentar sin internet: calles (OpenFreeMap), relieve (Mapterhorn),
 * tipografías e íconos, solo para la Región Metropolitana. Queda en viz/public/mapas (fuera de git).
 *
 *   npm run mapas
 *
 * Se puede repetir: salta lo que ya está. La pantalla lo usa sola si no hay red, o con ?mapa=local.
 */
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const AQUI = path.dirname(fileURLToPath(import.meta.url))
const SALIDA = path.resolve(AQUI, '../public/mapas')
const ESTILO = 'https://tiles.openfreemap.org/styles/positron'
const RELIEVE = 'https://tiles.mapterhorn.com/tilejson.json'
/** Región Metropolitana con holgura, para que la vista inclinada tenga horizonte: [lonMin, latMin, lonMax, latMax] */
const LIMITES = [-72.3, -34.8, -69.3, -32.5]
const ZOOM_CALLES = 12
const ZOOM_RELIEVE = 11
const RANGOS = ['0-255', '256-511', '8192-8447']
const EN_PARALELO = 8
const BASE = '__BASE__'

function teselas(z) {
  const n = 2 ** z
  const tx = (lon) => Math.min(n - 1, Math.max(0, Math.floor(((lon + 180) / 360) * n)))
  const ty = (lat) => {
    const r = (lat * Math.PI) / 180
    return Math.min(n - 1, Math.max(0, Math.floor(((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * n)))
  }
  const out = []
  for (let x = tx(LIMITES[0]); x <= tx(LIMITES[2]); x++) for (let y = ty(LIMITES[3]); y <= ty(LIMITES[1]); y++) out.push({ z, x, y })
  return out
}

const cuenta = { nuevas: 0, saltadas: 0, vacias: 0, fallas: 0, bytes: 0 }

async function bajar(url, destino) {
  try {
    const s = await fs.stat(destino)
    if (s.size > 0) {
      cuenta.saltadas++
      cuenta.bytes += s.size
      return
    }
  } catch {
    /* no existe todavía */
  }
  for (let intento = 0; intento < 3; intento++) {
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(30_000) })
      if (r.status === 404 || r.status === 204) {
        cuenta.vacias++ // sin datos en esa tesela (mar, fuera de cobertura)
        return
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const b = Buffer.from(await r.arrayBuffer())
      await fs.mkdir(path.dirname(destino), { recursive: true })
      await fs.writeFile(destino, b)
      cuenta.nuevas++
      cuenta.bytes += b.length
      return
    } catch (e) {
      if (intento === 2) {
        cuenta.fallas++
        console.warn(`  no se pudo bajar ${url}: ${e.message}`)
      } else await new Promise((ok) => setTimeout(ok, 800 * (intento + 1)))
    }
  }
}

async function enTandas(tareas) {
  let i = 0
  const total = tareas.length
  await Promise.all(
    Array.from({ length: EN_PARALELO }, async () => {
      while (i < total) {
        const n = i++
        await tareas[n]()
        if ((n + 1) % 200 === 0) console.log(`  ${n + 1} de ${total}`)
      }
    }),
  )
}

const json = async (url) => {
  const r = await fetch(url, { signal: AbortSignal.timeout(30_000) })
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`)
  return r.json()
}

const estilo = await json(ESTILO)
const calles = await json(estilo.sources.openmaptiles.url)
const relieve = await json(RELIEVE)
const urlCalles = calles.tiles[0]
const urlRelieve = relieve.tiles[0]
const ext = urlRelieve.split('.').pop().split('?')[0]
const tareas = []

for (let z = 0; z <= ZOOM_CALLES; z++)
  for (const t of teselas(z))
    tareas.push(() => bajar(urlCalles.replace('{z}', t.z).replace('{x}', t.x).replace('{y}', t.y), path.join(SALIDA, 'calles', `${t.z}`, `${t.x}`, `${t.y}.pbf`)))
for (let z = 0; z <= ZOOM_RELIEVE; z++)
  for (const t of teselas(z))
    tareas.push(() => bajar(urlRelieve.replace('{z}', t.z).replace('{x}', t.x).replace('{y}', t.y), path.join(SALIDA, 'relieve', `${t.z}`, `${t.x}`, `${t.y}.${ext}`)))

const fuentes = new Set(['Noto Sans Bold'])
for (const l of estilo.layers) for (const f of l.layout?.['text-font'] ?? []) if (typeof f === 'string') fuentes.add(f)
for (const f of fuentes) {
  if (!/^[\w ]+$/.test(f)) continue // solo nombres simples: van a una ruta de disco
  for (const r of RANGOS)
    tareas.push(() => bajar(estilo.glyphs.replace('{fontstack}', encodeURIComponent(f)).replace('{range}', r), path.join(SALIDA, 'fuentes', f, `${r}.pbf`)))
}
for (const s of ['.json', '.png', '@2x.json', '@2x.png']) tareas.push(() => bajar(estilo.sprite + s, path.join(SALIDA, 'iconos', `ofm${s}`)))

console.log(`Bajando ${tareas.length} archivos a ${SALIDA} …`)
await enTandas(tareas)

const local = {
  ...estilo,
  sources: {
    openmaptiles: {
      type: 'vector',
      tiles: [`${BASE}/calles/{z}/{x}/{y}.pbf`],
      minzoom: 0,
      maxzoom: ZOOM_CALLES,
      bounds: LIMITES,
      attribution: calles.attribution ?? '© OpenMapTiles © OpenStreetMap',
    },
    'relieve-dem': {
      type: 'raster-dem',
      tiles: [`${BASE}/relieve/{z}/{x}/{y}.${ext}`],
      tileSize: relieve.tileSize ?? 512,
      encoding: relieve.encoding ?? 'terrarium',
      minzoom: 0,
      maxzoom: ZOOM_RELIEVE,
      bounds: LIMITES,
      attribution: relieve.attribution ?? '© Mapterhorn',
    },
  },
  layers: estilo.layers.filter((l) => l.source !== 'ne2_shaded'),
  glyphs: `${BASE}/fuentes/{fontstack}/{range}.pbf`,
  sprite: `${BASE}/iconos/ofm`,
}
await fs.mkdir(SALIDA, { recursive: true })
await fs.writeFile(path.join(SALIDA, 'estilo.json'), JSON.stringify(local))

console.log(
  `Listo: ${cuenta.nuevas} nuevos, ${cuenta.saltadas} ya estaban, ${cuenta.vacias} sin datos, ${cuenta.fallas} con error. ` +
    `${(cuenta.bytes / 1e6).toFixed(1)} MB en ${SALIDA}`,
)
if (cuenta.fallas > 0) process.exitCode = 1
