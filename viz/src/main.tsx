import '@fontsource/bricolage-grotesque/latin-400.css'
import '@fontsource/bricolage-grotesque/latin-600.css'
import '@fontsource/bricolage-grotesque/latin-800.css'
import './tokens.css'
import './styles.css'

import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Simulador } from './App'
import { cargarAgua, cargarInversion, cargarDemografia, cargarGeo, cargarLena, cargarSimulacion, type Horizonte } from './lib/load'
import type { Resultado } from './lib/validate'

type Estado =
  | { fase: 'cargando' }
  | { fase: 'listo'; res: Resultado; geo: unknown; lena: unknown; demografia: unknown; agua: { caudales: unknown; rios: unknown }; inversion: unknown; horizonte: Horizonte }

const horizonteInicial = (): Horizonte => (new URLSearchParams(window.location.search).get('horizonte') === '15' ? '15' : '10')

function Raiz() {
  const [estado, setEstado] = useState<Estado>({ fase: 'cargando' })
  const [cambiando, setCambiando] = useState(false)
  useEffect(() => {
    let vivo = true
    const h = horizonteInicial()
    Promise.all([cargarSimulacion(h), cargarGeo(), cargarLena(), cargarDemografia(h), cargarAgua(), cargarInversion()]).then(([res, geo, lena, demografia, agua, inversion]) => {
      if (vivo) setEstado({ fase: 'listo', res, geo, lena, demografia, agua, inversion, horizonte: h })
    })
    return () => {
      vivo = false
    }
  }, [])

  // Cambiar de horizonte trae la otra corrida del modelo y la pone en su lugar, sin perder lo que la persona eligió.
  const cambiarHorizonte = (h: Horizonte) => {
    if (estado.fase !== 'listo' || cambiando || h === estado.horizonte) return
    setCambiando(true)
    void Promise.all([cargarSimulacion(h), cargarDemografia(h)]).then(([res, demografia]) => {
      setCambiando(false)
      if (!res.ok) return // la otra corrida no está: se queda la actual
      setEstado((e) => (e.fase === 'listo' ? { ...e, res, demografia, horizonte: h } : e))
    })
  }

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
  return (
    <Simulador
      data={estado.res.data}
      geoRaw={estado.geo}
      lenaRaw={estado.lena}
      demografiaRaw={estado.demografia}
      aguaRaw={estado.agua}
      inversionRaw={estado.inversion}
      horizonte={estado.horizonte}
      onHorizonte={cambiarHorizonte}
      cambiandoHorizonte={cambiando}
    />
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Raiz />
  </StrictMode>,
)
