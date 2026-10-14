import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

interface UserStatus {
  authenticated: boolean;
  has_workspace: boolean;
}

/**
 * Resolve the routing gate from the backend's single source of truth.
 *
 * Django decides "has a workspace" via `get_workspace` (signed-in user's
 * workspace, or the `bl_session` anonymous-workspace cookie). Both the Django
 * session cookie and `bl_session` are httpOnly, so this cannot be recomputed
 * client-side; we forward the incoming cookies to the existing `/api/user-status/`
 * endpoint instead of duplicating workspace resolution in the edge runtime.
 */
async function getUserStatus(cookieHeader: string | null): Promise<UserStatus | null> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/user-status/`, {
      headers: cookieHeader ? { Cookie: cookieHeader } : undefined,
      // Forward the credentials the endpoint needs to resolve the workspace.
      cache: "no-store",
    });
  } catch {
    // Network/backend failure: fail open — do not redirect, let the normal
    // page render rather than risk a redirect loop.
    return null;
  }

  if (!res.ok) return null;
  return (await res.json()) as UserStatus;
}

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Only gate the two entry points the routing decision cares about.
  if (pathname !== "/" && pathname !== "/workspace") {
    return NextResponse.next();
  }

  const cookieHeader = request.headers.get("cookie");
  const status = await getUserStatus(cookieHeader);
  if (!status) return NextResponse.next();

  const canEnter = status.authenticated || status.has_workspace;

  // On `/`: a logged-in user or a guest who already has a workspace belongs in
  // the studio. A brand-new guest (no workspace) stays on the landing page.
  if (pathname === "/" && canEnter) {
    return NextResponse.redirect(new URL("/workspace", request.url));
  }

  // On `/workspace`: a brand-new guest with no workspace must be sent back to
  // the landing page before entering the studio.
  if (pathname === "/workspace" && !canEnter) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/workspace"],
};
