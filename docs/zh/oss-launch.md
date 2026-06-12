# 开源发布清单

完整清单见仓库根目录 [OSS_LAUNCH.md](https://github.com/hiveflow/hiveflow/blob/main/OSS_LAUNCH.md)。

## Phase 0 — 第 1～3 天（公开分发）

| 天 | 任务 | 负责 | 状态 |
|----|------|------|------|
| 1 | 创建 GitHub org `hiveflow`、公开仓库、推送 `main` | 维护者 | ⬜ |
| 1 | 启用 **Discussions** + **Security Advisories** | 维护者 | ⬜ |
| 1 | Settings → Pages → **GitHub Actions** | 维护者 | ⬜ |
| 2 | 添加 Secret `PYPI_API_TOKEN` | 维护者 | ⬜ |
| 2 | 打 tag 发布：`git tag v0.1.0 && git push origin v0.1.0` | 维护者 | ⬜ |
| 3 | README Golden Path（Docker → Studio Agent） | 仓库 | ✅ |
| 3 | `docker compose up --build` 默认路径 | 仓库 | ✅ |
| 3 | 2 人盲测（≤30 分钟完成首次 plan） | 团队 | ⬜ |

本地自动化验证：

```bash
python scripts/verify_launch_readiness.py
```

## 仅维护者操作

1. 创建公开 GitHub org/repo
2. 添加 `PYPI_API_TOKEN` secret → 打 tag `v0.1.0`
3. 启用 GitHub Pages + Discussions
4. 将 demo GIF 添加到 `docs/assets/`
