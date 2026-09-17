import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastRefreshed, setLastRefreshed] = useState(new Date())

  const fetchResults = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('http://127.0.0.1:5000/api/results')
      if (!response.ok) {
        throw new Error('Network response was not ok')
      }
      const data = await response.json()
      setResults(data)
      setLastRefreshed(new Date())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchResults()
    const interval = setInterval(() => {
      fetchResults()
    }, 5 * 60 * 1000) // 5 minutes

    return () => clearInterval(interval)
  }, [])

  return (
    <div className="App">
      <h1>Live Voting Results</h1>
      <button onClick={fetchResults} disabled={loading} style={{ marginBottom: '20px', padding: '10px 20px', fontSize: '16px' }}>
        {loading ? 'Refreshing...' : 'Refresh Results'}
      </button>
      
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      
      {!loading && !error && results.length === 0 && <p>No votes yet.</p>}

      <div className="results-container" style={{ display: 'flex', flexDirection: 'column', gap: '15px', alignItems: 'center' }}>
        {results.map((candidate, index) => (
          <div key={index} className="candidate-card" style={{ border: '1px solid #ccc', padding: '15px', borderRadius: '8px', width: '300px', display: 'flex', justifyContent: 'space-between', fontSize: '20px', background: '#f9f9f9', color: '#333' }}>
            <strong>{candidate.name}</strong>
            <span>{candidate.votes} votes</span>
          </div>
        ))}
      </div>
      
      <p style={{ marginTop: '30px', fontSize: '12px', color: '#666' }}>
        Last refreshed: {lastRefreshed.toLocaleTimeString()}
      </p>
    </div>
  )
}

export default App
