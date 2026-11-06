import { useEffect, useMemo, useState } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const money = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

function formatCompact(value) {
  return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value)
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const values = Object.fromEntries(payload.map((item) => [item.dataKey, item.value]))
  const point = payload[0]?.payload ?? {}
  return (
    <div className="tooltip">
      <strong>{label}</strong>
      {values.actual != null && <span>Actual: {money.format(values.actual)}</span>}
      {values.forecast != null && <span>Forecast: {money.format(values.forecast)}</span>}
      {point.lower != null && <span>90% range: {money.format(point.lower)} – {money.format(point.upper)}</span>}
    </div>
  )
}

function StatCard({ eyebrow, value, detail, tone = '' }) {
  return (
    <article className={`stat-card ${tone}`}>
      <span>{eyebrow}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  )
}

function App() {
  const [horizon, setHorizon] = useState(14)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load(force = false) {
    setLoading(true)
    setError('')
    try {
      const endpoint = force ? '/api/refresh' : '/api/analyze'
      const response = await fetch(`${endpoint}?horizon=${horizon}&history_days=900`, {
        method: force ? 'POST' : 'GET',
      })
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || `The oracle returned HTTP ${response.status}`)
      }
      setData(await response.json())
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(false) }, [horizon])

  const chartData = useMemo(() => {
    if (!data) return []
    const recent = data.history.slice(-90).map((point) => ({ date: point.date, actual: point.price }))
    const bridge = recent[recent.length - 1]
    const future = data.forecast.map((point) => ({
      date: point.date,
      forecast: point.price,
      lower: point.lower,
      upper: point.upper,
      band: [point.lower, point.upper],
    }))
    return [...recent.slice(0, -1), { ...bridge, forecast: bridge.actual }, ...future]
  }, [data])

  const actionClass = data?.decision.action.toLowerCase()

  return (
    <main>
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <nav>
        <div className="brand"><span className="coin">₿</span> Satoshi's Crystal Ball</div>
        <div className="live-pill"><i /> BTC · USD · daily</div>
      </nav>

      <header className="hero">
        <div>
          <p className="kicker">TIME-SERIES FORECASTING, MINUS THE SUIT</p>
          <h1>Should I stack sats<br />or <em>sit tight?</em></h1>
          <p className="intro">A cautious machine-learning copilot that studies price history, tests itself on the past, and explains what it sees.</p>
          <div className="controls" aria-label="Forecast settings">
            <div className="segmented">
              {[7, 14, 30].map((days) => (
                <button key={days} className={horizon === days ? 'active' : ''} onClick={() => setHorizon(days)}>
                  {days} days
                </button>
              ))}
            </div>
            <button className="refresh" onClick={() => load(true)} disabled={loading}>
              <span className={loading ? 'spin' : ''}>↻</span> Fetch fresh data
            </button>
          </div>
        </div>
        <div className="mascot-wrap" aria-hidden="true">
          <div className="orbit"><span>✦</span></div>
          <div className="mascot">
            <div className="coin-face">₿</div>
            <div className="glasses"><i /><i /></div>
            <div className="smile">⌣</div>
          </div>
          <div className="speech">Beep boop.<br />Still not a fortune teller!</div>
        </div>
      </header>

      {error && (
        <section className="error-card">
          <strong>The crystal ball is foggy.</strong>
          <span>{error}</span>
          <button onClick={() => load(false)}>Try again</button>
        </section>
      )}

      {loading && !data ? (
        <section className="loading-card">
          <div className="loader">₿</div>
          <h2>Crunching candles…</h2>
          <p>Teaching a calculator to feel market anxiety.</p>
        </section>
      ) : data && (
        <>
          <section className="stats-grid">
            <StatCard eyebrow="CURRENT PRICE" value={money.format(data.current_price)} detail={`Market close · ${data.as_of}`} />
            <StatCard eyebrow={`${horizon}-DAY FORECAST`} value={money.format(data.predicted_price)} detail={`${money.format(data.forecast_range.lower)} – ${money.format(data.forecast_range.upper)}`} tone="purple" />
            <StatCard eyebrow="EXPECTED MOVE" value={`${data.expected_return_pct >= 0 ? '+' : ''}${data.expected_return_pct}%`} detail="Model estimate, not a promise" tone={data.expected_return_pct >= 0 ? 'green' : 'red'} />
            <StatCard eyebrow="VOLATILITY" value={`${data.decision.annualized_volatility_pct}%`} detail={`${data.decision.risk_level} annualized risk`} tone="orange" />
          </section>

          <section className="main-grid">
            <article className="panel chart-panel">
              <div className="panel-heading">
                <div>
                  <p>PRICE MAP</p>
                  <h2>History meets the maybe-future</h2>
                </div>
                <div className="legend"><span className="actual-dot" /> Actual <span className="forecast-dot" /> Forecast</div>
              </div>
              <div className="chart-wrap">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartData} margin={{ top: 16, right: 10, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="actualFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#65f4c4" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#65f4c4" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="#ffffff12" vertical={false} />
                    <XAxis dataKey="date" tickFormatter={(date) => date.slice(5)} minTickGap={32} tick={{ fill: '#8e8aa7', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis domain={['auto', 'auto']} tickFormatter={(value) => `$${formatCompact(value)}`} tick={{ fill: '#8e8aa7', fontSize: 11 }} axisLine={false} tickLine={false} width={62} />
                    <Tooltip content={<ChartTooltip />} />
                    <Area type="monotone" dataKey="actual" stroke="#65f4c4" strokeWidth={3} fill="url(#actualFill)" connectNulls={false} />
                    <Area type="monotone" dataKey="band" stroke="none" fill="#9b7cff" fillOpacity={0.12} connectNulls={false} />
                    <Line type="monotone" dataKey="forecast" stroke="#b69cff" strokeWidth={3} strokeDasharray="6 5" dot={false} connectNulls={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </article>

            <article className={`panel verdict ${actionClass}`}>
              <p>THE ORACLE'S TAKE</p>
              <div className="verdict-top">
                <span>{data.decision.emoji}</span>
                <div><h2>{data.decision.action}</h2><small>{data.decision.confidence_pct}% signal confidence</small></div>
              </div>
              <div className="scorebar"><i style={{ width: `${(data.decision.score + 100) / 2}%` }} /></div>
              <div className="score-labels"><span>Sell</span><strong>Score {data.decision.score > 0 ? '+' : ''}{data.decision.score}</strong><span>Buy</span></div>
              <ul>{data.decision.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
            </article>
          </section>

          <section className="details-grid">
            <article className="panel nerd-card">
              <div className="panel-heading"><div><p>NERD CORNER</p><h2>How well did it behave?</h2></div><span className="flask">⚗</span></div>
              <div className="metric-row"><span>Held-out MAPE</span><strong>{data.metrics.mape_pct}%</strong></div>
              <div className="metric-row"><span>Direction accuracy</span><strong>{data.metrics.directional_accuracy_pct}%</strong></div>
              <div className="metric-row"><span>Test observations</span><strong>{data.metrics.test_samples}</strong></div>
              <p className="method">{data.metrics.model}. Validated with {data.metrics.validation_method}.</p>
            </article>
            <article className="panel warning-card">
              <div className="warning-icon">!</div>
              <div><p>REALITY CHECK</p><h2>Markets are chaotic goblins.</h2><span>{data.decision.disclaimer}</span></div>
            </article>
          </section>

          <footer>
            <span>Data source: {data.data_source.replaceAll('_', ' ')}</span>
            <span>Built with math, caffeine, and healthy skepticism ☕</span>
          </footer>
        </>
      )}
    </main>
  )
}

export default App

