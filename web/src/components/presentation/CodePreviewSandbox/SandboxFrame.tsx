/**
 * SandboxFrame component
 *
 * This component creates a secure sandbox environment (iframe) for previewing and rendering HTML, CSS and JavaScript code.
 * Supports real-time content updates, screenshot functionality, theme customization and edit mode, with parent-child frame communication via postMessage.
 */
import { useEffect, useRef, useCallback, forwardRef, useImperativeHandle } from 'react';
import { saveAs } from 'file-saver';

// Import base styles module
import { baseStyles } from './styles/baseStyles';
// Import scrollbar styles
import { scrollbarStyles } from './styles/scrollbarStyles';

// Import type definitions, including newly added SandboxMessage
import { SandboxFrameProps, SandboxFrameRef, SandboxMessage } from './types';

/**
 * Helper function for processing HTML content
 *
 * Used to clean and process incoming HTML code, removing unnecessary tags and content,
 * ensuring only necessary content is rendered in the sandbox environment.
 *
 * @param html - Original HTML string
 * @returns Processed HTML string
 */
const processHtml = (html: string): string => {
  // ... (keep existing processHtml function)
  // 1. First remove script tags to prevent execution during parsing
  let processed = html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');

  // 2. Try to extract content inside <body> tags (if AI-generated code contains complete HTML structure)
  const bodyMatch = processed.match(/<body[^>]*>([\s\S]*)<\/body>/i);
  if (bodyMatch && bodyMatch[1]) {
    processed = bodyMatch[1];
  }

  // 3. 移除任何剩余的 <html>、<head> 标签及其内容
  // 这是一个简化的移除方法，可能无法处理所有边缘情况
  processed = processed.replace(/<html[^>]*>[\s\S]*?<\/html>/gi, ''); // 移除 <html> 及其内容
  processed = processed.replace(/<head[^>]*>[\s\S]*?<\/head>/gi, ''); // 移除 <head> 及其内容

  // 4. 双引号修复已移除，可能导致问题，原始 AI 输出似乎是正确的

  // 5. 修剪空白字符
  return processed.trim();
};

/**
 * SandboxFrame 组件 - 使用 forwardRef 包装以支持引用传递
 */
