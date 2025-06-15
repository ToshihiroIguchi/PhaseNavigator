/**
 * API communication utilities
 */

const API_BASE_URL = '/api';

/**
 * Make API request to generate phase diagram
 */
async function generatePhaseDiagram(data, apiKey) {
  const response = await fetch(`${API_BASE_URL}/diagrams/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-KEY': apiKey
    },
    body: JSON.stringify(data)
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Unknown error occurred' }));
    throw new Error(errorData.detail || `HTTP ${response.status}`);
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