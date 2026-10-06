import { NextRequest, NextResponse } from "next/server";
import {
  BUSINESS_SITE_ROOT,
  businessPreviewEnabled,
  resolveBusinessPathname,
} from "./lib/business-site";

export function proxy(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  if (
    pathname === BUSINESS_SITE_ROOT ||
    pathname.startsWith(`${BUSINESS_SITE_ROOT}/`)
  ) {
    const knownPath =
      resolveBusinessPathname(pathname) ||
      pathname === `${BUSINESS_SITE_ROOT}/icon.svg`;
    if (
      !businessPreviewEnabled(process.env.CUADRAO_WEBSITE_PREVIEW) ||
      !knownPath
    ) {
      // Deny before streaming begins so the HTTP status is a real 404.
      return new NextResponse(null, {
        status: 404,
        headers: { "X-Robots-Tag": "noindex, nofollow" },
      });
    }
    return NextResponse.next();
  }
  if (process.env.NODE_ENV === "production") {
    return new NextResponse(null, { status: 404 });
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dev/result-card/:path*", "/business/:path*"],
};
