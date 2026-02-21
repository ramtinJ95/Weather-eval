export type HelloResponse = {
  message: string
  source: 'firestore' | 'default' | 'error'
}

export async function fetchHello(): Promise<HelloResponse> {
  const response = await fetch('/api/hello')

  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`)
  }

  return (await response.json()) as HelloResponse
}
