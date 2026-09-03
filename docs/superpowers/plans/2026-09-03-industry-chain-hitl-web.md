# 产业链 HITL 本地 Web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Core HITL 合同稳定后，实现一个单机 localhost 审核工作台，让用户选择 Runner、快速审核来源、在 Full Review 编辑最终 Tree/description、观察任务进度，并通过共享 Python Core 原子写回九字段 XLSX。

**Architecture:** React + TypeScript + Vite 只负责 UI、working copy 和轮询；FastAPI 是薄 HTTP adapter；所有 Runner、Review、Work、Tree→records、状态机和原子 XLSX 行为继续落在 Python Core。前端不读写 `runner.json`、不维护第二套状态机、不渲染 Evidence 图片资产；审核依据只显示 uncertainty 的 `locator + description` 并提供原来源链接。

**Tech Stack:** Python 3.11+、FastAPI、Uvicorn、React、TypeScript、Vite、React Router、dnd-kit、Vitest、Testing Library、现有 Runner JSON/XLSX Core。

**Spec:** `docs/superpowers/specs/2026-09-03-industry-chain-hitl-web-frontend-design.md`；核心业务合同同时遵守 `docs/superpowers/specs/2026-09-03-industry-chain-human-review-design.md`。

## Global Constraints

- 这是单机 `localhost` 工具；默认绑定 `127.0.0.1:8765`，无登录、用户、角色、权限和公网部署能力。
- Web 与 CLI 必须调用同一套 Python Core；Web 不直接读写 Runner JSON，不暴露通用 `PATCH status`。
- Quick Review 严格只读；Tree、企业和 `description` 只允许在 Full Review 编辑。
- Full Review working copy 只有最终 `chain + description`；uncertainties/Evidence 是审核上下文，不要求人工逐条回答或编辑。
- `description` 的 UI 标签固定表达为“来源说明（最终备注）”，最终写入 XLSX 来源组第一行 `备注`。
- Evidence v1 只显示 `locator + description`；不做图片缩略图、Lightbox、OCR、bounding box、截图资产、PDF crop、网页镜像或浏览器录像。
- focus 从 uncertainty 在来源/Tree/企业 occurrence 中的位置动态派生，不持久化 `focus_item_id`，不出现 question/options/recommended_answer/human_answer。
- 初始 `chain=[]` 时不启用 Tree 编辑器，也不能 add root，只允许“交回 AI 继续”或“驳回来源”。
- Tree 最大正式分类深度为 4；同父排序和跨父 reparent 必须使用同一递归语义，移动父节点时整棵子树跟随。
- 企业模型固定是 `companies: string[]`；不展示企业组层级。
- “已完成 / 总主题”统计把 `completed + no_qualified_source` 都计为已完成；单个 `no_qualified_source` 标签仍是“无合格来源”。
- 不引入数据库、Redis、WebSocket、消息队列、用户模块、知识库、Agent 管理后台或统计分析后台。
- 视觉风格固定为 Warm Editorial Research Workbench，使用批准的暖色 token；不做 Dark Mode、渐变、玻璃、霓虹和大面积彩色 tag。

---

## 文件结构与职责

### Python Web adapter

| 文件 | 动作 | 职责 |
| --- | --- | --- |
| `skills/researching-industry-chains/src/industry_chain_skills/activity.py` | Create | 最小 Runner Activity event helper；只记录业务事实，不记录 Prompt/推理 |
| `skills/researching-industry-chains/src/industry_chain_skills/web_views.py` | Create | 生成 Runner Picker、Dashboard、Reviews、Progress、Completed、Activity 的只读 ViewModel |
| `skills/researching-industry-chains/src/industry_chain_skills/web_app.py` | Create | FastAPI app、业务 endpoints、SPA 静态文件服务 |
| `skills/researching-industry-chains/src/industry_chain_skills/storage.py` | Modify | 原子 Runner 删除入口 |
| `skills/researching-industry-chains/src/industry_chain_skills/runner.py` | Modify | failed topic retry、删除 guard 所需 claim 判断 helper |
| `skills/researching-industry-chains/src/industry_chain_skills/work.py` | Modify | 追加最小 Activity event |
| `skills/researching-industry-chains/src/industry_chain_skills/source_service.py` | Modify | 追加来源接受/送审/Agent 重提 Activity event |
| `skills/researching-industry-chains/src/industry_chain_skills/review.py` | Modify | 追加 Human approve/return/reject Activity event |
| `skills/researching-industry-chains/src/industry_chain_skills/cli.py` | Modify | `industry-chain web` 启动命令 |
| `skills/researching-industry-chains/pyproject.toml` | Modify | FastAPI/Uvicorn 依赖和 build 后静态资源 package-data |

### React Web

