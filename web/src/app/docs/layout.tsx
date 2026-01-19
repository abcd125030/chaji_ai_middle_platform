'use client';

import { Inter } from 'next/font/google';
import DocsSidebar from '@/components/docs/DocsSidebar';
import DocsHeader from '@/components/docs/DocsHeader';
import RouteGuard from '@/components/ui/RouteGuard';

const inter = Inter({ subsets: ['latin'] });

export default function DocsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RouteGuard>
      <div className={`min-h-screen bg-gray-50 ${inter.className}`}>
        <DocsHeader />
        <div className="flex">
          <DocsSidebar />
          <main className="flex-1 lg:ml-64">
            <div className="max-w-4xl mx-auto px-6 py-8">
              {children}
            </div>
          </main>
        </div>
      </div>
    </RouteGuard>
  );
}