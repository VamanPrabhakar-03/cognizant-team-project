const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

export async function request(path, options = {}) {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  const url = cleanPath.startsWith('http') ? cleanPath : `${API_BASE}${cleanPath}`;
  
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });

  const contentType = response.headers.get('content-type') || '';
  if (!response.ok) {
    let errorDetail = `${response.status} ${response.statusText}`;
    if (contentType.includes('application/json')) {
      try {
        const errJson = await response.json();
        if (errJson.detail) {
          errorDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
        }
      } catch {
        // ignore
      }
    } else {
      const text = await response.text();
      if (text) errorDetail = text.slice(0, 100);
    }
    const err = new Error(errorDetail);
    err.status = response.status;
    throw err;
  }

  if (contentType.includes('application/json')) {
    return response.json();
  }
  return response.text();
}

export function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return [];
  const headers = lines[0].split(',').map((val) => val.trim().replace(/^"|"$/g, ''));
  return lines.slice(1).map((line) => {
    const values = line.split(',').map((val) => val.trim().replace(/^"|"$/g, ''));
    return Object.fromEntries(headers.map((header, index) => [header, values[index] || '']));
  });
}
