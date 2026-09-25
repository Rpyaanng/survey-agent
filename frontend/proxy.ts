import { NextResponse, type NextRequest } from "next/server";

// Cheap optimistic gate: bounce visitors without a session cookie before the
// dashboard renders. The API still validates the token on every request.
export function proxy(request: NextRequest) {
  const hasSession = request.cookies.has("sa_session");
  const { pathname, search } = request.nextUrl;

  if (pathname.startsWith("/dashboard") && !hasSession) {
    const url = new URL("/login", request.url);
    url.searchParams.set("next", pathname + search);
    return NextResponse.redirect(url);
  }
  if ((pathname === "/login" || pathname === "/signup") && hasSession) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/login", "/signup"],
};
