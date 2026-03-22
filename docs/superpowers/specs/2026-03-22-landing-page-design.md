# Jeff's Personal Landing Page — Design Spec

## Overview

个人品牌/作品集网站。展示 Jeff 是谁、在做什么项目。电影感沉浸式风格，纯静态实现。

## Design Decisions

| 决策 | 选择 | 备选 |
|------|------|------|
| 风格方向 | 电影感沉浸式 | Bento 卡片式、Terminal 黑客风 |
| 布局结构 | 全屏分段式 | 长卷轴流式、分屏对比式 |
| 动画风格 | 极简渐入 | 粒子光效、文字动态排版 |
| 技术栈 | 纯 HTML/CSS/JS | Next.js、Astro、Vite+React |

## Page Structure

4 个全屏板块，每屏一个信息焦点：

### 1. Hero

- 全屏深蓝黑渐变背景 (`#0a0a0a` → `#1a1a2e` → `#16213e`)
- 居中大字标题 "JEFF"，副标题 "FOUNDER · BUILDER · CREATOR"
- 几何装饰：半透明圆环、细线，缓慢漂移动画
- 底部 scroll indicator

### 2. About

- 深色背景 (`#0d0d15`)
- 居中排版，一句话定位 + 简短介绍
- 板块编号 "01 / ABOUT"
- 元素滚动渐入

### 3. Projects

- 深色背景 (`#0a0a12`)
- 项目卡片列表，每个卡片包含：项目名（品牌色）、简介、箭头链接
- 品牌色方案：FounderOS `#e2b340`（金）、Onta Network `#4ecdc4`（青）、FocalPoint `#a78bfa`（紫）
- 卡片 hover 时微微抬起 + 边框高亮

### 4. Contact

- 最深色背景 (`#080810`)
- "Let's Connect" 标题
- 社交链接胶囊按钮（GitHub、Twitter、Email）
- 按钮 hover 时边框亮度变化

### Navigation

- 固定顶部导航栏，毛玻璃背景 (`backdrop-filter: blur`)
- 左侧 Logo "JEFF"，右侧锚点链接

## Visual Design

### Color Palette

- 背景渐变：`#0a0a0a` → `#1a1a2e` → `#16213e`
- 文字主色：`#ffffff`（标题）、`rgba(255,255,255,0.45)`（正文）
- 辅助色：`rgba(255,255,255,0.15)`（板块编号、装饰）
- 品牌强调色：金 `#e2b340`、青 `#4ecdc4`、紫 `#a78bfa`

### Typography

- 标题：无衬线体，800 weight，负 letter-spacing
- 正文：400 weight，高行距 (1.6-1.8)
- 板块编号/标签：小字，大 letter-spacing，低透明度

### Animation

- **渐入效果：** 元素从 `opacity: 0; transform: translateY(20px)` 过渡到可见，用 Intersection Observer 触发
- **几何装饰：** CSS `@keyframes` 缓慢漂移/旋转
- **卡片交互：** `transition: all 0.3s ease`，hover 时 `translateY(-2px)` + 边框变亮
- **导航：** 滚动时背景透明度渐变

## Technical Implementation

### 文件结构

```
landing-page/
├── index.html
├── css/
│   └── style.css
├── js/
│   └── main.js
└── assets/
    └── (images if needed)
```

### Key Technical Points

- **零依赖：** 不使用任何框架或库
- **Scroll Snap：** `scroll-snap-type: y mandatory` 实现全屏翻页
- **Intersection Observer：** 检测元素进入视口，触发渐入动画
- **CSS Custom Properties：** 统一管理颜色、间距等设计 token
- **响应式：** Desktop 优先，media query 适配 tablet/mobile
- **性能：** 无外部字体加载（系统字体栈），无图片依赖

### Responsive Breakpoints

- Desktop: > 1024px（默认）
- Tablet: 768px - 1024px（缩小间距，调整字号）
- Mobile: < 768px（单列，导航改为汉堡菜单或隐藏）

## Non-Goals (v1)

- 博客/文章系统
- CMS 后台管理
- 多语言支持
- SEO 深度优化
- 自定义域名配置（部署方案待定）
