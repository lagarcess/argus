import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

export async function proxy(request: NextRequest) {
  let supabaseResponse = NextResponse.next({
    request,
  })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value))
          supabaseResponse = NextResponse.next({
            request,
          })
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  const {
    data: { user },
  } = await supabase.auth.getUser()

  const url = request.nextUrl.clone()
  const bypassParam = url.searchParams.get('bypass_auth')
  const bypassCookie = request.cookies.get('sb-mock-bypass')?.value

  const isBypassActive = bypassParam === 'true' || bypassCookie === 'true'
  const isMockMode = process.env.NEXT_PUBLIC_MOCK_AUTH === "true" ||
                     (process.env.NODE_ENV === "development" && isBypassActive)

  const isProtectedRoute = request.nextUrl.pathname.startsWith('/builder') ||
                           request.nextUrl.pathname.startsWith('/strategies') ||
                           request.nextUrl.pathname.startsWith('/history') ||
                           request.nextUrl.pathname.startsWith('/profile')

  // Zero-trust boundary: If trying to access protected route without user OR mock override
  if (isProtectedRoute && !user && !isMockMode) {
    url.pathname = '/'
    return NextResponse.redirect(url)
  }

  // Persist bypass via cookie if parameter is present (development only)
  if (process.env.NODE_ENV === "development") {
    if (bypassParam === 'true') {
      supabaseResponse.cookies.set('sb-mock-bypass', 'true', {
        path: '/',
        maxAge: 60 * 60 * 24, // 1 day
        httpOnly: false, // Allow client-side detection for session hydration
        sameSite: 'lax',
      })
    } else if (bypassParam === 'false') {
      supabaseResponse.cookies.delete('sb-mock-bypass')
    }
  }

  return supabaseResponse
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * Feel free to modify this pattern to include more paths.
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
