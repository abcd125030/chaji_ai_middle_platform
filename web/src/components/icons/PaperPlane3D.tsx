import React from 'react';

interface PaperPlane3DProps {
  className?: string;
}

/**
 * 3D透视纸飞机图标组件
 * 机头朝向右上方，具有立体透视效果
 */
const PaperPlane3D: React.FC<PaperPlane3DProps> = ({ className = 'w-6 h-6' }) => {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* 主机身 - 带渐变填充 */}
      <defs>
        <linearGradient id="planeGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.8" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="1" />
        </linearGradient>
      </defs>
      
      {/* 纸飞机主体 - 3D透视效果 */}
      <path
        d="M2.5 19L21.5 12L2.5 5L2.5 10.5L14 12L2.5 13.5L2.5 19Z"
        fill="url(#planeGradient)"
        transform="rotate(-30 12 12)"
      />
      
      {/* 机翼阴影 - 增强立体感 */}
      <path
        d="M4 16.5L18 11.5L4 9.5L4 11L12 11.5L4 12L4 16.5Z"
        fill="currentColor"
        opacity="0.3"
        transform="rotate(-30 12 12)"
      />
      
      {/* 折痕线条 - 显示纸张折叠效果 */}
      <path
        d="M2.5 12L21.5 12"
        stroke="currentColor"
        strokeWidth="0.5"
        strokeOpacity="0.4"
        transform="rotate(-30 12 12)"
      />
    </svg>
  );
};

export default PaperPlane3D;