| 文件/目录 | 动作 | 职责 |
| --- | --- | --- |
| `skills/researching-industry-chains/web/` | Create | Vite React TS 工程源代码 |
| `web/src/api/client.ts` | Create | 唯一 HTTP client 与错误映射 |
| `web/src/api/types.ts` | Create | API DTO 类型 |
| `web/src/domain/tree.ts` | Create | 纯 Tree hydrate/serialize/add/remove/reparent/depth 逻辑 |
| `web/src/domain/review.ts` | Create | uncertainty→focus 派生、working copy/localStorage key |
| `web/src/components/` | Create | Sidebar、Tree、Evidence、ReviewActions、StatusBadge 等聚焦组件 |
| `web/src/pages/` | Create | RunnerPicker、Workspace、Reviews、FullReview、Progress、Completed 页面 |
| `web/src/styles.css` | Create | 批准的 Warm Editorial token 与全局布局 |
| `web/vite.config.ts` | Modify generated file | build 输出到 Python package `web_dist` |
| `skills/researching-industry-chains/src/industry_chain_skills/web_dist/` | Generated, not committed | `npm run build` 生成的生产静态文件 |

---

### Task 1: 增加 FastAPI 薄 adapter 骨架和静态 build 合同

**Files:**
- Modify: `skills/researching-industry-chains/pyproject.toml`
- Create: `skills/researching-industry-chains/src/industry_chain_skills/web_app.py`
- Create: `skills/researching-industry-chains/tests/test_web_app.py`
- Modify/Create: repository `.gitignore` entry for generated web assets if current file exists/does not exist.

**Interfaces:**
- `create_app(runs_root: Path, static_dir: Path | None = None) -> FastAPI`
- `serve_web(runs_root: Path, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None`

- [ ] **Step 1: 写 health/API prefix 失败测试**

```python
class WebAppTests(unittest.TestCase):
    def test_health_is_available_without_static_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            app = create_app(Path(tmpdir), static_dir=None)
            client = TestClient(app)
            response = client.get("/api/health")
            self.assertEqual(200, response.status_code)
            self.assertEqual({"ok": True}, response.json())
```

- [ ] **Step 2: 更新 Python dependencies**

`pyproject.toml` 主依赖增加：

```toml
"fastapi>=0.115,<1",
"uvicorn>=0.30,<1"
```

测试依赖新增：

```toml
[project.optional-dependencies]
test = ["httpx>=0.27,<1"]
```

并预留 build 后静态资源：

```toml
[tool.setuptools.package-data]
industry_chain_skills = ["web_dist/**"]
```

- [ ] **Step 3: 实现 create_app 最小骨架**

```python
def create_app(runs_root: Path, static_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Industry Chain HITL")
    app.state.runs_root = runs_root

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    if static_dir is not None:
        _mount_spa(app, static_dir)
    return app
```

API route 必须注册在 SPA catch-all 之前。

- [ ] **Step 4: 实现 SPA 静态服务行为测试**

创建临时 `index.html` + `assets/app.js`，验证：

```text
GET / → index.html
GET /runners/abc/reviews → index.html
GET /assets/app.js → asset
GET /api/health → JSON，不被 catch-all 吃掉
```

- [ ] **Step 5: 运行测试**

```bash
cd skills/researching-industry-chains
python -m pip install -e '.[test]'
PYTHONPATH=src python -m unittest tests.test_web_app -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/researching-industry-chains/pyproject.toml skills/researching-industry-chains/src/industry_chain_skills/web_app.py skills/researching-industry-chains/tests/test_web_app.py .gitignore
git commit -m "feat(web): add fastapi app shell"
```

---

### Task 2: 增加最小 Activity 与 Web 只读 Query ViewModel

**Files:**
- Create: `skills/researching-industry-chains/src/industry_chain_skills/activity.py`
- Create: `skills/researching-industry-chains/src/industry_chain_skills/web_views.py`
- Create: `skills/researching-industry-chains/tests/test_web_views.py`
- Modify: `runner.py`, `work.py`, `source_service.py`, `review.py` to call activity helper.
- Modify: `source_result.py` to add formal records→Tree reverse projection used only for read view.

**Interfaces:**
- `append_activity(state: dict, event_type: str, timestamp: str, **fields) -> dict`
- `records_to_tree(records: list[dict[str, str]]) -> list[dict]`
- `WebViewService.list_runners() -> list[dict]`
- `WebViewService.runner_overview(runner_id: str) -> dict`
- `WebViewService.dashboard(runner_id: str) -> dict`
- `WebViewService.list_reviews(runner_id: str) -> list[dict]`
- `WebViewService.review_detail(runner_id: str, review_id: str) -> dict`
- `WebViewService.progress(runner_id: str) -> list[dict]`
- `WebViewService.completed(runner_id: str) -> list[dict]`
- `WebViewService.activity(runner_id: str) -> list[dict]`

- [ ] **Step 1: 写 Activity 最小事件测试**

事件 shape 固定为：

