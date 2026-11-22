/**
 * API communication utilities
 */

const API_BASE_URL = '/api';

/**
 * Make API request to generate phase diagram
 */
async function generatePhaseDiagram(data, apiKey) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/diagrams/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-KEY': apiKey
      },
      body: JSON.stringify(data)
    });
  } catch (networkError) {
    // fetch() rejects with a bare TypeError ("Failed to fetch") when the server is unreachable.
    throw new Error('Cannot reach the server. Check that it is running and try again.');
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Unknown error occurred' }));
    const detail = typeof errorData.detail === 'string' ? errorData.detail : '';
    throw new Error(detail || `The server returned an error (HTTP ${response.status}).`);
  }

  return await response.json();
}

/**
 * Health check endpoint
 */
async function checkHealth() {
  const response = await fetch(`${API_BASE_URL}/health/`);
  return await response.json();
}