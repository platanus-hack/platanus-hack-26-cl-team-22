import '@fontsource/bricolage-grotesque/latin-400.css'
import '@fontsource/bricolage-grotesque/latin-600.css'
import '@fontsource/bricolage-grotesque/latin-800.css'
import './tokens.css'
import './styles.css'

import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Simulador } from './App'
import { cargarDemografia, cargarGeo, cargarLena, cargarSimulacion } from './lib/load'
import type { Resultado } from './lib/validate'

type Estado = { fase: 'cargando' } | { fase: 'listo'; res: Resultado; geo: unknown; lena: unknown; demografia: unknown }

function Raiz() {
  const [estado, setEstado] = useState<Estado>({ fase: 'cargando' })
  useEffect(() => {
    let vivo = true
    Promise.all([cargarSimulacion(), cargarGeo(), cargarLena(), cargarDemografia()]).then(([res, geo, lena, demografia]) => {
      if (vivo) setEstado({ fase: 'listo', res, geo, lena, demografia })
    })
    return () => {
      vivo = false
    }
  }, [])

  if (estado.fase === 'cargando') {
    return (
      <div className="estado">
        <p className="estado-marca">root</p>
        <p>Cargando la simulación…</p>
      </div>
    )
  }
  if (!estado.res.ok) {
    return (
      <div className="estado" role="alert">
        <p className="estado-marca">root</p>
        <h1>El archivo de simulación no tiene el formato esperado</h1>
        <p>Revisa que coincida con el contrato de docs/plan-comunas.md y vuelve a cargar la página. Problemas encontrados:</p>
        <ul>
          {estado.res.errores.map((e, i) => (
            <li key={i}>{e}</li>
          ))}
        </ul>
      </div>
    )
  }
  return <Simulador data={estado.res.data} geoRaw={estado.geo} lenaRaw={estado.lena} demografiaRaw={estado.demografia} />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Raiz />
  </StrictMode>,
)
