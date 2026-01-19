export const baseStyles = `
  :root {
    --scrollbar-color: rgba(0, 0, 0, 0.12);
    --scrollbar-hover-color: rgba(0, 0, 0, 0.2); /* This will be used by scrollbarStyles.ts if --theme-scrollbar-thumb-hover is not set */
    --scrollbar-width: 3px; /* Set to 3px for WebKit, used by scrollbarStyles.ts */
    --content-padding: 0px;
    /* --scrollbar-color will be effectively overridden by var(--theme-scrollbar-thumb) in scrollbarStyles.ts */
  }

  @media (prefers-color-scheme: dark) {
    :root {
      --scrollbar-color: rgba(255, 255, 255, 0.12);
      --scrollbar-hover-color: rgba(255, 255, 255, 0.2);
    }
  }

  html {
    scroll-behavior: smooth;
    width: 100%;
    height: 100%;
  }
  
  body {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    width: 100%;
    height: 100%;
    /* overflow: hidden; -- REMOVED to allow body to not clip content */
    font-family: 'Arial', sans-serif;
    font-size: 14px;
    user-select: text !important; /* Ensure text is selectable */
    cursor: auto !important; /* Ensure cursor is visible */
  }

  /* Basic wrapper styles, height will be set by JS */
  .slide-content-wrapper {
    display: flex; /* 改为 flex 布局 */
    flex-direction: column; /* 纵向排列子元素 */
    justify-content: center; /* 垂直居中 */
    align-items: center; /* 水平居中 */
    width: 100%; 
    overflow-y: auto; /* Enable vertical scrolling */
    overflow-x: hidden; /* Prevent horizontal scrolling */
    padding: var(--content-padding, 16px); /* Add padding, default 16px */
    box-sizing: border-box; /* Include padding in element's total width and height */
    /* Scrollbar styles for .slide-content-wrapper are now handled globally by scrollbarStyles.ts */
    /* Removing specific styles from here to avoid conflicts */
  }

  /* 确保内部元素可以占据整个宽度 */
  .slide-content-wrapper > * {
    width: 100%;
  }

  /* Ensure section itself doesn't interfere */
  #slide-content-section {
    overflow: visible !important; /* Allow child .slide-content-wrapper to show its scrollbar */
  }

  /* 作为后备方案，隐藏可能遗留的 Reveal.js 辅助元素 */
  .reveal .backgrounds {
    pointer-events: none !important;  /* 允许点击穿透 */
    visibility: hidden !important;
  }
  
  /* 确保内容区域可以正常交互 */
  .reveal .slides {
    pointer-events: auto !important;
  }
  
  .reveal .slides section {
    pointer-events: auto !important;
  }
`;
