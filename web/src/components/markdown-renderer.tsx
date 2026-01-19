'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Vditor from 'vditor';
import 'vditor/dist/index.css';

interface MarkdownRendererProps {
  content: string;
  baseUrl?: string;
}

interface ImageViewerProps {
  src: string;
  alt: string;
  onClose: () => void;
}

// 图片查看器组件
const ImageViewer: React.FC<ImageViewerProps> = ({ src, alt, onClose }) => {
  const [scale, setScale] = useState(1);

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY * -0.001;
    const newScale = Math.min(Math.max(0.5, scale + delta), 3);
    setScale(newScale);
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
      onClick={onClose}
    >
      <button
        className="absolute top-4 right-4 text-white text-2xl hover:text-gray-300"
        onClick={onClose}
      >
        ✕
      </button>
      <div
        className="relative max-w-[90vw] max-h-[90vh] overflow-auto"
        onClick={(e) => e.stopPropagation()}
        onWheel={handleWheel}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={alt}
          style={{ transform: `scale(${scale})` }}
          className="transition-transform duration-200"
        />
      </div>
      <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 text-white text-sm">
        滚轮缩放 • 点击背景关闭
      </div>
    </div>
  );
};

// Vditor Markdown 渲染器组件
export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({
  content,
  baseUrl = ''
}) => {
  const previewRef = useRef<HTMLDivElement>(null);
  const [viewerImage, setViewerImage] = useState<{ src: string; alt: string } | null>(null);

  // 处理图片URL
  const processImageUrl = useCallback((url: string): string => {
    if (url.startsWith('http')) {
      return url;
    }
    if (url.startsWith('/media/')) {
      return `${baseUrl}${url}`;
    }
    return url;
  }, [baseUrl]);

  // 预处理 markdown 内容
  const preprocessContent = useCallback((text: string): string => {
    // 清理连续的多个空行为最多2个空行
    text = text.replace(/\n{3,}/g, '\n\n');

    // 处理图片链接，添加完整的 URL
    if (baseUrl) {
      text = text.replace(/!\[([^\]]*)\]\(\/media\/([^)]+)\)/g, (match, alt, path) => {
        return `![${alt}](${baseUrl}/media/${path})`;
      });
    }

    return text;
  }, [baseUrl]);

  // 使用 Vditor 渲染 Markdown
  useEffect(() => {
    if (!previewRef.current) return;

    const processedContent = preprocessContent(content);

    // 使用 Vditor.preview 渲染
    Vditor.preview(previewRef.current, processedContent, {
      mode: 'dark',
      theme: {
        current: 'dark',
        path: 'https://unpkg.com/vditor/dist/css/content-theme'
      },
      hljs: {
        style: 'github-dark',
        lineNumber: true
      },
      math: {
        engine: 'KaTeX',
        inlineDigit: false,
        macros: {}
      },
      markdown: {
        toc: false,
        mark: true,
        footnotes: true,
        autoSpace: true
      },
      after: () => {
        // 渲染完成后，给所有图片添加点击事件
        if (previewRef.current) {
          const images = previewRef.current.querySelectorAll('img');
          images.forEach((img) => {
            img.style.cursor = 'pointer';
            img.onclick = () => {
              const src = img.getAttribute('src') || '';
              const alt = img.getAttribute('alt') || '';
              setViewerImage({ src: processImageUrl(src), alt });
            };

            // 处理图片加载错误
            img.onerror = () => {
              img.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIiBoZWlnaHQ9IjMwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8cmVjdCB3aWR0aD0iNDAwIiBoZWlnaHQ9IjMwMCIgZmlsbD0iIzFhMWExYSIvPgogIDx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwsIHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMTgiIGZpbGw9IiM4ODg4ODgiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj7lm77niYfliqDovb3lpLHotKU8L3RleHQ+Cjwvc3ZnPg==';
              img.style.maxWidth = '400px';
              img.style.maxHeight = '300px';
            };
          });
        }
      }
    });
  }, [content, baseUrl, preprocessContent, processImageUrl]);

  return (
    <>
      {/* Vditor 预览容器 */}
      <div
        ref={previewRef}
        className="vditor-preview vditor-preview--dark markdown-content"
        style={{
          backgroundColor: 'transparent',
          color: '#EDEDED'
        }}
      />

      {/* 图片查看器 */}
      {viewerImage && (
        <ImageViewer
          src={viewerImage.src}
          alt={viewerImage.alt}
          onClose={() => setViewerImage(null)}
        />
      )}

      {/* 自定义样式覆盖 */}
      <style jsx global>{`
        /* Vditor 暗色主题自定义 */
        .vditor-preview--dark {
          background-color: transparent !important;
          color: #ededed !important;
        }

        .vditor-preview--dark h1,
        .vditor-preview--dark h2,
        .vditor-preview--dark h3,
        .vditor-preview--dark h4,
        .vditor-preview--dark h5,
        .vditor-preview--dark h6 {
          color: #ffffff !important;
        }

        .vditor-preview--dark h1 {
          border-bottom: 1px solid #1a1a1a !important;
        }

        .vditor-preview--dark a {
          color: #60a5fa !important;
        }

        .vditor-preview--dark a:hover {
          color: #93c5fd !important;
        }

        .vditor-preview--dark code {
          background-color: #0a0a0a !important;
          color: #ededed !important;
          border: 1px solid #1a1a1a !important;
        }

        .vditor-preview--dark pre {
          background-color: #0a0a0a !important;
          border: 1px solid #1a1a1a !important;
        }

        .vditor-preview--dark pre > code {
          background-color: transparent !important;
          border: none !important;
        }

        .vditor-preview--dark table {
          border: 1px solid #1a1a1a !important;
        }

        .vditor-preview--dark table th,
        .vditor-preview--dark table td {
          border: 1px solid #1a1a1a !important;
        }

        .vditor-preview--dark table thead {
          background-color: #0a0a0a !important;
        }

        .vditor-preview--dark table tr:hover {
          background-color: #0a0a0a !important;
        }

        .vditor-preview--dark blockquote {
          border-left: 4px solid #888888 !important;
          background-color: #0a0a0a !important;
          color: #888888 !important;
        }

        .vditor-preview--dark hr {
          border-color: #1a1a1a !important;
        }

        .vditor-preview--dark img {
          border: 1px solid #1a1a1a !important;
          border-radius: 0.5rem !important;
          transition: border-color 0.2s !important;
        }

        .vditor-preview--dark img:hover {
          border-color: #888888 !important;
        }

        /* KaTeX 公式样式调整 */
        .vditor-preview--dark .katex {
          color: #ededed !important;
        }

        .vditor-preview--dark .katex-display {
          margin: 1rem 0 !important;
        }
      `}</style>
    </>
  );
};