```python
{
    "event_id": "event_...",
    "type": "source_accepted",
    "at": "2026-09-03T00:00:00+00:00",
    "topic_id": "node_0001",
    "review_id": None,
    "source_name": "示例研究院",
}
```

允许 `topic_id/review_id/source_name` 为 null；不写 Prompt、token、浏览器步骤或 chain-of-thought。

- [ ] **Step 2: 在现有 Core 业务点追加事件**

至少记录：

```text
topic_claimed
source_accepted
source_queued_for_review
review_returned_to_agent
review_resubmitted
review_approved
review_rejected
topic_completed
topic_no_qualified_source
work_failed
```

事件由 Core 在状态变化成功的同一个 mutation 中追加，不能由 Web 事后猜测。

- [ ] **Step 3: 写 records_to_tree 失败测试**

```python
def test_records_to_tree_restores_parent_child_order_and_companies(self) -> None:
    tree = records_to_tree([
        record("上游", "", company=""),
        record("上游", "锡粉", company="甲公司、乙公司"),
        record("中游", "", company="丙公司"),
    ])
    self.assertEqual("上游", tree[0]["name"])
    self.assertEqual(["甲公司", "乙公司"], tree[0]["children"][0]["companies"])
```

该函数只用于把正式 source_group rows 还原为 Completed 页面可读 Tree，不把 Tree 再持久化回 Runner，避免第二事实源。

- [ ] **Step 4: 实现 Runner Picker 与 Dashboard ViewModel**

Runner card 必须包含：

```text
runner_id, name, created_at, updated_at
total_topics, completed_topics
pending_reviews, in_progress, returned_to_agent
```

其中 `completed_topics = completed + no_qualified_source`。

Dashboard 固定输出四个 metrics：`待人工审核、AI处理中、已交回AI、今日完成`，以及最近 3 个 pending review 和少量 activity。

- [ ] **Step 5: 实现 Review/Progress/Completed ViewModel 并移除秘密字段**

Web DTO 不得暴露：

```text
claim.token
agent_claim.token
```

可以显示 `worker_label`、`lease_expires_at`、状态和更新时间。

Completed source view 从九字段 rows 反投影出：

```python
{
    "source_group_id": "source_...",
    "source": {"name": rows[0]["信源主体"], "url": rows[0]["信源URL"]},
    "description": rows[0]["备注"],
    "chain": records_to_tree(rows),
}
```

- [ ] **Step 6: 运行 Query 测试**

```bash
cd skills/researching-industry-chains
PYTHONPATH=src python -m unittest tests.test_web_views -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add skills/researching-industry-chains/src/industry_chain_skills/activity.py skills/researching-industry-chains/src/industry_chain_skills/web_views.py skills/researching-industry-chains/src/industry_chain_skills/source_result.py skills/researching-industry-chains/src/industry_chain_skills/runner.py skills/researching-industry-chains/src/industry_chain_skills/work.py skills/researching-industry-chains/src/industry_chain_skills/source_service.py skills/researching-industry-chains/src/industry_chain_skills/review.py skills/researching-industry-chains/tests/test_web_views.py
git commit -m "feat(web): add review query views and activity"
```

---

### Task 3: 实现 FastAPI 读写业务 endpoints、retry 与 Runner 删除

**Files:**
- Modify: `skills/researching-industry-chains/src/industry_chain_skills/web_app.py`
- Modify: `skills/researching-industry-chains/src/industry_chain_skills/storage.py`
- Modify: `skills/researching-industry-chains/src/industry_chain_skills/runner.py`
- Create: `skills/researching-industry-chains/tests/test_web_api.py`

**Interfaces:**
- GET:

```text
/api/runners
/api/runners/{runner_id}
/api/runners/{runner_id}/dashboard
/api/runners/{runner_id}/reviews
/api/runners/{runner_id}/reviews/{review_id}
/api/runners/{runner_id}/progress
/api/runners/{runner_id}/completed
/api/runners/{runner_id}/activity
```

- POST/DELETE:

```text
POST /api/runners/{runner_id}/reviews/{review_id}/approve
POST /api/runners/{runner_id}/reviews/{review_id}/return-to-agent
POST /api/runners/{runner_id}/reviews/{review_id}/reject
POST /api/runners/{runner_id}/topics/{topic_id}/retry
DELETE /api/runners/{runner_id}
```

- [ ] **Step 1: 写 Review actions HTTP 失败测试**

Approve body：

```json
{
  "expected_version": 3,
  "description": "最终来源说明",
  "chain": [{"name": "上游", "companies": ["甲公司"]}]
}
```

Return/reject body：

```json
{"expected_version": 3}
```

断言 Core `ClientError` 映射为：version conflict → HTTP 409；其它业务校验 → HTTP 400；not found → HTTP 404。

- [ ] **Step 2: 实现 typed request models 和业务 endpoint**

