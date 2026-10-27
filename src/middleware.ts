import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Loopback guard for the local-only screening app.
 *
 * Job Attune exposes powerful local APIs (filesystem browse, engine spawn,
 * PDF export). A web page in the same browser can attack them two ways:
 * cross-site requests (drive-by CSRF, e.g. `fetch(..., { mode: "no-cors" })`)
 * and DNS-rebinding. Mitigations implemented here:
 *
 * 1. Client-header requirement: every /api request must carry the
 *    `X-Attune-Client` header. The UI's `api()` helper always sends it;
 *    cross-site `no-cors` requests CANNOT set custom headers, which kills the
 *    realistic drive-by vector. Plain HTTP clients (curl/scripts) must send
 *    the header explicitly, e.g. `-H "X-Attune-Client: cli"`.
 * 2. Cross-site browser navigation is rejected via the `Sec-Fetch-Site` header
 *    when the browser supplies it.
 *
 * Residual risk (documented): DNS-rebinding with a fully spoofed same-origin
 * context cannot be distinguished by headers alone - run the server bound to
 * 127.0.0.1 (package.json dev/start scripts) so it is unreachable from other
 * machines.
 */
const CLIENT_HEADER = "x-attune-client";

export function middleware(request: NextRequest) {
  const secFetchSite = request.headers.get("sec-fetch-site");
  if (secFetchSite === "cross-site") {
    return NextResponse.json(
      { error: "Forbidden: cross-site requests are not allowed" },
      { status: 403 },
    );
  }
  if (!request.headers.get(CLIENT_HEADER)) {
    return NextResponse.json(
      { error: "Forbidden: missing X-Attune-Client header" },
      { status: 403 },
    );
  }
  return NextResponse.next();
}

export const config = {
  matcher: "/api/:path*",
};
