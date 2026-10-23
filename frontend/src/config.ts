/**
 * Frontend Configuration
 * Backend Base URL dynamically resolved from Vite environment variables.
 */
function resolveApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim() !== '') {
    return envUrl.trim().replace(/\/$/, '');
  }

  // In local development, default to local FastAPI server
  if (import.meta.env.DEV) {
    return 'http://127.0.0.1:8000';
  }

  // In production without explicit VITE_API_BASE_URL, default to relative root
  return '';
}

export const API_BASE_URL = resolveApiBaseUrl();

