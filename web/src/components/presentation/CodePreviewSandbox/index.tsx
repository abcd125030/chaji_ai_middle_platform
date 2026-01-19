/**
 * CodePreviewSandbox component - Tailwind version
 *
 * This is a code preview sandbox component for rendering and previewing HTML, CSS and JavaScript code in a secure environment.
 * The component supports fullscreen mode, download functionality, and interactive communication with sandbox content.
 */
import React, { useEffect, useState, useRef, useCallback } from 'react';
import SandboxFrame from './SandboxFrame';
import FullscreenControl from './FullscreenControl';
import DownloadControl from './DownloadControl';
import { SandboxFrameRef, SandboxMessage } from './types';

// Define component interface properties
interface CodePreviewSandboxProps {
  htmlContent: string; // HTML content
  cssContent: string; // CSS content
  jsContent: string; // JavaScript content
  globalStyleCode?: string; // Optional global style code
  mermaidContent?: string; // Optional Mermaid chart content
  isFullscreen?: boolean; // Whether in fullscreen mode
  showFullscreenControl?: boolean; // Whether to show fullscreen control button
  showDownloadControl?: boolean; // 是否显示下载控制按钮
  downloadTargetId?: string; // iframe 内部需要下载的元素 ID
  userRole?: string; // 用户角色，决定某些功能的可用性
  onHtmlChange?: (newHtml: string) => void; // HTML 内容变化时的回调函数
  onRequestTextModification?: (payload: {
    selectedText: string; // 被选中的文本
    instruction: string; // 修改指令
  }) => Promise<void>; // 请求文本修改的回调函数
  isEditMode?: boolean; // 是否处于编辑模式
}

/**
 * CodePreviewSandbox 组件实现
 * 使用 React.forwardRef 以支持引用传递，允许父组件访问内部方法
 */
const CodePreviewSandbox = React.forwardRef<SandboxFrameRef, CodePreviewSandboxProps>(
  (
    {
      htmlContent,
      cssContent,
      jsContent,
      globalStyleCode,
      mermaidContent,
      isFullscreen: externalIsFullscreen,
      showFullscreenControl = true,
      showDownloadControl = true, // 下载按钮默认显示
      downloadTargetId = 'capture-target', // 默认下载目标ID
      userRole = 'user', // 默认用户角色
      onHtmlChange, // HTML变更回调
      onRequestTextModification, // 文本修改请求回调
      isEditMode = false, // 编辑模式标志，默认为false
    },
    ref
  ) => {
    const [internalIsFullscreen, setInternalIsFullscreen] = useState(false); // 内部全屏状态
    const [captureError, setCaptureError] = useState<string | null>(null); // 捕获错误状态
    const sandboxFrameRef = useRef<SandboxFrameRef>(null); // SandboxFrame组件的引用

    // 将外部传入的ref转发到内部sandboxFrameRef，暴露组件方法
    React.useImperativeHandle(
      ref,
      () => ({
        // 请求捕获指定元素的方法
        requestCapture: (elementId: string) => {
          sandboxFrameRef.current?.requestCapture(elementId);
        },
        // 向沙盒发送消息的方法
        sendMessage: (message: SandboxMessage) => {
          sandboxFrameRef.current?.sendMessage(message);
        },
      }),
      []
    );

    // 监听浏览器全屏状态变化
    useEffect(() => {
      const handleFullscreenChange = () => {
        setInternalIsFullscreen(!!document.fullscreenElement);
      };
      document.addEventListener('fullscreenchange', handleFullscreenChange);
      // 组件卸载时移除事件监听器
      return () => {
        document.removeEventListener('fullscreenchange', handleFullscreenChange);
      };
    }, []);

    // 使用外部传入的全屏状态或内部状态
    // 如果外部传入了全屏状态，则使用外部状态；否则使用内部状态
    const isFullscreen =
      externalIsFullscreen !== undefined ? externalIsFullscreen : internalIsFullscreen;

    // 处理下载按钮点击事件
    const handleDownloadClick = () => {
      setCaptureError(null); // 清除之前的错误
      console.log(`[Index] Requesting capture for ID: ${downloadTargetId}`);
      // 调用沙盒框架的捕获方法
      sandboxFrameRef.current?.requestCapture(downloadTargetId);
    };

    // 处理从SandboxFrame组件捕获的错误 - 使用useCallback优化性能
    const handleCaptureError = useCallback((error: string) => {
      setCaptureError(error);
    }, []); // 空依赖数组，因为它只使用setCaptureError函数

    // 处理错误提示关闭事件
    const handleCloseSnackbar = () => {
      setCaptureError(null);
    };

    // 获取主题颜色（使用CSS变量）
    const themeBackgroundColor = 'var(--background)';
    const themeTextColor = 'var(--foreground)';

    return (
      <div
        id="preview-container"
        className={`
          relative flex flex-col w-full h-full
          ${isFullscreen ? 'rounded-none' : 'rounded-md'}
          shadow-md hover:shadow-lg
          transition-all duration-200 ease-in-out
        `}
        style={{
          backgroundColor: isFullscreen ? 'var(--code-bg)' : 'var(--background)',
        }}
      >
        {/* SandboxFrame包装器，允许其在flex布局中占据空间 */}
        <div className="flex-1 relative min-h-0 w-full">
          <SandboxFrame
            ref={sandboxFrameRef} // 传递引用
            htmlContent={htmlContent}
            cssContent={cssContent}
            jsContent={jsContent}
            globalStyleCode={globalStyleCode}
            mermaidContent={mermaidContent}
            themeBackgroundColor={themeBackgroundColor}
            themeTextColor={themeTextColor}
            onCaptureError={handleCaptureError} // 传递错误处理函数
            isEditMode={isEditMode} // 传递编辑模式标志
            onRequestTextModification={onRequestTextModification} // 传递文本修改请求回调
            onHtmlChange={onHtmlChange} // 传递HTML变更回调
          />
        </div>
        
        {/* 控制按钮容器 */}
        <div className="absolute bottom-2.5 right-2.5 z-10 flex flex-row gap-2 pointer-events-none">
          {/* 仅当showDownloadControl为true且用户角色不是普通用户时显示下载控制按钮 */}
          {showDownloadControl && userRole !== 'user' && (
            <DownloadControl onClick={handleDownloadClick} />
          )}
          {/* 仅当showFullscreenControl为true时显示全屏控制按钮 */}
          {showFullscreenControl && (
            <FullscreenControl
              isFullscreen={isFullscreen}
              // 如果外部控制全屏状态，则不改变内部状态；否则更新内部状态
              onFullscreenChange={
                externalIsFullscreen !== undefined ? (_state) => {} : setInternalIsFullscreen
              }
            />
          )}
        </div>

        {/* 错误提示 */}
        {captureError && (
          <div className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50">
            <div className="bg-red-500 text-white px-4 py-2 rounded-md shadow-lg flex items-center gap-2">
              <span>{captureError}</span>
              <button
                onClick={handleCloseSnackbar}
                className="ml-2 hover:opacity-80"
              >
                ✕
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }
);

// 设置组件显示名称，有助于React开发工具中的调试
CodePreviewSandbox.displayName = 'CodePreviewSandbox';
export default CodePreviewSandbox;