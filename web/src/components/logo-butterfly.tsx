import React from 'react';

interface LogoButterflyProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

export function LogoButterfly({ size = 'md', className = '' }: LogoButterflyProps) {
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

      {/* 抽象蝴蝶翅膀 - 左右对称，上下不对称 */}

      {/* 左上翅膀（较大、向外展开） */}
      <path
        d="M 32 28 Q 22 18 14 12 Q 18 20 26 28 Q 30 30 32 28"
        stroke="var(--foreground)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />

      {/* 右上翅膀（与左上对称） */}
      <path
        d="M 32 28 Q 42 18 50 12 Q 46 20 38 28 Q 34 30 32 28"
        stroke="var(--foreground)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />

      {/* 左下翅膀（较小、圆润） */}
      <path
        d="M 32 36 Q 24 42 18 48 Q 22 44 28 38 Q 30 36 32 36"
        stroke="var(--foreground)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />

      {/* 右下翅膀（与左下对称） */}
      <path
        d="M 32 36 Q 40 42 46 48 Q 42 44 36 38 Q 34 36 32 36"
        stroke="var(--foreground)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}
