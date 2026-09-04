# 学术谱系网络 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在仓库内创建一个独立的本地学术谱系工具，支持通过两个学者主页 URL 手动确认导师—学生关系，并导出可发布到 GitHub Pages 的公开静态图谱。

**Architecture:** `academic-lineage/` 是与现有个人网站隔离的子项目。Flask 提供本地管理 API 和管理页面，SQLite 保存完整本地数据，Cytoscape.js 渲染交互式谱系图；导出命令只生成通过公开筛选的数据 JSON 和静态页面。

**Tech Stack:** Python 3.11+, Flask, SQLite (`sqlite3`), pytest, HTML/CSS/JavaScript, Cytoscape.js, GitHub Pages, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-09-04-academic-lineage-network-design.md`

## Global Constraints

- 所有学术谱系代码放在 `academic-lineage/`，不得修改现有个人网站 `server.py`、`static/` 和 `docs/` 内容。
- `data/network.sqlite` 永远不提交到公开 GitHub 仓库。
- 不自动判断师生关系；关系方向必须由用户在确认页明确选择。
- 只访问用户明确提交的 URL；请求超时 8 秒、最大响应体 1 MiB、只接受 HTML。
- 公开导出只包含公开学者和两端均公开的已验证关系。
- 私有备注、草稿关系、未公开证据不得进入 `public/data/*.json`。
- 本地服务器默认绑定 `127.0.0.1`，不要使用 `0.0.0.0`。
- 每个任务完成后运行该任务列出的测试，再创建一个小而明确的 Git commit。

---

## 文件结构

```text
academic-lineage/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # 路径、端口、抓取限制
│   ├── db.py                    # SQLite 连接、迁移和事务
│   ├── schema.sql               # persons、mentorships、source_snapshots
│   ├── repositories.py          # 学者和关系的持久化操作
│   ├── fetcher.py               # URL 校验和主页元数据预览
│   ├── services.py              # 业务校验、谱系查询、公开导出
│   └── routes.py                # HTTP API 路由
├── templates/
│   └── index.html               # 本地管理页入口
├── static/
│   ├── app.js                   # 搜索、录入、图谱交互
│   └── style.css                # 管理页布局
├── public/
│   ├── index.html               # 无后端公开站点
│   ├── app.js                   # 公开站点逻辑
│   ├── style.css                # 公开站点样式
│   └── data/                    # 由导出命令生成
├── scripts/
│   └── export_public.py         # 数据库到公开 JSON 的导出命令
├── tests/
│   ├── test_db.py
│   ├── test_fetcher.py
│   ├── test_services.py
│   ├── test_routes.py
│   └── test_export.py
├── requirements.txt
├── run.py
├── README.md
└── .gitignore
```

### Task 1: 创建独立项目骨架和 Flask app factory

**Files:**
- Create: `academic-lineage/app/__init__.py`
- Create: `academic-lineage/app/config.py`
- Create: `academic-lineage/run.py`
- Create: `academic-lineage/requirements.txt`
- Create: `academic-lineage/.gitignore`
- Create: `academic-lineage/templates/index.html`
- Create: `academic-lineage/tests/test_routes.py`

**Interfaces:**
- Produces: `create_app(test_config: dict | None = None) -> Flask`
- Produces: `GET /` 返回管理页面；`GET /api/health` 返回 `{"status":"ok"}`

- [ ] **Step 1: 写 app factory 的失败测试**

```python
from app import create_app


def test_health_endpoint_returns_ok(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite")})
    response = app.test_client().get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
```

- [ ] **Step 2: 运行失败测试**

```bash
cd academic-lineage
python -m pytest tests/test_routes.py::test_health_endpoint_returns_ok -q
```

Expected: FAIL，因为 `app` 包和 `create_app` 尚未定义。

- [ ] **Step 3: 实现最小 app factory**

`create_app` 必须注册模板目录、静态目录和 `/api/health`，默认配置使用 `127.0.0.1`、端口 `5050` 和 `data/network.sqlite`。

- [ ] **Step 4: 创建运行入口和依赖文件**

`run.py` 使用：

```python
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=True)
```

`requirements.txt` 至少包含：

```text
Flask>=3.0,<4.0
pytest>=8.0,<9.0
```

- [ ] **Step 5: 运行测试并确认通过**

```bash
python -m pytest tests/test_routes.py::test_health_endpoint_returns_ok -q
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add academic-lineage
git commit -m "feat: scaffold academic lineage local app"
```

### Task 2: 实现 SQLite schema、连接管理和 repository

**Files:**
- Create: `academic-lineage/app/schema.sql`
- Create: `academic-lineage/app/db.py`
- Create: `academic-lineage/app/repositories.py`
- Create: `academic-lineage/tests/test_db.py`

**Interfaces:**
- `init_db(app: Flask) -> None`
- `get_db() -> sqlite3.Connection`
- `normalize_homepage_url(url: str) -> str`
- `find_or_create_person(data: dict) -> tuple[dict, bool]`
- `create_mentorship(data: dict) -> dict`
- `find_persons(query: str, limit: int = 50) -> list[dict]`
- `get_lineage(person_id: str, up: int, down: int) -> dict`

- [ ] **Step 1: 写数据库失败测试**

测试必须验证：主页 URL 去重、同名关系去重、自环拒绝和外键约束。

```python
import pytest
from app import create_app
from app.repositories import create_mentorship, find_or_create_person


def test_person_is_deduplicated_by_normalized_homepage(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite")})
    with app.app_context():
        first, created_first = find_or_create_person({
            "name": "Jane Doe",
            "homepage_url": "HTTPS://example.edu/jane/#bio",
        })
        second, created_second = find_or_create_person({
            "name": "Different Label",
            "homepage_url": "https://example.edu/jane",
        })
    assert created_first is True
    assert created_second is False
    assert first["id"] == second["id"]


def test_self_mentorship_is_rejected(app):
    with app.app_context():
        person, _ = find_or_create_person({"name": "Jane Doe", "homepage_url": "https://example.edu/jane"})
        with pytest.raises(ValueError, match="mentor and student must differ"):
            create_mentorship({
                "mentor_id": person["id"],
                "student_id": person["id"],
                "relationship_type": "phd",
                "evidence_url": "https://example.edu/jane",
            })
```

- [ ] **Step 2: 运行失败测试**

```bash
python -m pytest tests/test_db.py -q
```

Expected: FAIL，因为 schema 和 repository 尚未实现。

- [ ] **Step 3: 创建 schema.sql**

实现设计说明中的 `persons`、`mentorships`、`source_snapshots` 三张表、外键、索引和唯一约束；连接初始化时执行 `PRAGMA foreign_keys = ON`。

- [ ] **Step 4: 实现数据库连接生命周期**

`get_db()` 从 Flask `g` 复用连接；`teardown_appcontext` 关闭连接；app factory 创建数据库父目录并执行 schema 初始化。

- [ ] **Step 5: 实现 repository 的 URL 和关系校验**

`normalize_homepage_url` 只允许 `http`/`https`，去除 fragment 和末尾 `/`；关系创建必须拒绝自环、非法关系类型、缺失证据 URL和重复关系。

- [ ] **Step 6: 实现谱系查询**

`get_lineage(person_id, up, down)` 必须将 `up`、`down` 限制在 `0..10`，使用分层 BFS，返回：

```python
{
    "center_id": str,
    "nodes": list[dict],
    "edges": list[dict],
    "up": int,
    "down": int,
}
```

- [ ] **Step 7: 运行测试并确认通过**

```bash
python -m pytest tests/test_db.py -q
```

Expected: PASS。

- [ ] **Step 8: 提交**

```bash
git add academic-lineage/app/schema.sql academic-lineage/app/db.py academic-lineage/app/repositories.py academic-lineage/tests/test_db.py
git commit -m "feat: add lineage SQLite schema and repositories"
```

### Task 3: 实现主页 URL 校验和元数据预览

**Files:**
- Create: `academic-lineage/app/fetcher.py`
- Create: `academic-lineage/tests/test_fetcher.py`

**Interfaces:**
- `validate_url(url: str) -> str`
- `parse_html_metadata(html: str) -> dict`
- `preview_person_url(url: str, opener=None) -> dict`

- [ ] **Step 1: 写元数据解析失败测试**

```python
from app.fetcher import parse_html_metadata, validate_url


def test_metadata_prefers_og_title_and_author():
    html = """
    <html><head>
      <title>Fallback title</title>
      <meta property="og:title" content="Jane Doe | University">
      <meta name="author" content="Jane Doe">
      <meta name="description" content="Research profile">
    </head></html>
    """
    result = parse_html_metadata(html)
    assert result["title"] == "Jane Doe | University"
    assert result["candidate_name"] == "Jane Doe"
    assert result["description"] == "Research profile"


def test_unsafe_url_is_rejected():
    import pytest
    with pytest.raises(ValueError, match="http or https"):
        validate_url("file:///secret.txt")
```

- [ ] **Step 2: 运行失败测试**

```bash
python -m pytest tests/test_fetcher.py -q
```

Expected: FAIL，因为 URL 校验和解析函数尚未定义。

- [ ] **Step 3: 实现 URL 校验**

拒绝空值、非 HTTP(S) 协议、缺少主机名和包含用户密码的 URL；设置最大 URL 长度 2048 字符。

- [ ] **Step 4: 实现 HTML 元数据解析**

使用 Python 标准库 `html.parser.HTMLParser`，读取 `title`、`og:title`、`author` 和 `description`；所有返回文本去除首尾空白并限制为 500 字符。

- [ ] **Step 5: 实现受限网络预览**

`preview_person_url` 使用可注入的 `opener` 便于测试；默认请求设置 User-Agent、8 秒 timeout、最大读取 1 MiB、只接受 HTML，并最多跟随 3 次重定向。网络失败时返回 `fetch_error`，不要抛出未处理异常，也不要阻止后续手动录入。

- [ ] **Step 6: 运行测试并确认通过**

```bash
python -m pytest tests/test_fetcher.py -q
```

Expected: PASS。

- [ ] **Step 7: 提交**

```bash
git add academic-lineage/app/fetcher.py academic-lineage/tests/test_fetcher.py
git commit -m "feat: add safe academic homepage preview"
```

### Task 4: 实现业务 service 和本地 API

**Files:**
- Create: `academic-lineage/app/services.py`
- Create: `academic-lineage/app/routes.py`
- Modify: `academic-lineage/app/__init__.py`
- Modify: `academic-lineage/tests/test_routes.py`

**Interfaces:**
- `POST /api/preview-person`
- `POST /api/persons`
- `GET /api/persons?q=<query>`
- `GET /api/persons/<id>/lineage?up=3&down=2`
- `POST /api/mentorships`
- `GET /api/mentorships/<id>`
- `PATCH /api/mentorships/<id>`

- [ ] **Step 1: 写 API 失败测试**

```python
def test_create_mentorship_preserves_mentor_student_direction(app):
    client = app.test_client()
    mentor = client.post("/api/persons", json={
        "name": "Mentor", "homepage_url": "https://example.edu/mentor"
    }).get_json()
    student = client.post("/api/persons", json={
        "name": "Student", "homepage_url": "https://example.edu/student"
    }).get_json()
    response = client.post("/api/mentorships", json={
        "mentor_id": mentor["person"]["id"],
        "student_id": student["person"]["id"],
        "relationship_type": "phd",
        "evidence_url": "https://example.edu/student",
        "status": "verified",
        "public": True,
    })
    assert response.status_code == 201
    body = response.get_json()
    assert body["mentorship"]["mentor_id"] == mentor["person"]["id"]
    assert body["mentorship"]["student_id"] == student["person"]["id"]
```

- [ ] **Step 2: 运行失败测试**

```bash
python -m pytest tests/test_routes.py -q
```

Expected: FAIL，因为 API 路由尚未注册。

- [ ] **Step 3: 实现请求 schema 校验和 service**

所有 JSON 请求在进入 repository 前校验必填字段、枚举值、年份范围和布尔值；校验失败返回 `400`，重复关系返回 `409`，记录不存在返回 `404`。

- [ ] **Step 4: 实现 URL 预览路由**

`POST /api/preview-person` 调用 `preview_person_url`，成功返回设计说明中的预览结构；网络失败仍返回 `200` 和非空 `fetch_error`，非法 URL 返回 `400`。

- [ ] **Step 5: 实现学者、谱系和关系路由**

关系创建接口接受两种录入方式：已经确认的 `mentor_id`/`student_id`，以及两个已预览主页 URL 经服务层解析后的节点；第一版前端使用 ID 方式，服务端保留 URL 去重逻辑。

- [ ] **Step 6: 实现状态和公开权限更新**

`PATCH /api/mentorships/<id>` 只允许更新 `status`、`confidence`、年份、证据说明、私有备注和 `public`；不能静默更换关系方向。

- [ ] **Step 7: 运行测试并确认通过**

```bash
python -m pytest tests/test_routes.py -q
```

Expected: PASS。

- [ ] **Step 8: 提交**

```bash
git add academic-lineage/app academic-lineage/tests/test_routes.py
git commit -m "feat: expose lineage management API"
```

### Task 5: 实现本地管理页面和双 URL 确认流程

**Files:**
- Modify: `academic-lineage/templates/index.html`
- Create: `academic-lineage/static/app.js`
- Create: `academic-lineage/static/style.css`

**Interfaces:**
- 页面调用 `POST /api/preview-person`、`POST /api/persons`、`POST /api/mentorships`、`GET /api/persons` 和 `GET /api/persons/<id>/lineage`。
- 页面必须在提交前展示句式：`学生 {studentName} 是导师 {mentorName} 的学生`。

- [ ] **Step 1: 创建页面结构**

页面包含四个固定区域：搜索栏、双 URL 录入表单、Cytoscape 图谱容器、详情面板。录入表单字段为导师主页 URL、学生主页 URL、关系类型、开始年份、结束年份、机构、证据说明、可信度和公开标记。

- [ ] **Step 2: 实现预览按钮和身份卡片**

两个 URL 分别调用预览接口；成功显示候选姓名、页面标题和 URL；抓取失败显示错误但保留手动姓名输入字段。未完成两张身份卡片时禁用“确认并加入图谱”。

- [ ] **Step 3: 实现确认句式和提交**

点击确认后，先通过 `POST /api/persons` 确保两个节点存在，再以返回 ID 调用 `POST /api/mentorships`。收到 `409` 时显示已有关系，不重复创建。

- [ ] **Step 4: 实现搜索和谱系加载**

搜索输入至少等待 250 ms 防抖后调用 `/api/persons?q=`；点击结果后调用 `/lineage?up=3&down=2`，把节点和边转换为 Cytoscape.js elements。

- [ ] **Step 5: 实现上下游展开**

详情面板提供“向上展开一代”“向下展开一代”“重置视图”按钮；向上和向下的代数分别累计，但每次请求最大不超过 10 代。

- [ ] **Step 6: 实现关系详情和公开状态显示**

点击边显示导师、学生、关系类型、状态、可信度、证据 URL 和公开标记；点击节点显示学者主页和私有备注。私有备注只在本地管理页显示。

- [ ] **Step 7: 手工验证本地录入流程**

```bash
cd academic-lineage
python run.py
```

打开 `http://127.0.0.1:5050/`，使用两个公开学术主页 URL 完成一次预览、确认、录入和图谱展开。不要把真实私密资料用于测试仓库。

- [ ] **Step 8: 提交**

```bash
git add academic-lineage/templates academic-lineage/static
git commit -m "feat: add two-homepage mentorship entry flow"
```

### Task 6: 实现公开数据导出和静态站点

**Files:**
- Create: `academic-lineage/app/exporter.py`
- Create: `academic-lineage/scripts/export_public.py`
- Create: `academic-lineage/public/index.html`
- Create: `academic-lineage/public/app.js`
- Create: `academic-lineage/public/style.css`
- Create: `academic-lineage/tests/test_export.py`

**Interfaces:**
- `export_public_data(connection, output_dir: Path) -> dict`
- 命令：`python scripts/export_public.py --database data/network.sqlite --output public/data`
- 输出：`people.json`、`relationships.json`、`manifest.json`

- [ ] **Step 1: 写公开导出失败测试**

```python
import json
from app.db import get_db
from app.exporter import export_public_data
from app.repositories import create_mentorship, find_or_create_person


def test_public_export_filters_private_and_unverified_records(app, tmp_path):
    output = tmp_path / "data"
    with app.app_context():
        mentor, _ = find_or_create_person({
            "name": "Public Mentor",
            "homepage_url": "https://example.edu/mentor",
            "public": True,
        })
        student, _ = find_or_create_person({
            "name": "Public Student",
            "homepage_url": "https://example.edu/student",
            "public": True,
        })
        private_student, _ = find_or_create_person({
            "name": "Private Student",
            "homepage_url": "https://example.edu/private-student",
            "public": False,
        })
        create_mentorship({
            "mentor_id": mentor["id"], "student_id": student["id"],
            "relationship_type": "phd", "evidence_url": mentor["homepage_url"],
            "status": "verified", "public": True,
        })
        create_mentorship({
            "mentor_id": mentor["id"], "student_id": private_student["id"],
            "relationship_type": "phd", "evidence_url": mentor["homepage_url"],
            "status": "draft", "public": True,
        })
        result = export_public_data(get_db(), output)
    people = json.loads((output / "people.json").read_text())
    relationships = json.loads((output / "relationships.json").read_text())
    assert result["people"] == 2
    assert result["relationships"] == 1
    assert all("notes_private" not in person for person in people)
    assert all(edge["status"] == "verified" for edge in relationships)
```

测试 fixture 必须创建 3 个学者、2 条关系，其中一条关系为 draft、一位学者为 private；预期公开结果只保留 2 个公开学者和 1 条 verified 关系。

- [ ] **Step 2: 运行失败测试**

```bash
python -m pytest tests/test_export.py -q
```

Expected: FAIL，因为 exporter 尚未实现。

- [ ] **Step 3: 实现白名单导出**

公开学者只导出：`id`、`name`、`name_en`、`aliases`、`institution`、`field`、`homepage_url`。公开关系只导出：`id`、`mentor_id`、`student_id`、`relationship_type`、年份、机构、证据 URL、证据说明、可信度、状态。绝不导出 `notes_private`。

- [ ] **Step 4: 实现 manifest**

`manifest.json` 包含 `generated_at`、`people_count`、`relationship_count` 和 `schema_version`，使用 `schema_version: 1`。

- [ ] **Step 5: 实现无后端静态页面**

公开页面只从相对路径 `data/people.json` 和 `data/relationships.json` 加载数据；搜索和谱系展开在浏览器内完成。页面在 `file://` 环境下失败时显示明确提示，部署到 GitHub Pages 后使用正常相对路径。

- [ ] **Step 6: 运行导出测试和浏览器手工检查**

```bash
python -m pytest tests/test_export.py -q
python scripts/export_public.py --database data/network.sqlite --output public/data
```

Expected: 测试 PASS，三个 JSON 文件生成；使用任意静态文件服务器打开 `public/` 可以搜索并展开公开谱系。

- [ ] **Step 7: 提交**

```bash
git add academic-lineage/app/exporter.py academic-lineage/scripts academic-lineage/public academic-lineage/tests/test_export.py
git commit -m "feat: export verified public lineage site"
```

### Task 7: 加入完整测试、运行文档和 GitHub Pages 工作流

**Files:**
- Create: `academic-lineage/.github/workflows/deploy.yml`
- Modify: `academic-lineage/README.md`
- Modify: `academic-lineage/.gitignore`
- Create: `academic-lineage/tests/test_services.py`
- Modify: `academic-lineage/tests/test_routes.py`

**Interfaces:**
- `README.md` 必须提供安装、初始化、启动、测试、导出和公开部署命令。
- GitHub Actions 只构建 `public/`，不上传 SQLite 数据库。

- [ ] **Step 1: 写 service 边界测试**

覆盖以下行为：上下游代数超过 10 返回 400；重复关系返回 409；关系方向不被反转；主页抓取失败仍可手动保存；公开导出过滤正确。

- [ ] **Step 2: 运行全量测试并修复失败**

```bash
cd academic-lineage
python -m pytest -q
```

Expected: 所有测试 PASS。

- [ ] **Step 3: 编写 README**

README 至少包含：

```bash
cd academic-lineage
python -m venv .venv
\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

以及：

```bash
python -m pytest -q
python scripts/export_public.py --database data/network.sqlite --output public/data
```

说明本地数据库不提交、公开字段白名单、双主页录入流程和 GitHub Pages 的目录设置。

- [ ] **Step 4: 创建 GitHub Pages 工作流**

工作流在 `main` 分支 push 或手动触发时，直接上传仓库中已经提交的 `academic-lineage/public` 到 Pages。工作流不得安装或读取本地 SQLite，也不得执行导出命令，避免在 CI 中用空数据库覆盖公开数据。实际公开数据由本地导出命令生成后，经人工检查再提交到 `academic-lineage/public/data/`。

- [ ] **Step 5: 完成最终验证**

```bash
cd academic-lineage
python -m pytest -q
python scripts/export_public.py --database data/network.sqlite --output public/data
python -m http.server 4173 --directory public
```

验收：管理页可录入关系；导出后公开页可搜索、显示上下游谱系；公开 JSON 中没有 `notes_private`，没有 draft/rejected 关系；根目录现有个人网站仍可执行原有的 `npm run docs:build`。

- [ ] **Step 6: 提交**

```bash
git add academic-lineage
git commit -m "docs: document lineage app and publish public site"
```

## 完成后的交接信息

另一个 agent 开始执行时，先阅读：

1. `docs/superpowers/specs/2026-09-04-academic-lineage-network-design.md`
2. `docs/superpowers/plans/2026-09-04-academic-lineage-network-plan.md`
3. 现有 `package.json` 和 `server.py`，确认不修改个人网站和记账服务。

执行顺序必须从 Task 1 到 Task 7；每个任务都先写失败测试，再实现最小功能，最后运行测试并提交。完成后先验证本地管理页和公开静态页，再考虑把 `academic-lineage/` 拆成独立 GitHub 仓库。
