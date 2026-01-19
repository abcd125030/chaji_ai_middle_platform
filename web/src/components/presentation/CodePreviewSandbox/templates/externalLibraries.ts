/**
 * 该文件用于配置外部库的链接和脚本，
 * 以便为代码预览沙盒动态加载所需资源。
 * 包括设置页面头部加载的 CSS/JS、以及定义动态加载库的 URL 等。
 */

// 获取basePath
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

export const headLibraries = `
  <link rel="stylesheet" href="${basePath}/vendor/revealjs/reveal.css" id="theme">
  <link rel="stylesheet" href="https://cdn.bootcdn.net/ajax/libs/font-awesome/6.7.2/css/all.min.css">
  <script src="https://cdn.tailwindcss.com"></script>
`;
// 注释：headLibraries 字符串中包含页面头部需要加载的 CSS 样式和 JavaScript，用于设置主题样式和加载 TailwindCSS。

// 定义库的 URL，用于在 iframe 内脚本动态加载各个外部库。
export const libraryUrls = {
  revealJs: `${basePath}/vendor/revealjs/reveal.js`,
  markedJs: `${basePath}/vendor/marked.min.js`,
  chartJs: `${basePath}/vendor/chart.umd.js`,
  fabricJs: `${basePath}/vendor/fabric.min.js`,
  momentJs: `${basePath}/vendor/moment-with-locales.min.js`,
  highlightJs: `${basePath}/vendor/highlight.min.js`,
  lodashJs: `${basePath}/vendor/lodash.min.js`,
  xlsxPopulateJs: `${basePath}/vendor/xlsx-populate.min.js`,
  mermaidJs: `${basePath}/vendor/mermaid.js`,
  domToImageJs: 'https://cdn.bootcdn.net/ajax/libs/dom-to-image/2.6.0/dom-to-image.min.js',
  fileSaverJs: 'https://cdn.bootcdn.net/ajax/libs/FileSaver.js/2.0.5/FileSaver.min.js', // 修正了 FileSaver 的 URL
  fontAwesomeCss: 'https://cdn.bootcdn.net/ajax/libs/font-awesome/6.7.2/css/all.min.css',
};

// bodyLibraries 字符串目前为空模板，用于提示 iframeScript.js 动态加载额外的库。
export const bodyLibraries = `
  <!-- iframeScript.js will dynamically load other libraries -->
`;