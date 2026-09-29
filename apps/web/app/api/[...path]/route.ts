/**
 * Same-origin proxy to the FastAPI backend.
 *
 * The browser only talks to the web app (one public port, no CORS). The
 * target is read at request time, so one Docker image works everywhere:
 * set API_INTERNAL_URL (default http://127.0.0.1:8000). Response bodies are
 * streamed through untouched, which keeps Server-Sent Events live.
 */
import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const HOP_BY_HOP = [
  "connection",
  "keep-alive",
  "proxy-connection",
  "transfer-encoding",
  "upgrade",
  "te",
  "trailer",
  "host",
  "content-length",
];

function apiUrl(): string {
  return (process.env.API_INTERNAL_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
}

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const incoming = new URL(request.url);
  const target = `${apiUrl()}/api/${path.map(encodeURIComponent).join("/")}${incoming.search}`;

  const headers = new Headers(request.headers);
  for (const name of HOP_BY_HOP) headers.delete(name);
  // Ask for identity encoding so streamed bodies are forwarded as-is.
  headers.set("accept-encoding", "identity");
  headers.set("x-forwarded-host", incoming.host);
  headers.set("x-forwarded-proto", incoming.protocol.replace(":", ""));

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
      signal: request.signal,
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    if (request.signal.aborted) return new Response(null, { status: 499 });
    return Response.json({ detail: `The API is unreachable (${apiUrl()}). Is the backend running?` }, { status: 502 });
  }

  const responseHeaders = new Headers(upstream.headers);
  for (const name of [...HOP_BY_HOP, "content-encoding"]) responseHeaders.delete(name);
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export { proxy as DELETE, proxy as GET, proxy as PATCH, proxy as POST, proxy as PUT };