const SandboxFrame = forwardRef<SandboxFrameRef, SandboxFrameProps>(
  (
    {
      htmlContent, // HTML 内容
      cssContent, // CSS 内容
      jsContent, // JavaScript 内容
      globalStyleCode, // 全局样式代码
      themeBackgroundColor, // 主题背景色
      themeTextColor, // 主题文本颜色
      onCaptureError, // 捕获错误回调函数
      onHtmlChange, // HTML 内容变化回调
      onRequestTextModification, // 文本修改请求回调
      isEditMode = false, // 是否为编辑模式，默认为 false
    },
    ref // 组件引用
  ) => {
    // iframe 的引用
    const iframeRef = useRef<HTMLIFrameElement | null>(null);
    // 标记 iframe 是否已加载就绪
    const isIframeReady = useRef(false);

    // 存储最新回调属性的引用，避免在 useEffect 中出现过时闭包问题
    const onHtmlChangeRef = useRef(onHtmlChange);
    const onRequestTextModificationRef = useRef(onRequestTextModification);

    // 当属性变化时更新引用
    useEffect(() => {
      onHtmlChangeRef.current = onHtmlChange;
    }, [onHtmlChange]);

    useEffect(() => {
      onRequestTextModificationRef.current = onRequestTextModification;
    }, [onRequestTextModification]);

    /**
     * 向 iframe 发送内容更新的函数
     *
     * 当 HTML、CSS 或 JS 内容变化时，将处理后的内容发送到 iframe
     */
    const sendContentUpdate = useCallback(() => {
      if (iframeRef.current && iframeRef.current.contentWindow && isIframeReady.current) {
        const message = {
          type: 'updateContent',
          payload: {
            html: processHtml(htmlContent || ''),
            css: cssContent || '',
            js: jsContent || '',
          },
        };
        iframeRef.current.contentWindow.postMessage(message, '*');
      }
    }, [htmlContent, cssContent, jsContent]);

    /**
     * 通过 ref 暴露方法，允许父组件调用沙箱功能
     */
    useImperativeHandle(ref, () => ({
      // 请求捕获指定元素的方法
      requestCapture: (elementId: string) => {
        if (iframeRef.current && iframeRef.current.contentWindow && isIframeReady.current) {
          console.log(`[Parent] Sending captureElement request for ID: ${elementId}`);
          iframeRef.current.contentWindow.postMessage(
            {
              type: 'captureElement',
              payload: { elementId },
            },
            '*'
          );
        } else {
          console.error('[Parent] Cannot send capture request: iframe not ready or not available.');
          onCaptureError?.('沙盒环境尚未准备就绪，无法截图。');
        }
      },
      // 向沙箱发送消息的方法
      sendMessage: (message: SandboxMessage) => {
        if (iframeRef.current?.contentWindow && isIframeReady.current) {
          iframeRef.current.contentWindow.postMessage(message, '*');
        } else {
          console.error('[Parent] Cannot send message: iframe not ready or not available.');
          onCaptureError?.('沙盒环境尚未准备就绪，无法发送消息。');
        }
      },
    }));

    /**
     * 效果 1: 创建 iframe，设置基本 srcdoc，并添加消息监听器
     *
     * 这个 useEffect 负责：
     * 1. 创建和配置 iframe
     * 2. 设置初始 HTML 文档
     * 3. 处理与 iframe 之间的消息通信
     * 4. 清理资源
     */
    useEffect(() => {
      isIframeReady.current = false; // 重置就绪标志

      // 创建 iframe 元素
      const iframe = document.createElement('iframe');
      iframeRef.current = iframe;
      iframe.style.width = '100%';
      iframe.style.height = '100%';
      iframe.style.border = 'none';
      // 设置安全沙箱属性，明确指定允许的功能
      iframe.setAttribute(
        'sandbox',
        'allow-scripts allow-same-origin allow-presentation allow-forms allow-popups allow-downloads allow-modals'
      );

      // 获取 iframe 容器元素
      const iframeContainer = document.getElementById('iframe-container');
      if (!iframeContainer) {
        console.error('[Parent] iframe-container element not found!');
        return;
      }

      iframeContainer.innerHTML = ''; // 清除之前的 iframe
      iframeContainer.appendChild(iframe);

      // 获取 basePath - 在运行时获取
      const basePath = typeof window !== 'undefined' 
        ? window.location.pathname.startsWith('/_studio') ? '/_studio' : ''
        : '';

      // iframe 的基础 HTML 文档
      const baseSrcDoc = `
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
            <link rel="stylesheet" href="${basePath}/vendor/revealjs/reveal.css" id="theme">
            <link rel="stylesheet" href="https://cdn.bootcdn.net/ajax/libs/font-awesome/6.7.2/css/all.min.css">
            <script src="https://cdn.tailwindcss.com"></script>
            <script>
              // 在内容加载前设置初始主题颜色 - 使用独立的命名空间避免与外部冲突
              document.documentElement.style.setProperty('--iframe-background', '${themeBackgroundColor || '#1a1a1a'}');
              document.documentElement.style.setProperty('--iframe-text', '${themeTextColor || '#ffffff'}');
              // 设置全局 basePath 变量供 iframeScript.js 使用
              window.BASE_PATH = '${basePath}';
            </script>
            <style id="global-styles">
              /* 防止iframe内部样式影响外部 - 使用固定值避免被内容覆盖 */
              :root {
                /* 使用iframe专用的变量，避免与外部冲突 */
                --background: var(--iframe-background);
                --foreground: var(--iframe-text);
                --text: var(--iframe-text);
                /* 使用固定值而非半透明值，避免在白色背景上不可见 */
                --border: #2a2a2a;
                --code-bg: #1f1f1f;
                --accent: #383838;
              }
              html, body {
                height: 100%; /* Reverted to 100% */
                margin: 0;
                padding: 0;
                /* overflow: hidden; -- REMOVED TO ALLOW .slide-content-wrapper TO SCROLL */
              }
              .reveal {
                height: 100%; /* Reverted to 100% */
                background-color: var(--iframe-background);
                color: var(--iframe-text);
                /* display: block; -- Removed to revert to Reveal.js default or baseStyles */
              }
              /* Removed custom .slides and section styles to revert to defaults or baseStyles */
              ${baseStyles}
              ${scrollbarStyles} /* Inject scrollbar styles */
              /* 自定义滚动条样式已移除，将应用全局样式 */
              ${globalStyleCode || ''}
            </style>
            <style id="dynamic-styles"></style> <!-- 动态 CSS 的占位符 -->
        </head>
        <body>
          <div class="reveal">
            <div class="slides">
              <section id="slide-content-section">
                 <div class="slide-content-wrapper">
                   <!-- HTML 内容将注入此处 -->
                 </div>
              </section>
            </div>
          </div>
          <!-- 库将由 iframeScript.js 动态加载 -->
          <script src="${basePath}/sandbox/iframeScript.js"></script>
          ${isEditMode ? `<script src="${basePath}/sandbox/editModeScript.js"></script>` : ''}
        </body>
      </html>
    `;

      iframe.srcdoc = baseSrcDoc;

      /**
       * iframe 消息处理函数
       *
       * 处理从 iframe 接收的各种消息，包括：
       * - iframeReady: iframe 已准备就绪
       * - captureResult: 截图结果
       * - captureError: 截图错误
       * - requestTextModification: 文本修改请求
       */
      const handleIframeMessage = (event: MessageEvent) => {
        // 基本安全检查：确保消息来自我们的 iframe
        if (event.source !== iframeRef.current?.contentWindow) {
          return;
        }

        const message = event.data;

        // 处理 'iframeReady' 消息
        if (message.type === 'iframeReady') {
          console.log('[Parent] Received iframeReady message.');
          isIframeReady.current = true;
          // 发送初始主题更新
          if (iframeRef.current && iframeRef.current.contentWindow) {
            const themeMessage = {
              type: 'updateTheme',
              payload: {
                backgroundColor: themeBackgroundColor,
                textColor: themeTextColor,
              },
            };
            iframeRef.current.contentWindow.postMessage(themeMessage, '*');
          }
          sendContentUpdate(); // 发送初始内容
        }
        // 处理 'captureResult' 消息
        else if (message.type === 'captureResult') {
          console.log('[Parent] Received captureResult message.');
          const blob = message.payload?.blob;
          if (blob instanceof Blob) {
            try {
              // 使用默认文件名，后期可配置
              saveAs(blob, 'capture.png');
              console.log('[Parent] Download triggered via saveAs.');
            } catch (e) {
              console.error('[Parent] Error triggering download with saveAs:', e);
              onCaptureError?.('下载图片失败，请检查浏览器设置或稍后重试。');
            }
          } else {
            console.error(
              '[Parent] Received captureResult but payload is not a Blob:',
              message.payload
            );
            onCaptureError?.('截图失败：内部通信错误。');
          }
        }
        // 处理 'captureError' 消息
        else if (message.type === 'captureError') {
          const errorMsg = message.payload?.error || '未知的截图错误。';
          console.error(`[Parent] Received captureError message: ${errorMsg}`);
          onCaptureError?.('截图失败：请稍后重试或联系支持。');
        }
        // 处理 'requestTextModification' 消息
        else if (message.type === 'requestTextModification') {
          console.log('[Parent] Received text modification request with payload:', message.payload);
          // 使用引用访问最新的回调函数
          const currentOnRequestTextModification = onRequestTextModificationRef.current;

          if (typeof currentOnRequestTextModification === 'function') {
            try {
              // 解析有效载荷中的操作和新文本
              const {
                selectedText = '',
                action = '',
                newText = selectedText,
              } = message.payload || {};

              // 将操作和新文本组合成指令
              const instruction = `${action}: ${newText}`;

              currentOnRequestTextModification({
                selectedText,
                instruction,
              });
            } catch (error) {
              console.error('[Parent] Error calling onRequestTextModification:', error);
            }
          } else {
            console.warn('[Parent] onRequestTextModification is not a function or is missing.');
          }
        }
      };

      // 添加消息监听器
      window.addEventListener('message', handleIframeMessage);

      // 清理函数 - 组件卸载时执行
      return () => {
        window.removeEventListener('message', handleIframeMessage); // 移除合并的监听器
        if (iframeRef.current) {
          iframeRef.current.contentWindow?.postMessage({ type: 'cleanup' }, '*');
          iframeRef.current.remove();
          iframeRef.current = null;
        }
        isIframeReady.current = false;
      };
    }, [
      globalStyleCode,
      sendContentUpdate,
      themeBackgroundColor,
      themeTextColor,
      onCaptureError,
      isEditMode,
      onRequestTextModification,
    ]);

    /**
     * 效果 2: 当属性变化时发送内容更新（初始挂载后）
     */
    useEffect(() => {
      if (isIframeReady.current) {
        sendContentUpdate();
      }
    }, [sendContentUpdate]); // 依赖确保当 sendContentUpdate 变化时此效果运行

    // 渲染 iframe 容器
    return (
      <div
        id="iframe-container"
        className="w-full h-full relative z-[1]"
      />
    );
  }
);

// 添加显示名称，便于调试
SandboxFrame.displayName = 'SandboxFrame';

// 导出包装后的组件
export default SandboxFrame;
