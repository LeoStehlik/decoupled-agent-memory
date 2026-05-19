import { NextRequest, NextResponse } from 'next/server'

const canonicalHost = process.env.NEXT_PUBLIC_CANONICAL_HOST
const redirectHosts = (process.env.NEXT_PUBLIC_CANONICAL_REDIRECT_HOSTS || '')
  .split(',')
  .map((host) => host.trim())
  .filter(Boolean)

export function proxy(request: NextRequest) {
  const host = request.headers.get('host') || ''

  if (canonicalHost && redirectHosts.includes(host)) {
    const url = request.nextUrl.clone()
    url.protocol = 'http'
    url.host = canonicalHost
    return NextResponse.redirect(url, 308)
  }

  return NextResponse.next()
}

export const config = {
  matcher: '/:path*',
}
