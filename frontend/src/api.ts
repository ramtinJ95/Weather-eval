type PointMetricsRequest = {
  lat: number
  lon: number
  year: number
  month: number
}

type DayMetric = {
  date: string
  cloud_mean_pct: number | null
  lightning_count: number
}

type MonthMetric = {
  month: number
  cloud_mean_pct: number | null
  lightning_probability: number
  lightning_count: number
}

type YearMetric = {
  year: number
  cloud_mean_pct: number | null
  lightning_probability: number
  lightning_count: number
}

export type PointMetricsResponse = {
  point: {
    lat: number
    lon: number
    h3_r7: string
  }
  cloud_station: {
    station_id: string
    name: string
    distance_km: number
  } | null
  daily: { days: DayMetric[] }
  monthly: { months: MonthMetric[] }
  yearly: { years: YearMetric[] }
}

export async function fetchPointMetrics(
  payload: PointMetricsRequest,
  signal?: AbortSignal,
): Promise<PointMetricsResponse> {
  const response = await fetch('/api/metrics/point', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    const maybeJson = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null
    const detail = maybeJson?.detail ? `: ${maybeJson.detail}` : ''
    throw new Error(`Metrics request failed (${response.status})${detail}`)
  }

  return (await response.json()) as PointMetricsResponse
}
