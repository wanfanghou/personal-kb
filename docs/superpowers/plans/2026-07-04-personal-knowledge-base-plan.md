# 个人知识库网站实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 VitePress 搭建个人知识库网站，包含五大板块、标签系统、GitHub Actions 自动部署到 GitHub Pages。

**Architecture:** VitePress 静态站点，侧边栏按文件夹层级生成导航，每篇文章通过 frontmatter 声明标签，`tags.md` 页面通过 VitePress data loader 聚合所有标签。GitHub Actions 在推送时自动构建部署。

**Tech Stack:** VitePress, Vue 3, Markdown, GitHub Pages, GitHub Actions

## Global Constraints

- 仓库地址：`https://github.com/wanfanghou`，仓库名待确认
- 全中文内容
- 五大板块：个人介绍、科研项目、创业项目、生活记录、个人知识库
- 每个 .md 文件必须包含 `title`、`tags`、`created` frontmatter
- 标签系统：文件夹层级 + frontmatter tags 双维度

---

### Task 1: 初始化 VitePress 项目

**Files:**
- Create: `package.json`
- Create: `docs/.vitepress/config.mts`
- Create: `docs/index.md`
- Create: `.gitignore`

**Interfaces:**
- Produces: VitePress 项目骨架，`package.json` 含 vitepress 依赖和 scripts

- [ ] **Step 1: 创建 package.json**

```json
{
  "name": "personal-knowledge-base",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "docs:dev": "vitepress dev docs",
    "docs:build": "vitepress build docs",
    "docs:preview": "vitepress preview docs"
  },
  "devDependencies": {
    "vitepress": "^1.6.0"
  }
}
```

- [ ] **Step 2: 创建 VitePress 配置**

文件：`docs/.vitepress/config.mts`

```typescript
import { defineConfig } from 'vitepress'

export default defineConfig({
  title: '个人知识库',
  description: '知识、项目与生活记录',
  lang: 'zh-CN',
  cleanUrls: true,
  lastUpdated: true,

  themeConfig: {
    nav: [
      { text: '首页', link: '/' },
      { text: '个人介绍', link: '/about/' },
      { text: '科研项目', link: '/research/' },
      { text: '创业项目', link: '/startup/' },
      { text: '生活记录', link: '/life/' },
      { text: '个人知识库', link: '/kb/' },
      { text: '标签', link: '/tags' },
    ],

    sidebar: {
      '/about/': [
        {
          text: '个人介绍',
          items: [{ text: '关于我', link: '/about/' }],
        },
      ],
      '/research/': [
        {
          text: '科研项目',
          items: [],
        },
      ],
      '/startup/': [
        {
          text: '创业项目',
          items: [],
        },
      ],
      '/life/': [
        {
          text: '生活记录',
          items: [],
        },
      ],
      '/kb/': [
        {
          text: '个人知识库',
          items: [
            {
              text: '生活经验',
              collapsed: false,
              items: [
                {
                  text: '新加坡',
                  collapsed: false,
                  items: [
                    { text: '常用电话', link: '/kb/life-tips/singapore/phone-numbers' },
                    { text: '自行车导航', link: '/kb/life-tips/singapore/cycling-nav' },
                    { text: 'SingPass', link: '/kb/life-tips/singapore/singpass' },
                    { text: '法律注意事项', link: '/kb/life-tips/singapore/laws' },
                  ],
                },
              ],
            },
            {
              text: '学习资料',
              items: [],
            },
          ],
        },
      ],
    },

    search: {
      provider: 'local',
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/wanfanghou' },
    ],
  },
})
```

- [ ] **Step 3: 创建首页**

文件：`docs/index.md`

```markdown
---
layout: home

hero:
  name: 个人知识库
  text: 知识、项目与生活
  tagline: 记录所学、所做、所感
  actions:
    - theme: brand
      text: 个人介绍
      link: /about/
    - theme: alt
      text: 知识库
      link: /kb/

features:
  - title: 科研项目
    details: 学术研究记录
    link: /research/
  - title: 创业项目
    details: AI 创业实践
    link: /startup/
  - title: 生活记录
    details: 旅行与日常
    link: /life/
---
```

- [ ] **Step 4: 创建 .gitignore**

```
node_modules/
.vitepress/dist/
.vitepress/cache/
```

- [ ] **Step 5: 安装依赖并验证**

```bash
npm install
npm run docs:dev
```

Expected: 开发服务器启动，访问 `http://localhost:5173` 看到首页。

- [ ] **Step 6: 提交**

```bash
git add package.json package-lock.json .gitignore docs/
git commit -m "feat: init VitePress project with site structure and navigation"
```

---

### Task 2: 创建五大板块页面

**Files:**
- Create: `docs/about/index.md`
- Create: `docs/research/index.md`
- Create: `docs/startup/index.md`
- Create: `docs/life/index.md`
- Create: `docs/kb/index.md`
- Create: `docs/kb/learning/index.md`

**Interfaces:**
- Produces: 五个占位页面，侧边栏导航可点击跳转

- [ ] **Step 1: 创建个人介绍页面**

`docs/about/index.md`:

