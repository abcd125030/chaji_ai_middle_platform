'use client';

import { usePathname } from 'next/navigation';
import { notFound } from 'next/navigation';
import { isRouteAccessible } from '@/lib/menu-access-control';

/**
 * Route access control component
 * Check if current route is allowed access, if not use Next.js built-in 404 handling
 */
export default function RouteGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  // If current route is not accessible, trigger Next.js 404 handling
  if (!isRouteAccessible(pathname)) {
    notFound();
  }

  return <>{children}</>;
}