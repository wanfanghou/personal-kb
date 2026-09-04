# 学术谱系网络设计说明

## 目标

构建一个本地运行的导师—学生学术谱系工具。用户通过输入两位学者的个人主页 URL，确认谁是导师、谁是学生后，将两个学者加入本地图谱，并保存一条带来源、可信度和公开权限的关系。用户可以搜索任意学者，向上查看导师链，向下查看学生树；经过筛选的数据可以导出为静态文件并发布到 GitHub Pages。

## 范围

### 第一版包含

- 学者节点：姓名、主页、机构、研究方向、别名和公开权限。
- 导师—学生关系：导师、学生、关系类型、年份、机构、证据 URL、证据说明、状态和公开权限。
- 手动录入优先；仅在用户提交 URL 后读取网页标题和 meta 信息辅助识别姓名。
- 学者搜索、学者详情、导师链、学生树、图谱展开和关系详情。
- 双 URL 录入流程：预览身份 → 明确关系方向 → 确认写入。
- 草稿、已确认、已拒绝三种关系状态。
- 本地完整数据库和公开静态导出数据分离。
- GitHub Pages 静态展示公开数据。

### 第一版不包含

- 自动判断或自动导入导师—学生关系。
- 全文复制个人主页内容。
- 合作者、论文引用、机构网络等非谱系关系。
- 多用户账号、云端数据库、在线协作和评论系统。
- 将本地 SQLite 文件提交到公开 GitHub 仓库。

## 总体架构

```text
本地浏览器
    │
    ▼
academic-lineage/server.py
    │  HTTP API + 静态管理页面
    ▼
academic-lineage/data/network.sqlite

导出命令
    │  只选择 public=true 且 status=verified 的数据
    ▼
academic-lineage/public/data/*.json
    │
    ▼
GitHub Pages 静态谱系网站
```

项目使用独立目录，不修改现有个人网站的 `server.py`、`static/`、`docs/` 内容。第一版采用 Python 标准库 `sqlite3`、Flask 和原生 HTML/CSS/JavaScript；图谱使用 Cytoscape.js。SQLite 适合该个人本地工具，因为它是自包含且不需要独立数据库服务的数据库。公开站点不依赖 Python 服务，只读取构建后的 JSON。

## 数据模型

### `persons`

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | TEXT | UUID，主键 |
| `name` | TEXT | 必填，当前显示名 |
| `name_en` | TEXT | 可空 |
| `aliases_json` | TEXT | JSON 字符串数组 |
| `institution` | TEXT | 可空 |
| `field` | TEXT | 可空 |
| `title` | TEXT | 可空，当前职称/头衔（如 Professor、教授） |
| `editorial_roles_json` | TEXT | JSON 字符串数组，编委会任职 |
| `honors_json` | TEXT | JSON 字符串数组，荣誉/人才称号（如国家杰青） |
| `homepage_url` | TEXT | 必填，规范化 URL |
| `homepage_title` | TEXT | 可空，来自抓取预览 |
| `public` | INTEGER | 0/1，默认 0 |
| `notes_private` | TEXT | 可空，只存本地 |
| `created_at` | TEXT | ISO 8601 |
| `updated_at` | TEXT | ISO 8601 |

对 `homepage_url` 建立唯一索引。URL 规范化只移除片段、去除末尾多余斜杠并统一协议大小写，不改变路径语义。

### `mentorships`

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | TEXT | UUID，主键 |
| `mentor_id` | TEXT | 外键 → `persons.id` |
| `student_id` | TEXT | 外键 → `persons.id` |
| `relationship_type` | TEXT | `undergrad`、`phd`、`master`、`postdoc`、`informal`、`other` |
| `start_year` | INTEGER | 可空，1900–当前年份+1 |
| `end_year` | INTEGER | 可空，不能早于 `start_year` |
| `institution` | TEXT | 可空 |
| `student_placement` | TEXT | 可空，学生毕业去向（机构+职位） |
| `evidence_url` | TEXT | 必填，至少一个主页 URL |
| `evidence_text` | TEXT | 可空 |
| `confidence` | TEXT | `confirmed`、`probable`、`uncertain` |
| `status` | TEXT | `draft`、`verified`、`rejected` |
| `public` | INTEGER | 0/1，默认 0 |
| `notes_private` | TEXT | 可空，只存本地 |
| `created_at` | TEXT | ISO 8601 |
| `updated_at` | TEXT | ISO 8601 |

建立 `UNIQUE(mentor_id, student_id, relationship_type)`，并拒绝 `mentor_id = student_id`。同一对学者可以存在不同类型的导师关系，但不能重复建立同类型关系。

### `source_snapshots`

保存用户主动提交 URL 时得到的最小识别信息，而不是整页内容：

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | TEXT | UUID，主键 |
| `person_id` | TEXT | 外键 → `persons.id` |
| `url` | TEXT | 被访问的 URL |
| `title` | TEXT | 页面 title |
| `description` | TEXT | meta description，可空 |
| `fetched_at` | TEXT | ISO 8601 |
| `http_status` | INTEGER | HTTP 状态码 |

