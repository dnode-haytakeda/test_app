import { env } from "../config/env";

export class ApiError extends Error {
    readonly status: number;
    readonly code: string;
    readonly requestId: string | null;

    constructor(
        status: number,
        code: string,
        requestId: string | null,
        message: string,
    ) {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.code = code;
        this.requestId = requestId;
    }
}

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface RequestOptions {
    params?: Record<string, string | number | boolean | undefined>;
    body?: unknown;
    signal?: AbortSignal;
    headers?: Record<string, string>;
}

const BASE_URL = env.VITE_API_BASE_URL;
const DEFAULT_TIMEOUT_MS = 30_000;

let accessToken: string | null = null;
let refreshPromise: Promise<boolean> | null = null;

export const AUTH_SIGNED_OUT_EVENT = "auth:signed-out";

export function setAccessToken(token: string): void {
    accessToken = token;
}

export function clearAccessToken(): void {
    accessToken = null;
    if (typeof window !== "undefined") {
        window.dispatchEvent(new Event(AUTH_SIGNED_OUT_EVENT));
    }
}

function getAuthHeaders(): Record<string, string> {
    return accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
}

function buildUrl(path: string, params?: RequestOptions["params"]): string {
    const url = new URL(`${BASE_URL}${path}`, window.location.origin);
    if (params) {
        for (const [key, value] of Object.entries(params)) {
            if (value !== undefined) url.searchParams.set(key, String(value));
        }
    }
    return url.toString();
}

async function refreshToken(): Promise<boolean> {
    try {
        const res = await fetch(`${BASE_URL}/auth/refresh`, {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
        });
        if (!res.ok) return false;
        const data = (await res.json()) as { access_token: string };
        setAccessToken(data.access_token);
        return true;
    } catch {
        return false;
    }
}

async function handleUnauthorized(): Promise<boolean> {
    if (!refreshPromise) {
        refreshPromise = refreshToken().finally(() => {
            refreshPromise = null;
        });
    }
    return refreshPromise;
}

async function request<T>(
    method: HttpMethod,
    path: string,
    options: RequestOptions = {},
): Promise<T> {
    const url = buildUrl(path, method === "GET" ? options.params : undefined);
    const baseHeaders: Record<string, string> = {
        "Content-Type": "application/json",
        ...options.headers,
    };
    const baseInit: Omit<RequestInit, "headers" | "signal"> = {
        method,
        credentials: "include",
    };
    if (method !== "GET" && options.body !== undefined) {
        baseInit.body = JSON.stringify(options.body);
    }

    async function attempt(): Promise<Response> {
        const timeoutController = new AbortController();
        const timeoutId = setTimeout(
            () =>
                timeoutController.abort(
                    new DOMException("Request timed out", "TimeoutError"),
                ),
            DEFAULT_TIMEOUT_MS,
        );
        const signal = options.signal
            ? AbortSignal.any([options.signal, timeoutController.signal])
            : timeoutController.signal;
        const headers = { ...baseHeaders, ...getAuthHeaders() };
        try {
            return await fetch(url, { ...baseInit, headers, signal });
        } catch (err) {
            if (err instanceof DOMException && err.name === "TimeoutError") {
                throw new ApiError(0, "TIMEOUT", null, "Request timed out");
            } 
            if (err instanceof DOMException && err.name === "AbortError") throw err;
            throw new ApiError(
                0,
                "NETWORK_ERROR",
                null,
                "Please check your connection",
            );
        } finally {
            clearTimeout(timeoutId);
        }
    }

    let res = await attempt();

    if (res.status === 401) {
        const refreshed = await handleUnauthorized();
        if (refreshed) {
            res = await attempt();
        } else {
            clearAccessToken();
            throw new ApiError(401, "UNAUTHORIZED", null, "Session expired");
        }
    }

    if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as {
            detail?: string;
            error_code?: string;
            request_id?: string;
        };
        throw new ApiError(
            res.status,
            body.error_code ?? "UNKNOWN",
            body.request_id ?? res.headers.get("X-Request-ID"),
            body.detail ?? res.statusText,
        );
    }

    if (res.status === 204) return undefined as T;
    return res.json() as Promise<T>;
}

export const api = {
    get: <T>(path: string, options?: RequestOptions) =>
        request<T>("GET", path, options),
    post: <T>(path: string, options?: RequestOptions) => 
        request<T>("POST", path, options),
    put: <T>(path: string, options?: RequestOptions) => 
        request<T>("PUT", path, options),
    patch: <T>(path: string, options?: RequestOptions) => 
        request<T>("PATCH", path, options),
    delete: <T>(path: string, options?: RequestOptions) => 
        request<T>("DELETE", path, options),
}
