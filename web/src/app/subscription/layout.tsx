'use client';

import RouteGuard from '@/components/ui/RouteGuard';

export default function SubscriptionLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RouteGuard>
      {children}
    </RouteGuard>
  );
}