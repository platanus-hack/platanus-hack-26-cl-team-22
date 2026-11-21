interface Props {
  anios: number[]
  idx: number
  jugando: boolean
  onIdx: (i: number) => void
  onJugar: (v: boolean) => void
}

export function ControlTiempo({ anios, idx, jugando, onIdx, onJugar }: Props) {
  const ultimo = anios.length - 1
  return (
    <div className="tiempo">
      <button
        type="button"
        className="boton"
        style={{ minWidth: 86 }}
        onClick={() => {
          if (!jugando && idx >= ultimo) onIdx(0)
          onJugar(!jugando)
        }}
      >
        {jugando ? 'Pausar' : 'Reproducir'}
      </button>
      <div className="anio" aria-live="polite">
        {anios[idx]}
      </div>
      <div className="regla-tiempo">
        <input
          type="range"
          min={0}
          max={ultimo}
          step={1}
          value={idx}
          aria-label="Año de la proyección"
          aria-valuetext={String(anios[idx])}
          onChange={(e) => {
            onJugar(false)
            onIdx(Number(e.target.value))
          }}
        />
        <div className="marcas" aria-hidden="true">
          {anios.map((a, i) => (
            <span key={a} style={{ visibility: i % 2 === 0 || i === ultimo ? 'visible' : 'hidden' }}>
              {a}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
