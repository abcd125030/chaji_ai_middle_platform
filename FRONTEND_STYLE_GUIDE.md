# 前端风格设计说明文档

## 设计理念

本项目采用现代化的深色主题设计风格，灵感来源于Next.js官网的设计语言。通过高对比度的黑白配色体系，营造专业、简洁、技术感强的视觉体验。

## 禁止使用硬编码色值
必须使用css里预定义的颜色变量！

## 核心配色方案

### 基础色板

#### 背景色系
- **主背景色**: `#000000` - 纯黑背景，营造深邃的视觉层次
- **次级背景色**: `#0A0A0A` - 用于卡片、按钮等元素的深色背景
- **高亮背景色**: `#1A1A1A` - 用于悬停状态或选中状态

#### 文本色系
- **主文本色**: `#FFFFFF` - 标题和重要内容
- **次级文本色**: `#ADADAD` - 描述性文字和次要信息
- **辅助文本色**: `#888888` - 提示文字、时间戳等辅助信息

#### 交互色系
- **主按钮背景**: `#EDEDED` - 高亮度按钮背景
- **主按钮文本**: `#0A0A0A` - 与浅色背景形成对比
- **次级按钮边框**: `#EDEDED` - 轮廓按钮边框色
- **次级按钮背景**: `#0A0A0A` - 深色背景
- **次级按钮文本**: `#EDEDED` - 浅色文本

### 特殊效果

#### 渐变色
- **标题渐变**: `linear-gradient(180deg, #FFFFFF 0%, #ADADAD 100%)`
  - 用于大标题文字，创造动态视觉焦点
  - 应用于hero区域的主标题

## 组件样式规范

### 按钮组件

#### 主按钮 (Primary Button)
```css
background-color: #EDEDED;
color: #0A0A0A;
border: 2px solid #0A0A0A;
border-radius: 8px;
padding: 12px 24px;
font-weight: 500;
transition: all 0.2s ease;
```

#### 次级按钮 (Secondary Button)
```css
background-color: #0A0A0A;
color: #EDEDED;
border: 1px solid #EDEDED;
border-radius: 8px;
padding: 12px 24px;
font-weight: 400;
transition: all 0.2s ease;
```

### 卡片组件
```css
background-color: #0A0A0A;
border: 1px solid #1A1A1A;
border-radius: 12px;
padding: 24px;
transition: border-color 0.2s ease;
```

### 输入框组件
```css
background-color: #0A0A0A;
color: #FFFFFF;
border: 1px solid #1A1A1A;
border-radius: 6px;
padding: 10px 16px;
transition: border-color 0.2s ease;
```

## 排版规范

### 字体系统
- **主字体**: system-ui, -apple-system, sans-serif
- **代码字体**: 'SF Mono', Monaco, monospace

### 字体大小
- **超大标题**: 72px (4.5rem)
- **大标题**: 48px (3rem)
- **中标题**: 32px (2rem)
- **小标题**: 24px (1.5rem)
- **正文**: 16px (1rem)
- **小字**: 14px (0.875rem)
- **辅助文字**: 12px (0.75rem)

### 字重
- **粗体**: 700
- **中等**: 500
- **常规**: 400
- **细体**: 300

## 间距系统

采用8px基础单位的间距系统：
- **xs**: 4px (0.25rem)
- **sm**: 8px (0.5rem)
- **md**: 16px (1rem)
- **lg**: 24px (1.5rem)
- **xl**: 32px (2rem)
- **2xl**: 48px (3rem)
- **3xl**: 64px (4rem)

## 动画与过渡

### 过渡时长
- **快速**: 150ms
- **标准**: 200ms
- **缓慢**: 300ms

### 缓动函数
- **标准缓动**: ease
- **进入缓动**: ease-out
- **退出缓动**: ease-in
- **弹性缓动**: cubic-bezier(0.4, 0, 0.2, 1)

## 响应式断点

