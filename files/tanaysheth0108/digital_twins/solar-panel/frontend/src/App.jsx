import { useEffect, useMemo, useRef, useState } from 'react'
import { io } from 'socket.io-client'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const SOCKET_URL = 'http://localhost:4000'
const WINDOW_SECONDS = 120
const SAMPLE_INTERVAL_MS = 1000

export default function App() {
  const socketRef = useRef(null)
  const pointCounterRef = useRef(0)
  const latestPowerRef = useRef(0)

  const [currentPower, setCurrentPower] = useState(0)
  const [powerHistory, setPowerHistory] = useState([])
  const [mode, setMode] = useState('forward')
  const [pan, setPan] = useState(90)
  const [tilt, setTilt] = useState(45)
  const [targetPower, setTargetPower] = useState(10)
  const [targetPowerInput, setTargetPowerInput] = useState('10')
  const [optimizedPan, setOptimizedPan] = useState(null)
  const [optimizedTilt, setOptimizedTilt] = useState(null)
  const [isTargetUnachievable, setIsTargetUnachievable] = useState(false)

  useEffect(() => {
    const socket = io(SOCKET_URL, { transports: ['polling'] })
    socketRef.current = socket

    socket.on('telemetry_update', (payload) => {
      if (!payload || typeof payload.current_power !== 'number') {
        return
      }

      const nextPower = Number(payload.current_power.toFixed(2))
      latestPowerRef.current = nextPower
      setCurrentPower(nextPower)
    })

    const handleOptimizationUpdate = (payload) => {
      if (!payload || typeof payload !== 'object') {
        return
      }

      const nextPan =
        typeof payload.target_pan === 'number'
          ? payload.target_pan
          : typeof payload.pan === 'number'
            ? payload.pan
            : null
      const nextTilt =
        typeof payload.target_tilt === 'number'
          ? payload.target_tilt
          : typeof payload.tilt === 'number'
            ? payload.tilt
            : null

      if (nextPan !== null) {
        setOptimizedPan(Number(nextPan.toFixed(2)))
      }
      if (nextTilt !== null) {
        setOptimizedTilt(Number(nextTilt.toFixed(2)))
      }

      const unachievable =
        payload.unachievable === true ||
        payload.achievable === false ||
        payload.clamped === true ||
        payload.status === 'unachievable'
      setIsTargetUnachievable(unachievable)
    }

    socket.on('model_update', handleOptimizationUpdate)
    socket.on('optimization_result', handleOptimizationUpdate)

    return () => {
      socket.off('model_update', handleOptimizationUpdate)
      socket.off('optimization_result', handleOptimizationUpdate)
      socket.disconnect()
      socketRef.current = null
    }
  }, [])

  useEffect(() => {
    const timer = window.setInterval(() => {
      pointCounterRef.current += 1
      const nextPoint = {
        step: pointCounterRef.current,
        power: latestPowerRef.current,
      }

      setPowerHistory((prev) => [...prev, nextPoint].slice(-WINDOW_SECONDS))
    }, SAMPLE_INTERVAL_MS)

    return () => {
      window.clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    if (!socketRef.current) {
      return
    }

    socketRef.current.emit('control_mode', { mode })
  }, [mode])

  const handleTargetPowerChange = (event) => {
    const nextValue = event.target.value
    setTargetPowerInput(nextValue)
  }

  const handleApplyAngles = () => {
    if (!socketRef.current || mode !== 'forward') {
      return
    }

    socketRef.current.emit('set_angles', { pan, tilt })
  }

  const handleRunOptimization = () => {
    if (!socketRef.current || mode !== 'inverse') {
      return
    }

    const parsed = Number(targetPowerInput)
    if (!Number.isFinite(parsed) || parsed < 0) {
      return
    }

    setTargetPower(parsed)
    socketRef.current.emit('control_mode', { mode: 'inverse' })
    socketRef.current.emit('update_target_power', { target: parsed })
  }

  const modeLabel = useMemo(
    () => (mode === 'forward' ? 'Forward Mode (Manual)' : 'Inverse Mode (AI Optimization)'),
    [mode]
  )

  const chartData = useMemo(() => {
    const lastIndex = powerHistory.length - 1
    return powerHistory.map((point, index) => ({
      x: index - lastIndex,
      power: point.power,
    }))
  }, [powerHistory])

  const formatRelativeTime = (secondsOffset) => {
    if (!Number.isFinite(secondsOffset)) {
      return 'now'
    }

    const secondsAgo = Math.max(0, Math.round(Math.abs(secondsOffset)))
    return secondsAgo === 0 ? 'now' : `-${secondsAgo}s`
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="mb-6 rounded-2xl border border-cyan-500/20 bg-slate-900/60 p-6 shadow-2xl shadow-cyan-500/10 backdrop-blur">
          <h1 className="text-xl font-bold tracking-tight text-cyan-300 sm:text-2xl lg:text-3xl">
            Solar Panel Digital Twin - Telemetry &amp; Control
          </h1>
          <p className="mt-2 text-sm text-slate-400">{modeLabel}</p>
          <p className="mt-4 text-3xl font-semibold text-emerald-300 sm:text-4xl">
            {currentPower.toFixed(2)} W
          </p>
        </header>

        <section className="grid gap-6 lg:grid-cols-[320px,1fr]">
          <aside className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5 shadow-xl">
            <label className="mb-4 block">
              <span className="mb-2 block text-sm font-medium text-slate-200">Control Mode</span>
              <select
                value={mode}
                onChange={(event) => setMode(event.target.value)}
                className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-100 focus:border-cyan-400 focus:outline-none"
              >
                <option value="forward">Forward Mode (Manual)</option>
                <option value="inverse">Inverse Mode (AI Optimization)</option>
              </select>
            </label>

            {mode === 'forward' ? (
              <div className="space-y-5">
                <RangeControl
                  label="Pan"
                  min={0}
                  max={180}
                  step={1}
                  value={pan}
                  onChange={setPan}
                  unit="°"
                />
                <RangeControl
                  label="Tilt"
                  min={0}
                  max={90}
                  step={1}
                  value={tilt}
                  onChange={setTilt}
                  unit="°"
                />
                <button
                  type="button"
                  onClick={handleApplyAngles}
                  className="h-11 w-full rounded-lg bg-cyan-500 px-4 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 focus:outline-none focus:ring-2 focus:ring-cyan-300"
                >
                  Go
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <label className="block">
                  <div className="mb-2 flex items-center justify-between text-sm">
                    <span className="font-medium text-slate-200">Target Power</span>
                    <span className="text-cyan-300">{Number.isFinite(targetPower) ? targetPower : '--'}W</span>
                  </div>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    inputMode="decimal"
                    value={targetPowerInput}
                    onChange={handleTargetPowerChange}
                    className="h-11 w-full rounded-lg border border-slate-600 bg-slate-800 px-3 text-sm text-slate-100 focus:border-cyan-400 focus:outline-none"
                    placeholder="Enter target power (W)"
                  />
                </label>

                <button
                  type="button"
                  onClick={handleRunOptimization}
                  className="h-11 w-full rounded-lg bg-cyan-500 px-4 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 focus:outline-none focus:ring-2 focus:ring-cyan-300"
                >
                  Go
                </button>

                <div className="rounded-xl border border-slate-700 bg-slate-800/40 p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-400">Optimized Orientation</p>
                  <p className="mt-2 text-sm text-slate-200">
                    Target Pan: <span className="font-semibold text-cyan-300">{optimizedPan ?? '--'}°</span>
                  </p>
                  <p className="mt-1 text-sm text-slate-200">
                    Target Tilt: <span className="font-semibold text-cyan-300">{optimizedTilt ?? '--'}°</span>
                  </p>
                  {isTargetUnachievable ? (
                    <p className="mt-3 rounded-md border border-amber-500/50 bg-amber-500/10 px-2 py-1 text-xs text-amber-300">
                      Status: Target Power Unachievable - Showing closest approximation.
                    </p>
                  ) : null}
                </div>
              </div>
            )}
          </aside>

          <section className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5 shadow-xl">
            <div className="h-[360px] w-full sm:h-[420px]">
              <ResponsiveContainer>
                <LineChart data={chartData} margin={{ top: 10, right: 24, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis
                    dataKey="x"
                    type="number"
                    domain={[-WINDOW_SECONDS + 1, 0]}
                    ticks={[-120, -90, -60, -30, 0]}
                    stroke="#94a3b8"
                    tick={{ fill: '#94a3b8', fontSize: 12 }}
                    tickFormatter={formatRelativeTime}
                  />
                  <YAxis
                    domain={[0, 25]}
                    stroke="#94a3b8"
                    tick={{ fill: '#94a3b8', fontSize: 12 }}
                  />
                  <Tooltip
                    labelFormatter={formatRelativeTime}
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      border: '1px solid #334155',
                      borderRadius: 10,
                      color: '#e2e8f0',
                    }}
                  />
                  <Line
                    type="linear"
                    dataKey="power"
                    stroke="#22d3ee"
                    strokeWidth={3}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>
        </section>
      </div>
    </main>
  )
}

function RangeControl({ label, min, max, step, value, onChange, unit }) {
  return (
    <label className="block">
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="font-medium text-slate-200">{label}</span>
        <span className="text-cyan-300">
          {value}
          {unit}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-slate-700 accent-cyan-400"
      />
    </label>
  )
}
