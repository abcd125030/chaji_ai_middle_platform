'use client';

import React from 'react';
import Link from 'next/link';
import { siteConfig } from '@/lib/site-config';

interface LogoProps {
  showLink?: boolean;
  className?: string;
}

/**
 * Logo component with beta tag
 * Reusable across different navigation bars
 */
const Logo: React.FC<LogoProps> = ({ showLink = true, className = '' }) => {
  const logoContent = (
    <div className={`relative inline-flex items-center ${className}`}>
      <h1 className="text-base font-bold text-[var(--foreground)]">
        {siteConfig.name}
      </h1>
      <span className="ml-1.5 px-1.5 py-0.5 rounded text-[8px] font-medium bg-white text-black align-super">
        beta
      </span>
    </div>
  );

  if (showLink) {
    return (
      <Link href="/" className="cursor-pointer">
        {logoContent}
      </Link>
    );
  }

  return logoContent;
};

export default Logo;