```css
/* 移动设备 */
@media (max-width: 640px) { }

/* 平板设备 */
@media (min-width: 641px) and (max-width: 1024px) { }

/* 桌面设备 */
@media (min-width: 1025px) and (max-width: 1440px) { }

/* 大屏幕 */
@media (min-width: 1441px) { }
```

## 深色模式适配

本设计默认为深色模式，但需要考虑以下适配原则：
1. 保持高对比度，确保可读性
2. 避免纯白色（#FFFFFF）大面积使用，采用略微偏灰的白色（#FAFAFA）
3. 使用细微的阴影和边框来区分层级

## 无障碍设计

1. **对比度要求**：
   - 普通文本：至少4.5:1
   - 大文本：至少3:1
   - 交互元素：至少3:1

2. **焦点状态**：
   - 所有可交互元素必须有明确的焦点样式
   - 使用`outline: 2px solid #EDEDED`作为焦点指示

3. **键盘导航**：
   - 支持Tab键导航
   - 使用语义化HTML标签

## 图标使用规范

1. **图标库**: 使用@heroicons/react
2. **图标大小**:
   - 小图标: 16px
   - 中图标: 20px
   - 大图标: 24px
3. **图标颜色**: 继承父元素文本颜色

## 实施指南

### Tailwind CSS配置

```javascript
// tailwind.config.js 示例配置
module.exports = {
  theme: {
    extend: {
      colors: {
        background: '#000000',
        'background-secondary': '#0A0A0A',
        'background-hover': '#1A1A1A',
        'text-primary': '#FFFFFF',
        'text-secondary': '#ADADAD',
        'text-muted': '#888888',
        'button-primary': '#EDEDED',
        'button-text': '#0A0A0A',
        'border-primary': '#EDEDED',
        'border-secondary': '#1A1A1A',
      },
      backgroundImage: {
        'gradient-title': 'linear-gradient(180deg, #FFFFFF 0%, #ADADAD 100%)',
      },
    },
  },
}
```

### CSS变量定义

```css
:root {
  --color-background: #000000;
  --color-background-secondary: #0A0A0A;
  --color-background-hover: #1A1A1A;
  --color-text-primary: #FFFFFF;
  --color-text-secondary: #ADADAD;
  --color-text-muted: #888888;
  --color-button-primary: #EDEDED;
  --color-button-text: #0A0A0A;
  --color-border-primary: #EDEDED;
  --color-border-secondary: #1A1A1A;
}
```

## 组件示例

### Hero Section
```jsx
<section className="bg-black text-white">
  <h1 className="text-7xl font-bold bg-gradient-to-b from-white to-[#ADADAD] bg-clip-text text-transparent">
    The React Framework for the Web
  </h1>
  <p className="text-[#888888] text-lg">
    Build great products with Next.js
  </p>
</section>
```

### Button Component
```jsx
// 主按钮
<button className="bg-[#EDEDED] text-[#0A0A0A] px-6 py-3 rounded-lg font-medium border-2 border-[#0A0A0A] hover:opacity-90 transition-opacity">
  Get Started
</button>

// 次级按钮
<button className="bg-[#0A0A0A] text-[#EDEDED] px-6 py-3 rounded-lg font-medium border border-[#EDEDED] hover:bg-[#1A1A1A] transition-colors">
  Learn More
</button>
```

## 最佳实践

1. **保持一致性**: 严格遵循配色方案，避免随意添加新颜色
2. **层级分明**: 使用不同的背景色和边框色创建视觉层次
3. **适度留白**: 充分利用间距系统，避免内容拥挤
4. **渐进增强**: 先确保基础功能，再添加视觉效果
5. **性能优先**: 避免过度使用动画和特效

## 更新日志

- **2025-08-28**: 初始版本，基于Next.js官网设计语言创建

---

本文档为前端开发的统一风格指南，所有UI组件和页面设计应严格遵循此规范。