```python
class ApproveRequest(BaseModel):
    expected_version: int
    description: str
    chain: list[dict]

class VersionedActionRequest(BaseModel):
    expected_version: int
```

Endpoint 只调用 `ReviewService` / `RunnerService`，不直接改 state。

- [ ] **Step 3: 实现 failed topic retry**

`RunnerService.retry(runner_id, topic_id)` 只允许 `failed` → `pending`，清 `last_error`，不修改已有正式 source_groups/review_items。其它状态返回 `TOPIC_RETRY_NOT_ALLOWED`。

- [ ] **Step 4: 实现原子 Runner 删除**

在 `RunnerStore` 增加：

```python
def delete(self, runner_id: str, validator: Callable[[dict], None]) -> None:
    with self._lock(runner_id):
        state = self._read_json(self._json_path(runner_id))
        validator(state)
        shutil.rmtree(self._runner_dir(runner_id))
```

Web/Core validator 在删除前检查当前时间下是否存在有效 topic claim 或 review agent_claim；有则抛 `RUNNER_ACTIVE_CLAIM`。不提供 force delete。

- [ ] **Step 5: 写删除测试**

覆盖：无 claim 删除 JSON/XLSX 目录；有效 topic claim 阻止；有效 review claim 阻止；过期 claim 不阻止。

- [ ] **Step 6: 运行 API 测试**

```bash
cd skills/researching-industry-chains
PYTHONPATH=src python -m unittest tests.test_web_api -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add skills/researching-industry-chains/src/industry_chain_skills/web_app.py skills/researching-industry-chains/src/industry_chain_skills/storage.py skills/researching-industry-chains/src/industry_chain_skills/runner.py skills/researching-industry-chains/tests/test_web_api.py
git commit -m "feat(web): add hitl business api"
```

---

### Task 4: 增加 `industry-chain web` 本地启动命令

**Files:**
- Modify: `skills/researching-industry-chains/src/industry_chain_skills/cli.py`
- Modify: `skills/researching-industry-chains/src/industry_chain_skills/web_app.py`
- Create: `skills/researching-industry-chains/tests/test_web_cli.py`

**Interfaces:**

```text
industry-chain web [--host 127.0.0.1] [--port 8765] [--no-browser]
```

`--runs-root` 继续使用顶层已有参数。

- [ ] **Step 1: 写 parser defaults 测试**

```python
def test_web_defaults_are_localhost(self) -> None:
    args = build_parser().parse_args(["web"])
    self.assertEqual("127.0.0.1", args.host)
    self.assertEqual(8765, args.port)
    self.assertFalse(args.no_browser)
```

- [ ] **Step 2: 实现 build 目录定位**

默认静态目录：

```python
Path(__file__).resolve().parent / "web_dist"
```

如果不存在 `index.html`，CLI 返回清楚业务错误：

```text
WEB_BUILD_MISSING
前端尚未构建，请在 skills/researching-industry-chains/web 执行 npm install && npm run build
```

不自动安装 Node、不在运行时偷偷构建。

- [ ] **Step 3: 实现 serve_web**

```python
def serve_web(runs_root: Path, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    static_dir = Path(__file__).resolve().parent / "web_dist"
    if not (static_dir / "index.html").exists():
        raise ClientError("WEB_BUILD_MISSING", "前端尚未构建，请在 skills/researching-industry-chains/web 执行 npm install && npm run build")
    if open_browser:
        webbrowser.open(f"http://{host}:{port}")
    uvicorn.run(create_app(runs_root, static_dir), host=host, port=port)
```

- [ ] **Step 4: 测试 dispatch 不真正启动 server**

mock `serve_web`，验证 runs_root/host/port/open_browser 参数。

- [ ] **Step 5: 运行测试**

```bash
cd skills/researching-industry-chains
PYTHONPATH=src python -m unittest tests.test_web_cli -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/researching-industry-chains/src/industry_chain_skills/cli.py skills/researching-industry-chains/src/industry_chain_skills/web_app.py skills/researching-industry-chains/tests/test_web_cli.py
git commit -m "feat(cli): add local hitl web command"
```

---

### Task 5: 创建 Vite React TS 工程、API client 和官方视觉 token

**Files:**
- Create: `skills/researching-industry-chains/web/package.json` and Vite-generated config files
- Create: `web/src/main.tsx`
- Create: `web/src/App.tsx`
- Create: `web/src/api/client.ts`
- Create: `web/src/api/types.ts`
- Create: `web/src/styles.css`
- Modify: `web/vite.config.ts`

**Interfaces:**
- `apiGet<T>(path: string): Promise<T>`
- `apiPost<T>(path: string, body: unknown): Promise<T>`
- `apiDelete<T>(path: string): Promise<T>`
- `ApiError { status: number; code: string; message: string; details?: unknown }`

- [ ] **Step 1: 创建 React TS 工程并安装必要依赖**

Run:

