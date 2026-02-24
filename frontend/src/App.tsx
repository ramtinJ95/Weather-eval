import { useEffect, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, TileLayer, useMapEvents } from 'react-leaflet'
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { fetchPointMetrics, type PointMetricsResponse } from './api'

type MapPoint = { lat: number; lon: number }
type TabKey = 'day' | 'month' | 'year'

const START_YEAR = 2023
const END_YEAR = Math.max(START_YEAR, new Date().getFullYear())

const SWEDEN_BOUNDS: [[number, number], [number, number]] = [
  [55.0, 10.5],
  [69.5, 24.5],
]

function MapClickHandler({ onPick }: { onPick: (point: MapPoint) => void }) {
  useMapEvents({
    click: (event) => {
      onPick({ lat: event.latlng.lat, lon: event.latlng.lng })
    },
  })

  return null
}

function monthName(month: number): string {
  return new Date(Date.UTC(2024, month - 1, 1)).toLocaleString(undefined, {
    month: 'short',
  })
}

function shortDate(dateStr: string): string {
  const parts = dateStr.split('-')
  const month = Number(parts[1])
  const day = Number(parts[2])
  return `${monthName(month)} ${day}`
}

function App() {
  const [selectedPoint, setSelectedPoint] = useState<MapPoint | null>(null)
  const [selectedYear, setSelectedYear] = useState<number>(Math.max(START_YEAR, END_YEAR - 1))
  const [selectedMonth, setSelectedMonth] = useState<number>(7)
  const [tab, setTab] = useState<TabKey>('day')
  const [data, setData] = useState<PointMetricsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!selectedPoint) {
      return
    }

    const controller = new AbortController()
    setLoading(true)
    setError(null)

    fetchPointMetrics(
      {
        lat: selectedPoint.lat,
        lon: selectedPoint.lon,
        year: selectedYear,
        month: selectedMonth,
      },
      controller.signal,
    )
      .then(setData)
      .catch((err: Error) => {
        if (err.name !== 'AbortError') {
          setError(err.message)
          setData(null)
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      })

    return () => controller.abort()
  }, [selectedPoint, selectedYear, selectedMonth])

  const yearOptions = useMemo(() => {
    const years: number[] = []
    for (let year = START_YEAR; year <= END_YEAR; year += 1) {
      years.push(year)
    }
    return years
  }, [])

  const dailyData = data?.daily.days ?? []
  const monthlyData =
    data?.monthly.months.map((item) => ({
      ...item,
      monthLabel: monthName(item.month),
      lightning_probability_pct: Number((item.lightning_probability * 100).toFixed(2)),
    })) ?? []
  const yearlyData =
    data?.yearly.years.map((item) => ({
      ...item,
      lightning_probability_pct: Number((item.lightning_probability * 100).toFixed(2)),
    })) ?? []

  const hasDailyCloud = dailyData.some((item) => item.cloud_mean_pct !== null)
  const hasDailyLightning = dailyData.some((item) => item.lightning_count > 0)
  const hasMonthlyCloud = monthlyData.some((item) => item.cloud_mean_pct !== null)
  const hasMonthlyLightning = monthlyData.some((item) => item.lightning_count > 0)
  const latestCloudYear = yearlyData.reduce<number | null>((acc, item) => {
    if (item.cloud_mean_pct === null) {
      return acc
    }
    if (acc === null || item.year > acc) {
      return item.year
    }
    return acc
  }, null)

  return (
    <main className="app-shell">
      <h1>Thundercloud Sweden</h1>

      <section className="card">
        <h2>Select point (map click)</h2>
        <p>Click anywhere in Sweden to fetch cloud + lightning metrics.</p>

        <div className="map-wrap">
          <MapContainer
            center={[62.0, 15.0]}
            zoom={5}
            scrollWheelZoom
            maxBounds={SWEDEN_BOUNDS}
            maxBoundsViscosity={1.0}
            minZoom={5}
            style={{ height: '100%' }}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <MapClickHandler onPick={setSelectedPoint} />
            {selectedPoint && (
              <CircleMarker
                center={[selectedPoint.lat, selectedPoint.lon]}
                radius={8}
                pathOptions={{ color: '#1d4ed8', fillColor: '#1d4ed8', fillOpacity: 0.75 }}
              />
            )}
          </MapContainer>
        </div>

        <div className="controls-row">
          <label>
            Year
            <select value={selectedYear} onChange={(e) => setSelectedYear(Number(e.target.value))}>
              {yearOptions.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </label>

          <label>
            Month
            <select value={selectedMonth} onChange={(e) => setSelectedMonth(Number(e.target.value))}>
              {Array.from({ length: 12 }).map((_, i) => (
                <option key={i + 1} value={i + 1}>
                  {monthName(i + 1)}
                </option>
              ))}
            </select>
          </label>
        </div>

        {!selectedPoint && <p className="hint">Pick a location to load data.</p>}

        {selectedPoint && (
          <p className="hint">
            Selected point: <strong>{selectedPoint.lat.toFixed(5)}</strong>,{' '}
            <strong>{selectedPoint.lon.toFixed(5)}</strong>
          </p>
        )}

        {loading && <p>Loading metrics...</p>}
        {error && <p className="error">{error}</p>}

        {data?.cloud_interpolation && (
          <p className="hint">
            Cloud data: nearest station{' '}
            <strong>{data.cloud_interpolation.nearest_station_name}</strong> ({data.cloud_interpolation.nearest_station_distance_km} km)
          </p>
        )}

        {selectedYear > (latestCloudYear ?? selectedYear) && latestCloudYear !== null && (
          <p className="warn">
            Cloud archive currently has data through <strong>{latestCloudYear}</strong>. Selected year is{' '}
            {selectedYear}.
          </p>
        )}
      </section>

      {data && (
        <section className="card">
          <h2>Metrics</h2>

          <div className="tabs">
            {(['day', 'month', 'year'] as const).map((key) => (
              <button
                key={key}
                className={tab === key ? 'active' : ''}
                onClick={() => setTab(key)}
                type="button"
              >
                {key.toUpperCase()}
              </button>
            ))}
          </div>

          {tab === 'day' && (
            <div className="chart-wrap">
              {!hasDailyCloud && !hasDailyLightning && (
                <p className="warn">No day-level values for this month at the selected location.</p>
              )}
              <ResponsiveContainer width="100%" height={330}>
                <ComposedChart data={dailyData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={shortDate}
                    tick={{ fontSize: 10 }}
                    minTickGap={16}
                  />
                  <YAxis
                    yAxisId="left"
                    allowDecimals={false}
                    label={{ value: 'Lightning Count', angle: -90, position: 'insideLeft', style: { textAnchor: 'middle' } }}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    domain={[0, 100]}
                    ticks={[0, 25, 50, 75, 100]}
                    tickFormatter={(v: number) => `${v}%`}
                    label={{ value: 'Cloud Cover', angle: 90, position: 'insideRight', style: { textAnchor: 'middle' } }}
                  />
                  <Tooltip labelFormatter={(label) => shortDate(String(label))} />
                  <Legend />
                  <Bar yAxisId="left" dataKey="lightning_count" fill="#f59e0b" name="Lightning count" />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="cloud_mean_pct"
                    stroke="#2563eb"
                    name="Cloud mean %"
                    dot={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}

          {tab === 'month' && (
            <div className="chart-wrap">
              {!hasMonthlyCloud && !hasMonthlyLightning && (
                <p className="warn">No month-level values for the selected year at this location.</p>
              )}
              <ResponsiveContainer width="100%" height={330}>
                <ComposedChart data={monthlyData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="monthLabel" />
                  <YAxis
                    yAxisId="left"
                    allowDecimals={false}
                    label={{ value: 'Count / Cloud %', angle: -90, position: 'insideLeft', style: { textAnchor: 'middle' } }}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tickFormatter={(v: number) => `${v}%`}
                    label={{ value: 'Lightning Prob.', angle: 90, position: 'insideRight', style: { textAnchor: 'middle' } }}
                  />
                  <Tooltip />
                  <Legend />
                  <Bar yAxisId="left" dataKey="lightning_count" fill="#f59e0b" name="Lightning count" />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="cloud_mean_pct"
                    stroke="#2563eb"
                    name="Cloud mean %"
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="lightning_probability_pct"
                    stroke="#7c3aed"
                    name="Lightning probability %"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}

          {tab === 'year' && (
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height={330}>
                <ComposedChart data={yearlyData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="year" />
                  <YAxis
                    yAxisId="left"
                    allowDecimals={false}
                    label={{ value: 'Count / Cloud %', angle: -90, position: 'insideLeft', style: { textAnchor: 'middle' } }}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tickFormatter={(v: number) => `${v}%`}
                    label={{ value: 'Lightning Prob.', angle: 90, position: 'insideRight', style: { textAnchor: 'middle' } }}
                  />
                  <Tooltip />
                  <Legend />
                  <Bar yAxisId="left" dataKey="lightning_count" fill="#f59e0b" name="Lightning count" />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="cloud_mean_pct"
                    stroke="#2563eb"
                    name="Cloud mean %"
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="lightning_probability_pct"
                    stroke="#7c3aed"
                    name="Lightning probability %"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>
      )}
    </main>
  )
}

export default App
