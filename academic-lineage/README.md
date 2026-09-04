# 学术谱系网络（本地工具）

在仓库内独立运行的导师—学生学术谱系工具：本地管理、私有数据与公开导出分离。

- 本地管理页：`http://127.0.0.1:5050/`（Flask + SQLite + Cytoscape.js）
- 公开静态页：`public/`（无后端，只读 `public/data/*.json`，可发布到 GitHub Pages）
- 数据库：`data/network.sqlite`（**永不提交到公开仓库**）

## 安装与启动

```bash
cd academic-lineage
python -m venv .venv
\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

打开 `http://127.0.0.1:5050/`：输入两位学者的主页 URL → 预览身份 → 确认“学生 X 是导师 Y 的学生” → 写入图谱。

## 测试

```bash
cd academic-lineage
python -m pytest -q
```

## 公开导出

```bash
python scripts/export_public.py --database data/network.sqlite --output public/data
```

只导出同时满足以下条件的数据：学者 `public=1`；关系 `public=1` 且 `status=verified` 且两端学者均公开。采用白名单字段，私有备注、草稿、拒绝记录不会出现在 JSON 中。

本地预览公开站点：

```bash
python -m http.server 4173 --directory public
```

打开 `http://127.0.0.1:4173/`。请勿直接用 `file://` 打开（fetch 会失败）。

## 隐私与安全

- 本地服务器只绑定 `127.0.0.1`，不暴露到局域网。
- 只抓取用户主动提交的 URL：8 秒超时、最大 1 MiB、只接受 HTML、最多 3 次重定向。
- 不自动推断师生关系；关系方向必须由用户确认。
- `data/` 已在 `.gitignore` 中；实际公开数据由本地导出命令生成、人工检查后提交 `public/data/`。

## 投稿审核（协作）

1. 朋友打开公开站点 → 点「投稿关系」→ 填写信息 → 「生成投稿内容」→ 复制 JSON 发给你。
2. 你在本地管理页「投稿审核」粘贴 JSON →「导入为待审核」。
3. 逐条审核：**通过**（自动创建两位学者和关系，默认私有，可再编辑/公开）或**拒绝**。

投稿数据只存在本地 SQLite，不经第三方服务器。

## 目录结构

```text
app/            Flask 应用（工厂、配置、schema、repository、fetcher、service、路由、导出）
templates/      本地管理页模板
static/         管理页样式与逻辑（vendor/cytoscape.min.js 为本地副本）
public/         无后端公开站点（data/ 由导出命令生成）
scripts/        公开导出命令
tests/          pytest 测试
```