```bash
cd skills/researching-industry-chains
npm create vite@latest web -- --template react-ts
cd web
npm install react-router-dom @dnd-kit/core @dnd-kit/sortable
npm install -D vitest jsdom @testing-library/react @testing-library/jest-dom
```

提交 `package-lock.json`，不提交 `node_modules`。

- [ ] **Step 2: 配置 Vite build 到 Python package**

`vite.config.ts`：

```ts
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/industry_chain_skills/web_dist",
    emptyOutDir: true,
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
})
```

生成的 `web_dist/` 加 `.gitignore`，不提交 build artifact。

- [ ] **Step 3: 定义 API DTO**

至少包含：`RunnerSummary`、`DashboardView`、`ReviewListItem`、`ReviewDetail`、`ChainNode`、`Uncertainty`、`Evidence`、`ProgressTopic`、`CompletedTopic`、`ActivityEvent`。

`ChainNode`：

```ts
export type ChainNode = {
  name: string
  companies?: string[]
  children?: ChainNode[]
  uncertainties?: Uncertainty[]
}
```

- [ ] **Step 4: 实现统一 HTTP 错误映射测试**

mock fetch 返回：

```json
{"error":{"code":"REVIEW_VERSION_CONFLICT","message":"审核版本已变化"}}
```

断言 client 抛 `ApiError`，页面不直接解析任意 response shape。

- [ ] **Step 5: 写批准的全局 CSS token**

```css
:root {
  --bg: #FAF6F0;
  --surface: #FFFDFC;
  --surface-secondary: #F7EFE7;
  --border: #E9DCD1;
  --text: #2E2622;
  --text-secondary: #776C65;
  --primary: #C65F49;
  --primary-hover: #B8533F;
  --warning: #D9913D;
  --success: #78906B;
  --error: #B85F55;
  font-family: Inter, -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
}
```

卡片圆角 10–12px、1px warm border、轻 shadow；不写 gradient/glass/neon/dark mode。

- [ ] **Step 6: 运行前端测试和 build**

```bash
cd skills/researching-industry-chains/web
npm test -- --run
npm run build
```

Expected: PASS and `src/industry_chain_skills/web_dist/index.html` exists.

- [ ] **Step 7: Commit**

```bash
git add skills/researching-industry-chains/web skills/researching-industry-chains/.gitignore .gitignore
git commit -m "feat(web): scaffold react review workbench"
```

---

### Task 6: 实现 Runner Picker、Workspace shell 和极薄 Dashboard

**Files:**
- Create: `web/src/router.tsx`
- Create: `web/src/components/Sidebar.tsx`
- Create: `web/src/components/MetricCard.tsx`
- Create: `web/src/components/StatusBadge.tsx`
- Create: `web/src/pages/RunnerPickerPage.tsx`
- Create: `web/src/pages/WorkspacePage.tsx`
- Create: `web/src/pages/DashboardPage.tsx`
- Create tests under matching `*.test.tsx` files.

**Interfaces:**
- Routes exactly:

```text
/runners
/runners/:runnerId
/runners/:runnerId/reviews
/runners/:runnerId/reviews/:reviewId
/runners/:runnerId/progress
/runners/:runnerId/completed
```

- [ ] **Step 1: 写 Sidebar/route 失败测试**

断言侧边栏只出现：当前 Runner、工作台、待审核、任务进度、已完成、切换 Runner；不出现用户头像、通知、知识库、数据源、Agent 管理、统计分析、设置中心。

- [ ] **Step 2: 实现 Runner Picker**

Runner card 显示名称、创建时间、`已完成 / 总主题`、待人工审核、AI处理中、最近更新时间。删除按钮弹出确认框，必须输入 `删除` 才调用 DELETE。

- [ ] **Step 3: 实现 Workspace shell**

`WorkspacePage` 负责获取当前 runner 基本信息并渲染 Sidebar + `<Outlet />`，不复制页面级业务数据。

- [ ] **Step 4: 实现 Dashboard 四指标**

只允许：

```text
待人工审核
AI处理中
已交回AI
今日完成
```

其下最多最近 3 个待审来源 + 少量 Activity；不实现趋势图、环比、企业总量、模型成功率、审核效率和 Worker 排行。

- [ ] **Step 5: 运行组件测试**

```bash
cd skills/researching-industry-chains/web
npm test -- --run RunnerPicker Sidebar Dashboard
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/researching-industry-chains/web/src
git commit -m "feat(web): add runner workspace shell"
```

---

### Task 7: 实现 Quick Review 严格只读流程

**Files:**
- Create: `web/src/pages/ReviewsPage.tsx`
- Create: `web/src/components/ReviewQueue.tsx`
- Create: `web/src/components/ReadOnlyTree.tsx`
- Create: `web/src/components/EvidenceList.tsx`
- Create: `web/src/components/ReviewActions.tsx`
- Create tests.