```markdown
# 个人介绍

> 基本信息待补充
```

- [ ] **Step 2: 创建科研项目页面**

`docs/research/index.md`:

```markdown
# 科研项目

> 学术科研项目记录
```

- [ ] **Step 3: 创建创业项目页面**

`docs/startup/index.md`:

```markdown
# 创业项目

> AI 创业相关项目
```

- [ ] **Step 4: 创建生活记录页面**

`docs/life/index.md`:

```markdown
# 生活记录

> 旅行日志、生活见闻
```

- [ ] **Step 5: 创建知识库页面**

`docs/kb/index.md`:

```markdown
# 个人知识库

## 生活经验

- [新加坡](/kb/life-tips/singapore/)

## 学习资料

> 待补充
```

- [ ] **Step 6: 创建学习资料占位页**

`docs/kb/learning/index.md`:

```markdown
# 学习资料

> 待补充
```

- [ ] **Step 7: 验证**

```bash
npm run docs:dev
```

Expected: 导航栏全部链接可点击，侧边栏结构正确。

- [ ] **Step 8: 提交**

```bash
git add docs/
git commit -m "feat: add five section placeholder pages"
```

---

### Task 3: 写入新加坡四篇文章

**Files:**
- Create: `docs/kb/life-tips/singapore/phone-numbers.md`
- Create: `docs/kb/life-tips/singapore/cycling-nav.md`
- Create: `docs/kb/life-tips/singapore/singpass.md`
- Create: `docs/kb/life-tips/singapore/laws.md`

**Interfaces:**
- Produces: 四篇含完整内容、frontmatter 的 Markdown 文章

- [ ] **Step 1: 创建常用电话页面**

`docs/kb/life-tips/singapore/phone-numbers.md`:

```markdown
---
title: 新加坡常用电话号码
tags: [新加坡, 生活, 电话]
created: 2026-07-04
---

# 新加坡常用电话号码

## 紧急电话

| 用途 | 号码 |
|------|------|
| 意外报警（普通） | 999 |
| 意外报警（海事） | 6325 2488 |
| 火警 / 紧急救护车 | 995 |
| 非紧急救护车 | 1777 |
| 传染病通报 | 6731 9757 |
| 交通事故报告 | 6547 6242 / 6547 6243 |
| 中国领事馆 | 65-64750165 |
| NUS 校园安全保卫处 | 65-68741616 |

## 生活热线

| 用途 | 号码 |
|------|------|
| 机场航班咨询 | 6542 4422 / 6541 2302 |
| 电话号码查询 | 1900-777-7777 |
| 新冠病毒通报 | 1800-333-9999 |
| 一般民众求助 | 1800-286-5555 |
| 火灾隐患报告 | 1800-280-0000 |

## 投诉热线

| 用途 | 号码 |
|------|------|
| 消费者协会 | 6100 0315 |
| 反诈骗 | 1800-722-6688 |
| 旅游局旅客专线 | 1800-736-2000 |
| 人力部维权 | 1800-221-9922 |
```

- [ ] **Step 2: 创建自行车导航页面**

`docs/kb/life-tips/singapore/cycling-nav.md`:

```markdown
---
title: 新加坡谷歌地图自行车导航
tags: [新加坡, 出行, 骑行]
created: 2026-07-04
---

# 新加坡谷歌地图自行车导航

新加坡是东南亚首个推出谷歌地图自行车导航功能的国家。

## 功能介绍

覆盖 **6800 公里** 的骑行导航路线，连接新加坡各大自然公园、自然绿道和自行车专属道。

## 使用方式

1. 打开谷歌地图，输入目的地
2. 点击 🚴‍♂️ 自行车图标
3. 即可查看骑行路线
```

- [ ] **Step 3: 创建 SingPass 页面**

`docs/kb/life-tips/singapore/singpass.md`:

```markdown
---
title: SingPass 是什么？
tags: [新加坡, 行政, 生活]
created: 2026-07-04
---

# SingPass 是什么？

SingPass 被称为"新加坡电子身份证"，是登录新加坡各政府网站的统一认证工具。

## 谁需要 SingPass？

新加坡人、永久居民、家属准证持有者、工作准证持有者、学生准证持有者，几乎人手一个。

## 主要功能

- 接收政府重要通知（身份证重新登记、护照更新等）
- 作为数字身份（NRIC 号码或 FIN 号码）
- 安全登录政府及私营部门服务平台
- **申请 PR 必备**

> 来源：[gov.sg](https://www.gov.sg)
```

- [ ] **Step 4: 创建法律注意事项页面**

`docs/kb/life-tips/singapore/laws.md`:

```markdown
---
title: 新加坡法律注意事项
tags: [新加坡, 法律, 生活]
created: 2026-07-04
---

# 新加坡法律注意事项

## 地铁站交易违法

在地铁站进行二手物品交易属于违法行为，被查到罚款 **2000 新币**。

陆路交通管理局规定：任何大型货物或危险物品均不可使用地铁服务运输。

## 禁止随意喂野生动物

随意投喂野猪、猴子、鸟类等均属违法。曾有案例因公开喂猪被罚款 **300 新币**。

## 禁止蹭网

根据《滥用电脑法令》，未经许可使用他人 Wi-Fi 最高可判 **3 年** 监禁。

2006 年，一名 17 岁新加坡少年因蹭邻居 Wi-Fi 被判 **18 个月缓刑** 和 **80 小时社区服务**。
```

