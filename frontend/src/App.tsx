import { useEffect, useState } from 'react'
import { fetchHello, type HelloResponse } from './api'

function App() {
  const [data, setData] = useState<HelloResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchHello()
      .then(setData)
      .catch((err: Error) => setError(err.message))
  }, [])

  return (
    <main>
      <h1>weather-eval</h1>
      <p>Frontend + Backend + Firebase wiring check:</p>

      {error && <p style={{ color: 'crimson' }}>Error: {error}</p>}

      {!error && !data && <p>Loading...</p>}

      {data && (
        <section>
          <p>
            <strong>Message:</strong> {data.message}
          </p>
          <p>
            <strong>Source:</strong> {data.source}
          </p>
        </section>
      )}
    </main>
  )
}

export default App