**Interfaces:**
- Quick Review 三栏：`审核队列 | 来源 / Tree 快速预览 | 审核处理`。
- Quick actions：`查看审核依据、打开完整审核、采用当前结果、交回 AI 继续、驳回来源`。

- [ ] **Step 1: 写“没有编辑控件”失败测试**

选择一个 review 后断言：页面能看到 description、Tree、uncertainty、Evidence；看不到节点输入框、add child、drag handle、企业编辑按钮或 description textarea。

- [ ] **Step 2: 实现 queue 与 preview**

队列项显示 topic、source.name、URL 可读部分、status、uncertainty count、updated_at。

Preview 只读 Tree；`chain=[]` 显示“当前没有可编辑草稿”，不显示空 Tree 编辑器。

- [ ] **Step 3: 实现 EvidenceList**

Evidence 卡只渲染：

```text
locator
description
```

无 evidence 时显示 uncertainty message + “打开原来源”；不创建图片占位、OCR、截图上传或 Lightbox。

- [ ] **Step 4: 实现 Quick actions**

- `采用当前结果`：chain 非空时 POST approve，body 使用当前 description + chain + expected_version。
- `交回 AI 继续`：POST return-to-agent。
- `驳回来源`：POST reject。
- chain=[] 时隐藏/禁用 approve，只留 return/reject。
- 不做批量 approve。

- [ ] **Step 5: 运行测试**

```bash
cd skills/researching-industry-chains/web
npm test -- --run ReviewsPage ReviewQueue ReadOnlyTree EvidenceList
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/researching-industry-chains/web/src/pages/ReviewsPage.tsx skills/researching-industry-chains/web/src/components
git commit -m "feat(web): add read only quick review"
```

---

### Task 8: 先做可独立测试的 Tree 编辑领域函数

**Files:**
- Create: `web/src/domain/tree.ts`
- Create: `web/src/domain/tree.test.ts`
- Create: `web/src/domain/review.ts`
- Create: `web/src/domain/review.test.ts`

**Interfaces:**

```ts
export type EditableNode = {
  uiId: string
  name: string
  companies: string[]
  children: EditableNode[]
}

export function hydrateTree(chain: ChainNode[]): EditableNode[]
export function serializeTree(tree: EditableNode[]): ChainNode[]
export function addRoot(tree: EditableNode[], name: string): EditableNode[]
export function addChild(tree: EditableNode[], parentId: string, name: string): EditableNode[]
export function removeNode(tree: EditableNode[], nodeId: string): EditableNode[]
export function moveSubtree(tree: EditableNode[], nodeId: string, targetParentId: string | null, targetIndex: number): EditableNode[]
export function moveCompany(tree: EditableNode[], company: string, fromNodeId: string, toNodeId: string): EditableNode[]
export function maxTreeDepth(tree: EditableNode[]): number
```

- [ ] **Step 1: 写 hydrate/serialize 测试**

`hydrateTree` 生成仅前端存在的 `uiId`，同时剥离 node uncertainties；`serializeTree` 只输出 `name + 非空 companies + 非空 children`，不把 `uiId`、focus、uncertainties 写回最终 Tree。

- [ ] **Step 2: 写同父排序和跨父 reparent 测试**

```ts
it("moves the whole subtree under a new parent", () => {
  const result = moveSubtree(tree, "B", "X", 0)
  expect(findNode(result, "B")?.children.map(n => n.name)).toEqual(["C", "D"])
  expect(findParent(result, "B")?.name).toBe("X")
})
```

- [ ] **Step 3: 写循环和四层 guard 测试**

`moveSubtree` 必须拒绝：node→自己、node→后代、移动后任意后代深度 >4。函数返回 typed domain error，例如：

```ts
throw new TreeEditError("TREE_CYCLE", "节点不能移动到自己或后代下面")
throw new TreeEditError("TREE_DEPTH_EXCEEDED", "产业链正式分类最多支持 4 层")
```

- [ ] **Step 4: 写公司增删改/移动测试**

同节点公司保持数组顺序；移动只改变明确指定的 company occurrence，不根据同名企业全局搜索后批量移动。

- [ ] **Step 5: 实现 uncertainty→focus 派生**

`review.ts` 把：

```text
root uncertainty → source focus
node uncertainty → node uiId focus
node uncertainty + company → node uiId + company focus
```

focus 只存在浏览器内存，不进入 API write payload。

- [ ] **Step 6: 运行 domain tests**

```bash
cd skills/researching-industry-chains/web
npm test -- --run src/domain/tree.test.ts src/domain/review.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add skills/researching-industry-chains/web/src/domain
git commit -m "feat(web): add tree editing domain"
```

---

### Task 9: 实现 Full Review 唯一编辑面

**Files:**
- Create: `web/src/pages/ReviewDetailPage.tsx`
- Create: `web/src/components/TreeEditor.tsx`
- Create: `web/src/components/TreeNodeEditor.tsx`
- Create: `web/src/components/NodeInspector.tsx`
- Create: `web/src/components/ReviewContextPanel.tsx`
- Create tests.

