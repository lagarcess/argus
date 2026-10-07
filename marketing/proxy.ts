import { NextResponse } from "next/server";
import { indexingEnabled } from "./lib/indexing";

export function proxy() {
  const response = NextResponse.next();
  if (!indexingEnabled(process.env.CUADRAO_SITE_INDEXING)) {
    response.headers.set("X-Robots-Tag", "noindex, nofollow");
  }
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image).*)"],
};
