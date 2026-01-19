// 文件说明：此文件定义了沙盒组件相关的接口，用于约束沙盒内容、消息通信和回调函数的类型。

// 沙盒参数接口
export interface SandboxFrameProps {
  htmlContent: string;
  cssContent?: string;
  jsContent?: string;
  globalStyleCode?: string;
  mermaidContent?: string;
  themeBackgroundColor?: string;
  themeTextColor?: string;
  onCaptureError?: (error: string) => void; // 捕获错误时的回调函数
  isEditMode?: boolean; // 是否处于编辑模式
  onRequestTextModification?: (payload: {
    selectedText: string;
    instruction: string;
  }) => Promise<void>; // 请求文本修改时的回调函数
  onHtmlChange?: (html: string) => void; // HTML内容变化时的回调函数
}

// 通用消息接口，用于 postMessage 通信
export interface SandboxMessage {
  type: string;
  payload?: unknown; // 使用 unknown 代替 any
}

// 沙盒框架引用接口，提供外部调用方法
export interface SandboxFrameRef {
  requestCapture: (elementId: string) => void;
  sendMessage: (message: SandboxMessage) => void; // 发送消息的方法
}

// 清理回调函数接口
export interface CleanupFunction {
  (): void;
}