**Interfaces:**
- 布局：`审核依据 25% | 产业链草稿 50% | 审核处理 25%`。
- working copy：`EditableNode[] + description`。
- dirty=false → “采用当前结果”；dirty=true → “修正后通过”。

- [ ] **Step 1: 写 Full Review 基础渲染测试**

必须显示：topic、source.name、source.url、打开原来源、review 状态、`来源说明（最终备注）` textarea、Tree、审核处理栏。

不得出现 question/radio/checkbox answer/recommended answer。

- [ ] **Step 2: 实现 description working copy**

用户修改 description 只改本地状态，不逐按键写 API；dirty state 与原始值比较。

- [ ] **Step 3: 实现节点和企业编辑**

支持：rename、add root/sibling/child、delete、父级选择器、企业 add/delete/rename/move。删除有子树节点前必须显示包含后代数量的确认文案。

- [ ] **Step 4: 用 dnd-kit 接上 Task 8 的 moveSubtree**

UI drag 只负责确定 `nodeId + targetParentId + targetIndex`，实际规则统一调用 `moveSubtree()`；不在组件里复制 cycle/depth 逻辑。

- [ ] **Step 5: 实现右侧 Review Context / Inspector 单栏切换**

默认右栏显示当前 uncertainty message、target（来源/节点路径/企业 occurrence）、相关 Evidence locator、来源级 actions。

点击 Tree node/company 时同一右栏切换 NodeInspector；关闭 Inspector 回审核处理。不增加第四列。

- [ ] **Step 6: 实现 chain=[] 限制**

初始 chain=[] 时不 hydrate TreeEditor，不显示 add root；只显示来源说明、uncertainty/Evidence、return/reject。

- [ ] **Step 7: 运行组件测试**

```bash
cd skills/researching-industry-chains/web
npm test -- --run ReviewDetailPage TreeEditor ReviewContextPanel
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add skills/researching-industry-chains/web/src/pages/ReviewDetailPage.tsx skills/researching-industry-chains/web/src/components
git commit -m "feat(web): add full tree review editor"
```

---

### Task 10: 实现 Full Review 提交、version conflict 和本地 working copy 恢复

**Files:**
- Modify: `web/src/pages/ReviewDetailPage.tsx`
- Create: `web/src/hooks/useReviewDraft.ts`
- Create: `web/src/hooks/usePolling.ts`
- Create tests.

**Interfaces:**
- localStorage key：`industry-chain-review:{runnerId}:{reviewId}:v{version}`。
- approve payload：`expected_version + description + serializeTree(tree)`。

- [ ] **Step 1: 写 localStorage version 隔离测试**

同 review version=3 保存的草稿不能自动应用到 version=4；version 匹配时刷新页面可恢复 description/Tree。

- [ ] **Step 2: 实现 useReviewDraft**

保存内容：

```ts
{
  version: number,
  description: string,
  tree: EditableNode[],
  savedAt: string,
}
```

approve 成功后清除该 version localStorage。

- [ ] **Step 3: 实现 approve/return/reject 提交状态**

提交期间按钮禁用；成功后刷新 review queue/跳回待审核；业务错误原样显示中文 message。

- [ ] **Step 4: 实现 409 REVIEW_VERSION_CONFLICT**

出现 409 时：不覆盖 working copy，显示“审核结果已被更新”，提供“重新加载最新版本”和“保留当前本地草稿”说明；不自动 merge。

- [ ] **Step 5: 实现 Full Review 只检测版本、不自动覆盖**

后台可以每 10s GET review detail，仅比较 `version`；相同 version 不动作，不同 version 显示 banner，绝不替换当前 tree/description。

- [ ] **Step 6: 运行测试**

```bash
cd skills/researching-industry-chains/web
npm test -- --run useReviewDraft ReviewDetailPage
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add skills/researching-industry-chains/web/src/hooks skills/researching-industry-chains/web/src/pages/ReviewDetailPage.tsx
git commit -m "feat(web): protect review working copies"
```

---

### Task 11: 实现 Progress、Completed 和剩余轮询

**Files:**
- Create: `web/src/pages/ProgressPage.tsx`
- Create: `web/src/pages/CompletedPage.tsx`
- Create: `web/src/components/ActivityList.tsx`
- Modify: Dashboard/Reviews pages to use polling.
- Create tests.

**Interfaces:**
- polling：Dashboard 5s、Progress 5s、Review queue 10s。
- topic label：

```text
pending              等待处理
in_progress          AI处理中
awaiting_review      待人工审核
completed            已完成
no_qualified_source  无合格来源
failed               执行异常
```

- [ ] **Step 1: 写 Progress 分类测试**

推荐四列：`等待处理 | AI处理中 | 待人工 | 已完成`；`no_qualified_source` 放已完成列但保留“无合格来源”子标签。

