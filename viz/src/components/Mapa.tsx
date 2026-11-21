import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { elegirMapa, esEstiloValido, ESTILO_LINEA, ESTILO_LOCAL, resolverBase, siguienteMapa, type MapaElegido, type TipoMapa } from '../lib/relieve'
import { MapaPapel, type PropsMapa } from './MapaPapel'

const MapaRelieve = lazy(() => import('./MapaRelieve'))

const ESPERA_ESTILO_MS = 4000

async function leerEstilo(url: string): Promise<unknown | null> {
  const corte = new AbortController()
  const t = window.setTimeout(() => corte.abort(), ESPERA_ESTILO_MS)
  try {
    const r = await fetch(url, { signal: corte.signal, cache: 'no-cache' })
    if (!r.ok) return null
    const j: unknown = await r.json() // si el servidor devuelve index.html, esto lanza
    return esEstiloValido(j) ? j : null
  } catch {
    return null
  } finally {
    window.clearTimeout(t)
  }
}

const sondas = {
  linea: () => leerEstilo(ESTILO_LINEA),
  local: async () => {
    const e = await leerEstilo(ESTILO_LOCAL)
    return e ? resolverBase(e, new URL('mapas', document.baseURI).href) : null
  },
}

/**
 * Elige el mapa: relieve en línea; si no hay red, relieve con el paquete predescargado; si tampoco, el mapa plano.
 * `?mapa=local` o `?mapa=plano` fuerzan el respaldo, y la tecla L lo cambia en plena presentación.
 */
export function Mapa(p: PropsMapa) {
  const [elegido, setElegido] = useState<MapaElegido | null>(null)
  const turno = useRef(0)

  const elegir = useCallback((pedido: string | null) => {
    const n = ++turno.current
    void elegirMapa(pedido, sondas).then((m) => {
      if (turno.current === n) setElegido(m)
    })
  }, [])

  useEffect(() => {
    elegir(new URLSearchParams(location.search).get('mapa'))
  }, [elegir])

  // Tecla L: pasa al siguiente mapa (en línea, local, plano). Si el pedido no está disponible, sigue la cadena.
  const actual = elegido?.tipo
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== 'l' || e.ctrlKey || e.metaKey || e.altKey || !actual) return
      const tag = (e.target as HTMLElement | null)?.tagName
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return
      const sig: TipoMapa = siguienteMapa(actual)
      elegir(sig === 'linea' ? null : sig)
    }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [actual, elegir])

  if (!elegido) return <div className="mapa mapa-espera">{p.children}</div>
  if (elegido.tipo === 'plano') return <MapaPapel {...p} />
  return (
    <Suspense fallback={<div className="mapa mapa-espera">{p.children}</div>}>
      <MapaRelieve
        key={elegido.tipo}
        {...p}
        estiloBase={elegido.estilo}
        local={elegido.tipo === 'local'}
        onFalla={() => elegir(elegido.tipo === 'linea' ? 'local' : 'plano')}
      />
    </Suspense>
  )
}
