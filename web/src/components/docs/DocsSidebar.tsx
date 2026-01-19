'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ChevronRightIcon } from '@heroicons/react/24/outline';

interface NavItem {
  title: string;
  href: string;
  children?: NavItem[];
}

const navigation: NavItem[] = [
  {
    title: 'Getting Started',
    href: '/docs/getting-started',
    children: [
      { title: 'Quick Start', href: '/docs/getting-started' },
      { title: 'Environment Setup', href: '/docs/getting-started/setup' },
      { title: 'First Application', href: '/docs/getting-started/first-app' },
    ],
  },
  {
    title: 'API Documentation',
    href: '/docs/api',
    children: [
      { title: 'API Overview', href: '/docs/api' },
      { title: 'Authentication', href: '/docs/api/authentication' },
      { title: 'Chat Sessions', href: '/docs/api/chat' },
      { title: 'Knowledge Base', href: '/docs/api/knowledge' },
      { title: 'File Processing', href: '/docs/api/files' },
    ],
  },
  {
    title: 'System Architecture',
    href: '/docs/architecture',
    children: [
      { title: 'Overall Architecture', href: '/docs/architecture' },
      { title: 'Frontend Architecture', href: '/docs/architecture/frontend' },
      { title: 'Backend Architecture', href: '/docs/architecture/backend' },
      { title: 'Data Flow', href: '/docs/architecture/data-flow' },
    ],
  },
  {
    title: 'Development Guide',
    href: '/docs/development',
    children: [
      { title: 'Development Environment', href: '/docs/development' },
      { title: 'Coding Standards', href: '/docs/development/coding-standards' },
      { title: 'Testing Guide', href: '/docs/development/testing' },
      { title: 'CI/CD', href: '/docs/development/cicd' },
    ],
  },
  {
    title: 'Deployment & Operations',
    href: '/docs/deployment',
    children: [
      { title: 'Deployment Guide', href: '/docs/deployment' },
      { title: 'Docker Deployment', href: '/docs/deployment/docker' },
      { title: 'Kubernetes', href: '/docs/deployment/kubernetes' },
      { title: 'Monitoring & Alerting', href: '/docs/deployment/monitoring' },
    ],
  },
  {
    title: 'Troubleshooting',
    href: '/docs/troubleshooting',
    children: [
      { title: 'Common Issues', href: '/docs/troubleshooting' },
      { title: 'Performance Optimization', href: '/docs/troubleshooting/performance' },
      { title: 'Error Codes', href: '/docs/troubleshooting/error-codes' },
    ],
  },
];

export default function DocsSidebar() {
  const pathname = usePathname();

  const isActiveLink = (href: string) => {
    return pathname === href || pathname.startsWith(href + '/');
  };

  const renderNavItem = (item: NavItem, level = 0) => {
    const isActive = isActiveLink(item.href);
    const hasChildren = item.children && item.children.length > 0;
    const isExpanded = hasChildren && item.children?.some(child => isActiveLink(child.href));

    return (
      <div key={item.href}>
        <Link
          href={item.href}
          className={`group flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
            level === 0 ? 'mb-1' : 'ml-4 mb-0.5'
          } ${
            isActive
              ? 'bg-blue-50 text-blue-700 border-r-2 border-blue-500'
              : 'text-gray-700 hover:text-gray-900 hover:bg-gray-50'
          }`}
        >
          <span className="flex-1">{item.title}</span>
          {hasChildren && (
            <ChevronRightIcon
              className={`w-4 h-4 transition-transform ${
                isExpanded ? 'rotate-90' : ''
              }`}
            />
          )}
        </Link>
        
        {hasChildren && isExpanded && (
          <div className="mt-1 space-y-0.5">
            {item.children?.map(child => renderNavItem(child, level + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <aside className="hidden lg:block fixed inset-y-0 left-0 w-64 bg-white border-r border-gray-200 pt-16 overflow-y-auto">
      <nav className="px-3 py-6">
        <div className="space-y-1">
          {navigation.map(item => renderNavItem(item))}
        </div>
      </nav>
    </aside>
  );
}