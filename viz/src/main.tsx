import '@fontsource/source-serif-4/latin-400.css'
import '@fontsource/source-serif-4/latin-600.css'
import '@fontsource/ibm-plex-sans/latin-400.css'
import '@fontsource/ibm-plex-sans/latin-500.css'
import '@fontsource/ibm-plex-sans/latin-600.css'
import '@fontsource/ibm-plex-mono/latin-400.css'
import '@fontsource/ibm-plex-mono/latin-500.css'
import './tokens.css'
import './styles.css'

import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Simulador } from './App'
import { cargarGeo, cargarSimulacion } from './lib/load'
import type { Resultado } from './lib/validate'

type Estado = { fase: 'cargando' } | { fase: 'listo'; res: Resultado; geo: unknown }

function Raiz() {
  const [estado, setEstado] = useState<Estado>({ fase: 'cargando' })
  useEffect(() => {
    let vivo = true
    Promise.all([cargarSimulacion(), cargarGeo()]).then(([res, geo]) => {
      if (vivo) setEstado({ fase: 'listo', res, geo })
    })
    return () => {
      vivo = false
    }
  }, [])

  if (estado.fase === 'cargando') {
    return (
      <div className="estado">
        <span className="caps">Cargando datos…</span>
      </div>
    )
  }
  if (!estado.res.ok) {
    return (
      <div className="estado" role="alert">
        <span className="caps">Error en los datos</span>
        <h1>El archivo de simulación no tiene el formato esperado</h1>
        <p>Revisa que coincida con el contrato descrito en docs/plan-comunas.md. Detalle:</p>
        <ul>
          {estado.res.errores.map((e, i) => (
            <li key={i}>{e}</li>
          ))}
        </ul>
      </div>
    )
  }
  return <Simulador data={estado.res.data} geoRaw={estado.geo} />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Raiz />
  </StrictMode>,
)
