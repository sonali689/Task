/**
 * API client for the SwasthiQ backend.
 * 
 * All endpoints are proxied through Vite dev server (/api → localhost:8000).
 */

const API_BASE = '/api';

/**
 * Upload a billing log JSON file.
 * @param {File} file - The JSON file to upload
 * @returns {Promise<Object>} Upload response with validation results
 */
export async function uploadBillingLog(file) {
  const formData = new FormData();
  formData.append('file', file);

  const resp = await fetch(`${API_BASE}/billing/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
  }

  return resp.json();
}

/**
 * Get the deterministic reconciliation report.
 * @param {string} clinicId
 * @param {string} date - YYYY-MM-DD
 * @returns {Promise<Object>} Reconciliation report
 */
export async function getReconciliation(clinicId, date) {
  const resp = await fetch(`${API_BASE}/billing/${clinicId}/${date}/reconciliation`);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Failed to load reconciliation' }));
    throw new Error(err.detail);
  }
  return resp.json();
}

/**
 * Get the deterministic analytics report.
 * @param {string} clinicId
 * @param {string} date - YYYY-MM-DD
 * @returns {Promise<Object>} Analytics report
 */
export async function getAnalytics(clinicId, date) {
  const resp = await fetch(`${API_BASE}/billing/${clinicId}/${date}/analytics`);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Failed to load analytics' }));
    throw new Error(err.detail);
  }
  return resp.json();
}

/**
 * Generate the LLM narrative summary.
 * @param {string} clinicId
 * @param {string} date - YYYY-MM-DD
 * @returns {Promise<Object>} Narrative with traced figures
 */
export async function getNarrative(clinicId, date) {
  const resp = await fetch(`${API_BASE}/billing/${clinicId}/${date}/narrative`, {
    method: 'POST',
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Failed to generate narrative' }));
    throw new Error(err.detail);
  }
  return resp.json();
}

/**
 * List all available dates.
 * @returns {Promise<Array>} Array of { clinic_id, date, record_count }
 */
export async function getAvailableDates() {
  const resp = await fetch(`${API_BASE}/billing/dates`);
  if (!resp.ok) return [];
  return resp.json();
}

/**
 * Format paise as rupees string (₹1,234).
 * @param {number} paise
 * @returns {string}
 */
export function formatRupees(paise) {
  const rupees = paise / 100;
  if (Number.isInteger(rupees)) {
    return `₹${rupees.toLocaleString('en-IN')}`;
  }
  return `₹${rupees.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
}