- [ ] **Step 5: 验证页面可访问**

```bash
npm run docs:dev
```

Expected: 通过侧边栏导航到四篇文章，内容正确显示。

- [ ] **Step 6: 提交**

```bash
git add docs/kb/
git commit -m "feat: add Singapore knowledge base articles"
```

---

### Task 4: 实现标签聚合系统

**Files:**
- Create: `docs/tags.data.ts`
- Create: `docs/tags.md`

**Interfaces:**
- Consumes: 所有 .md 文件中的 `tags` frontmatter
- Produces: `/tags` 页面，按标签分组展示所有文章链接

- [ ] **Step 1: 创建标签数据加载器**

`docs/tags.data.ts`:

```typescript
import { createContentLoader } from 'vitepress'

interface TaggedPost {
  title: string
  url: string
  tags: string[]
  created: string
}

interface TagData {
  tags: Record<string, TaggedPost[]>
}

export default createContentLoader('**/*.md', {
  includeSrc: false,
  render: false,
  excerpt: false,
  transform(raw): TagData {
    const tagMap: Record<string, TaggedPost[]> = {}

    for (const page of raw) {
      const tags: string[] = page.frontmatter?.tags ?? []
      const title: string = page.frontmatter?.title ?? page.url

      if (tags.length === 0) continue

      for (const tag of tags) {
        if (!tagMap[tag]) {
          tagMap[tag] = []
        }
        tagMap[tag].push({
          title,
          url: page.url,
          tags,
          created: page.frontmatter?.created ?? '',
        })
      }
    }

    return { tags: tagMap }
  },
})
```

- [ ] **Step 2: 创建标签聚合页面**

`docs/tags.md`:

```markdown
---
title: 标签
---

<script setup>
import { data } from './tags.data.ts'

// 按标签名排序
const sortedTags = Object.keys(data.tags).sort()
</script>

# 标签

<div v-for="tag in sortedTags" :key="tag" style="margin-bottom: 2rem;">
  <h2 :id="tag">{{ tag }}</h2>
  <ul>
    <li v-for="post in data.tags[tag]" :key="post.url">
      <a :href="post.url">{{ post.title }}</a>
      <span style="color: #888; font-size: 0.85em;" v-if="post.created">
        — {{ post.created }}
      </span>
    </li>
  </ul>
</div>
```

- [ ] **Step 3: 更新 VitePress 配置，注册标签导航**

修改 `docs/.vitepress/config.mts`，确认 nav 中已有 `{ text: '标签', link: '/tags' }`（Task 1 已添加）。

- [ ] **Step 4: 验证标签页面**

```bash
npm run docs:dev
```

Expected: 访问 `/tags`，看到所有标签分组（新加坡、生活、电话、出行、骑行、行政、法律），每组下有对应文章链接。

- [ ] **Step 5: 提交**

```bash
git add docs/tags.data.ts docs/tags.md
git commit -m "feat: add tag aggregation system"
```

---

### Task 5: 配置 GitHub Actions 自动部署

**Files:**
- Create: `.github/workflows/deploy.yml`

**Interfaces:**
- Consumes: `npm run docs:build` 构建产物
- Produces: 推送到 GitHub Pages，网站上线

- [ ] **Step 1: 创建部署工作流**

`.github/workflows/deploy.yml`:

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: npm ci

      - name: Build
        run: npm run docs:build

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: docs/.vitepress/dist

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: 更新 .gitignore**

确保 `.gitignore` 包含 `.vitepress/dist/` 和 `.vitepress/cache/`（Task 1 已添加）。

- [ ] **Step 3: 提交**

```bash
git add .github/workflows/deploy.yml
git commit -m "feat: add GitHub Actions deploy workflow"
```

---

### Task 6: 创建 GitHub 仓库并推送

- [ ] **Step 1: 初始化 Git 仓库**

```bash
cd "D:\01_OneDrive\OneDrive\000_personal website"
git init
git add -A
git commit -m "feat: initial commit - personal knowledge base"
```

- [ ] **Step 2: 确认仓库名**

询问用户仓库名。如果取 `personal-kb`，则网站地址为 `https://wanfanghou.github.io/personal-kb/`。

- [ ] **Step 3: 在 GitHub 创建仓库并推送**

```bash
git remote add origin https://github.com/wanfanghou/<repo-name>.git
git branch -M main
git push -u origin main
```

- [ ] **Step 4: 在 GitHub 仓库 Settings → Pages 中确认 Source 为 GitHub Actions**

手动步骤：GitHub 仓库页面 → Settings → Pages → Source 选择 "GitHub Actions"。

- [ ] **Step 5: 等待 Actions 运行完成，验证网站可访问**

访问 `https://wanfanghou.github.io/<repo-name>/`，确认网站上线。

Expected: 首页、五大板块、新加坡文章、标签页全部正常显示。
```

