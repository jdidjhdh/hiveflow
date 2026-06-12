# 发布后续清单（GitHub push 之后）

仓库：**https://github.com/jdidjhdh/hiveflow**

首次 `git push` 到 `main` 后按此清单操作。标注 **（网页）** 的需在 GitHub 设置中完成；**（本地）** 可在本机执行。

---

## 第 1 天 — 让仓库可用

| # | 任务 | 操作 |
|---|------|------|
| 1 | **确认 main 上 CI 通过** **（网页）** | [Actions → Test](https://github.com/jdidjhdh/hiveflow/actions/workflows/test.yml) |
| 2 | **启用 GitHub Pages** **（网页）** | Settings → Pages → Source: **GitHub Actions** |
| 3 | **确认文档部署** **（网页）** | [Actions → Docs](https://github.com/jdidjhdh/hiveflow/actions/workflows/docs.yml) → **https://jdidjhdh.github.io/hiveflow/zh/** |
| 4 | **启用 Discussions** **（网页）** | Settings → General → Features → **Discussions** ✓ |
| 5 | **安全公告** **（网页）** | Settings → Security → 私密漏洞报告（可选） |
| 6 | **仓库 About** **（网页）** | 描述 + 网站链接 + Topics |

**本地验证：**

```bash
git clone https://github.com/jdidjhdh/hiveflow.git
cd hiveflow
python scripts/verify_launch_readiness.py
```

---

## 第 2 天 — PyPI（可选，建议做）

| # | 任务 | 操作 |
|---|------|------|
| 1 | 注册 PyPI + 创建 API Token | https://pypi.org/manage/account/token/ |
| 2 | 添加 Secret **（网页）** | 仓库 Settings → Secrets → `PYPI_API_TOKEN` |
| 3 | 打 tag **（本地）** | 见下方命令 |
| 4 | 确认包已发布 | `hiveflow` 与 `hiveflow-agent` |

```bash
git tag v0.1.0
git push origin v0.1.0
```

会触发 [release.yml](https://github.com/jdidjhdh/hiveflow/blob/main/.github/workflows/release.yml)。

---

## 第 3 天 — 首次用户路径

| # | 任务 | 操作 |
|---|------|------|
| 1 | **盲测 Golden Path** | 新人 `docker compose up --build` → Studio plan-only → 执行（≤30 分钟） |
| 2 | **PyPI 路径** | `pip install hiveflow` → 跑 `examples/01_hello_hiveflow.py` |
| 3 | **Dependabot** **（网页）** | 批量依赖 PR 可先关闭，按需再合并 |

---

## 常用链接

| 资源 | URL |
|------|-----|
| 仓库 | https://github.com/jdidjhdh/hiveflow |
| 文档（中文） | https://jdidjhdh.github.io/hiveflow/zh/ |
| CI | https://github.com/jdidjhdh/hiveflow/actions |
| 质量门禁 | [quality-gates.md](quality-gates.md) |
