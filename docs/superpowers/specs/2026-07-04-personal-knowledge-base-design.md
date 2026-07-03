# 个人知识库网站设计文档

## 概述

基于 VitePress 的个人知识库网站，托管在 GitHub Pages 上。内容分为五大板块，通过文件夹层级导航和标签系统双维度组织。

## 技术栈

- **静态站点生成器：** VitePress
- **托管：** GitHub Pages（GitHub Actions 自动部署）
- **内容格式：** Markdown + YAML frontmatter
- **搜索：** VitePress 内置本地搜索

## 五大板块

| 板块 | 路由 | 内容 |
|---------|-------|---------|
| 个人介绍 | `/about/` | 基本信息、简介、联系方式 |
| 科研项目 | `/research/` | 学术科研项目 |
| 创业项目 | `/startup/` | AI 创业相关项目 |
| 生活记录 | `/life/` | 旅行日志、生活见闻 |
| 个人知识库 | `/kb/` | 学习资料、生活经验 |

## 目录结构

```
docs/
├── index.md                    # 首页
├── about/
│   └── index.md                # 个人介绍
├── research/
│   └── ...
├── startup/
│   └── ...
├── life/
│   ├── travel/
│   └── ...
├── kb/
│   ├── life-tips/              # 生活经验
│   │   └── singapore/
│   │       ├── phone-numbers.md #   常用电话
│   │       ├── cycling-nav.md   #   自行车导航
│   │       ├── singpass.md      #   SingPass 介绍
│   │       └── laws.md          #   法律注意事项
│   └── learning/               # 学习资料
│       └── ...
└── tags.md                     # 标签聚合页
```

## 双维度组织系统

### 1. 文件夹层级

侧边栏导航与目录结构一一对应，每个板块有独立的侧边栏配置，像书本目录一样浏览。

### 2. 标签系统

每篇文章通过 frontmatter 声明标签：

```yaml
---
title: 新加坡常用电话号码
tags: [新加坡, 生活, 电话]
created: 2026-07-04
---
```

`/tags.md` 标签聚合页按标签汇总所有文章，支持跨主题检索。

## VitePress 配置要点

- 默认主题，每个板块自定义侧边栏
- 内置本地搜索
- 开启 Clean URLs
- 显示最后更新时间

## 文章页面布局

每篇文章包含以下要素：
- 文章标题
- 标签（可点击跳转对应标签页）
- 创建日期
- 自动生成的目录（基于标题层级）
- 正文内容

## 部署方式

- GitHub 创建仓库
- GitHub Actions 在推送到 main 分支时自动 `vitepress build`
- 部署产物发布到 GitHub Pages

## 内容发布流程

1. 本地编辑 `.md` 文件
2. `git push` 推送到 GitHub
3. GitHub Actions 自动构建部署

## 后续可扩展

- 评论系统（Giscus）
- 全文搜索增强
- RSS 订阅
