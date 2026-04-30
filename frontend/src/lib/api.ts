/**
 * Typed fetch client for the FastAPI backend.
 *
 * Centralised here so every hook gets:
 *   - one base URL, configurable via VITE_API_BASE_URL.
 *   - one error shape (`ApiError`) usable by TanStack Query.
 *   - one place to add auth headers, tracing, retries, etc.
 *
 * The `request<T>()` helper is generic so each hook supplies the
 * response type. We deliberately avoid hand-writing fetch calls in
 * hooks — every backend call must go through `request()` so we never
 * silently swallow non-2xx responses.
 */

const DEFAULT_BASE_URL = 'http://localhost:8000';

export const apiBaseUrl: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? DEFAULT_BASE_URL;

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  signal?: AbortSignal;
};

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal } = options;
  const url = `${apiBaseUrl}${path}`;

  const response = await fetch(url, {
    method,
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    let detail: unknown = undefined;
    try {
      detail = await response.json();
    } catch {
      // body is not JSON — leave detail undefined
    }
    const message =
      typeof detail === 'object' && detail && 'detail' in detail
        ? String((detail as { detail: unknown }).detail)
        : `Request failed with status ${response.status}`;
    throw new ApiError(response.status, message, detail);
  }

  return (await response.json()) as T;
}