- [ ] **Step 2: 实现 Progress read-only 页面**

顶部显示 `已完成 / 总主题`，禁止拖拽状态。worker_label 若存在只作为观察信息。

- [ ] **Step 3: 实现 Completed 页面**

支持搜索 topic、查看最终来源、最终 Tree、description、简要审核记录和打开 URL。正式来源 Tree 从 API 已反投影的 chain 显示，不做 XLSX 网页表格编辑器。

- [ ] **Step 4: 实现 ActivityList**

只展示 Core 记录的最小业务事实；不显示 Prompt、token、完整推理、截图或浏览器日志。

- [ ] **Step 5: 接上页面 polling**

使用统一 `usePolling`，组件 unmount 时清 timer；网络失败保留上一份成功数据并显示轻量错误，不清空页面。

- [ ] **Step 6: 运行测试**

```bash
cd skills/researching-industry-chains/web
npm test -- --run ProgressPage CompletedPage ActivityList
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add skills/researching-industry-chains/web/src/pages skills/researching-industry-chains/web/src/components/ActivityList.tsx
git commit -m "feat(web): add progress and completed views"
```

---

### Task 12: 完成视觉收口、build/serve 联调和当前文档

**Files:**
- Modify: `web/src/styles.css` and component CSS as needed
- Modify: `README.md`
- Modify: `USAGE.md`
- Modify: `AGENTS.md` only if Web runtime boundary is not yet reflected
- Create/Modify: tests for final API/static smoke as needed

**Interfaces:**
- `industry-chain web` after `npm run build` must serve the production UI at `127.0.0.1:8765`。

- [ ] **Step 1: 对照视觉 token 做一次 UI 收口**

检查：暖象牙背景、白暖 surface、陶土主色、琥珀 review、sage success、muted brick error；卡片圆角 10–12px、低阴影、无 dark mode/gradient/glass/neon。

- [ ] **Step 2: 验证窄屏和常规桌面布局**

重点不是做手机产品，而是确保 1280px/1440px 桌面下三栏不溢出；小窗口允许侧栏收窄和 Full Review 横向最小宽度提示，不把三栏硬压成无法审核的卡片流。

- [ ] **Step 3: build 前端**

```bash
cd skills/researching-industry-chains/web
npm test -- --run
npm run build
```

Expected: `../src/industry_chain_skills/web_dist/index.html` generated.

- [ ] **Step 4: 跑 Python 全量测试**

```bash
cd skills/researching-industry-chains
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 5: 本地启动 smoke**

```bash
python run_cli.py --runs-root /tmp/industry-chain-web-smoke web --no-browser
```

手动请求：

```text
GET http://127.0.0.1:8765/api/health → {"ok": true}
GET http://127.0.0.1:8765/runners → React app
```

- [ ] **Step 6: 按 spec 完成业务验收**

至少人工走通：Runner Picker → Dashboard → Quick Review → Full Review 修改 description + Tree → approve → Completed；再走一条 chain=[] review → return/reject；再制造旧 expected_version → 409 banner。

- [ ] **Step 7: 更新 README/USAGE 当前行为**

只写当前用法：安装 Python 包、前端首次 `npm install && npm run build`、`industry-chain web`、Runner/HITL 入口。不要写迁移历史、旧 UI 或旧 CLI 比较。

- [ ] **Step 8: Commit**

```bash
git add README.md USAGE.md AGENTS.md skills/researching-industry-chains/web skills/researching-industry-chains/src/industry_chain_skills/web_app.py
git commit -m "docs(web): finalize local hitl workflow"
```

---

## Final Verification

- [ ] Core plan `docs/superpowers/plans/2026-09-03-industry-chain-hitl-core.md` 已全部完成并通过测试。
- [ ] `cd skills/researching-industry-chains/web && npm test -- --run && npm run build` 全绿。
- [ ] `cd skills/researching-industry-chains && PYTHONPATH=src python -m unittest discover -s tests -v` 全绿。
- [ ] `industry-chain web` 默认只绑定 `127.0.0.1:8765`。
- [ ] Browser 不可读取任何 claim token。
- [ ] Quick Review 没有任何 Tree/description 编辑入口。
- [ ] Full Review 是唯一编辑面，支持同父排序、跨父整棵子树移动、cycle guard 和 4 层 guard。
- [ ] Evidence UI 只有 locator + description + 打开原来源，没有图片 asset/viewer。
- [ ] chain=[] review 无法从零建链。
- [ ] approve 后 XLSX 只有九列，第一行备注等于最终 description。
- [ ] `completed + no_qualified_source` 都计入“已完成”，但后者仍显示“无合格来源”。
- [ ] Runner 有有效 topic/review claim 时 DELETE 返回冲突，不提供 force delete。
- [ ] 409 version conflict 不静默覆盖浏览器 working copy。