## 双主页 URL 录入流程

### 前端步骤

1. 用户输入导师主页 URL 和学生主页 URL。
2. 前端调用 `POST /api/preview-person` 两次，服务端返回页面标题、候选姓名和规范化 URL。
3. 页面展示两个身份卡片，用户确认这两个 URL 对应的学者。
4. 用户选择关系类型，默认 `phd`，可填写年份、机构、证据说明、可信度和公开权限。
5. 页面用明确句式展示：`学生 A 是导师 B 的学生`。
6. 用户点击确认后，调用 `POST /api/mentorships`。
7. 服务端以 URL 查找或创建学者，再创建关系；若关系已存在，返回 409 并展示已有关系。
8. 成功后跳转到以学生为中心的谱系页面，并自动显示导师和学生节点。

### 识别规则

- URL 必须是 `http` 或 `https`，禁止 `file:`、`javascript:`、`data:` 等协议。
- 只访问用户明确提交的 URL，超时 8 秒，最大响应体 1 MiB，只读取 HTML。
- 优先读取 `<title>`、`meta[name="author"]`、`meta[property="og:title"]`、`meta[name="description"]`。
- 页面无法访问时不阻止手动录入，允许用户手动填写姓名，但必须保留输入 URL。
- 不根据页面文本自动推断师生关系；关系方向只能由用户确认。

## API 契约

### `POST /api/preview-person`

请求：

```json
{"url": "https://example.edu/person"}
```

成功响应：

```json
{
  "normalized_url": "https://example.edu/person",
  "title": "Jane Doe — University",
  "candidate_name": "Jane Doe",
  "description": "Researcher in ...",
  "http_status": 200,
  "fetch_error": null
}
```

### `POST /api/persons`

请求：

```json
{
  "name": "Jane Doe",
  "homepage_url": "https://example.edu/person",
  "institution": "Example University",
  "field": "Computer Science",
  "public": false,
  "notes_private": ""
}
```

创建时按规范化主页 URL 去重；已存在时返回已有节点和 `created=false`。

### `GET /api/persons?q=<query>`

按姓名、英文名、别名和机构模糊搜索，返回最多 50 条。

### `GET /api/persons/<id>/lineage?up=3&down=2`

返回以指定学者为中心、向上最多 3 代、向下最多 2 代的节点和边。

### `POST /api/mentorships`

请求必须包含 `mentor_id`、`student_id`、`relationship_type`、`evidence_url`；其余字段按数据模型校验。

### `GET /api/mentorships/<id>`

返回关系、导师、学生和证据数据。

### `PATCH /api/mentorships/<id>`

允许修改状态、可信度、年份、公开权限、证据说明和私有备注；不允许通过 PATCH 交换导师和学生，交换方向必须显式删除后重新创建。

### `POST /api/export/public`

导出当前数据库中同时满足 `public=1`、关系 `status=verified`、两端学者 `public=1` 的数据到 `public/data/people.json` 和 `public/data/relationships.json`，并生成 `public/data/manifest.json`。

## 前端页面

### 本地管理页 `/`

- 搜索框：按姓名、英文名、别名、机构搜索。
- URL 录入卡片：导师 URL、学生 URL、预览、确认关系。
- 图谱区域：上下游展开、拖动、缩放、重置视图。
- 详情区域：姓名、主页、机构、关系来源、状态、公开标记和私有备注。

### 公开静态页 `/public/`

- 只加载 `data/*.json`。
- 支持搜索公开学者。
- 支持向上/向下展开已验证关系。
- 不显示任何 `notes_private`、草稿关系、未公开学者或未公开证据。
- 页面中标注“数据由人工维护，关系以证据链接为准”。

## 隐私与安全

- `data/network.sqlite`、本地导出临时文件和 `.env` 必须加入 `.gitignore`。
- 公开导出采用白名单字段，不使用“删除几个字段”的黑名单策略。
- 私有备注只允许本地 API 返回，不允许出现在静态 JSON。
- URL 抓取使用请求超时、响应大小限制、HTML 内容类型检查和重定向次数限制。
- 本地服务器默认绑定 `127.0.0.1`，不默认暴露到局域网。
- 不保存 Cookie、登录信息或需要认证的页面内容。

## 验收标准

- 输入两个有效主页 URL，可以预览身份并明确选择导师与学生。
- 确认后，两个学者节点和一条正确方向的关系出现在 SQLite 中。
- 重复提交同一对学者和关系类型不会产生重复边。
- 搜索学者后可以分别查看导师链和学生树。
- 页面无法访问时，用户仍可以手动确认姓名并保存主页 URL。
- 公开导出不包含任何私有备注、草稿关系或未公开节点。
- 使用导出数据可以在无 Python 后端的情况下打开公开静态页面。
- 单元测试覆盖 URL 校验、HTML 元数据解析、关系方向、去重、代数限制和公开导出过滤。
