import React from 'react';
import { LogoButterfly } from './logo-butterfly';

interface LogoProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

export function Logo({ size = 'md', className = '' }: LogoProps) {
  // 根据环境变量选择不同的 Logo
  const logoType = process.env.NEXT_PUBLIC_LOADING_SVG || 'frago';

  // 如果是 chagee，显示蝴蝶 Logo
  if (logoType === 'chagee') {
    return <LogoButterfly size={size} className={className} />;
  }

  // 默认 Logo (frago 或其他)
  const sizeMap = {
    sm: 'w-8 h-8',
    md: 'w-12 h-12',
    lg: 'w-16 h-16',
    xl: 'w-20 h-20',
  };

  return (
    <svg
      className={`${sizeMap[size]} ${className}`}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* 背景圆角矩形 */}
      <rect
        width="64"
        height="64"
        rx="16"
        fill="var(--accent)"
        stroke="var(--border)"
        strokeWidth="1"
      />
      {/* 层叠的倒V形 - 外层更长，内层更短 */}
      <g>
        {/* 外层 - 更长的两条边 */}
        <path
          d="M 32 14 L 12 48 M 32 14 L 52 48"
          stroke="var(--foreground)"
          strokeWidth="3"
          strokeLinecap="round"
          fill="none"
        />
        {/* 内层 - 更短的两条边 */}
        <path
          d="M 32 22 L 20 40 M 32 22 L 44 40"
          stroke="var(--foreground)"
          strokeWidth="3"
          strokeLinecap="round"
          fill="none"
        />
      </g>
    </svg>
  );
}

// 文字Logo组件
interface TextLogoProps {
  text?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

export function TextLogo({ text = 'X', size = 'md', className = '' }: TextLogoProps) {
  const sizeMap = {
    sm: 'w-8 h-8 text-lg',
    md: 'w-12 h-12 text-2xl',
    lg: 'w-16 h-16 text-3xl',
    xl: 'w-20 h-20 text-4xl',
  };

  const [containerSize, textSize] = sizeMap[size].split(' text-');

  return (
    <div className={`${containerSize} bg-[var(--accent)] rounded-2xl flex items-center justify-center border border-[var(--border)] ${className}`}>
      <span className={`text-${textSize} font-bold text-[var(--foreground)]`}>
        {text}
      </span>
    </div>
  );
}