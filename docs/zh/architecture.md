# 架构

深入介绍 HiveFlow 的架构与设计决策。

---

## 概览

HiveFlow 是一个**三层**多智能体编排系统：

```
┌─────────────────────────────────────────────────────────────┐
│                    HiveFlow Studio (Web UI)                 │
│  Visual workflow builder, analytics, plugin marketplace     │
└─────────────────────────────┬───────────────────────────────┘
                              │ REST API + WebSocket (SSE)
┌─────────────────────────────▼───────────────────────────────┐
│                   HiveFlow Agent Runtime                    │
│  ReAct workers, intent parsing, memory management, tools    │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                    HiveFlow Core Engine                     │
│  Event Bus, Scheduler, Blackboard, Cell, Orchestrator       │
└─────────────────────────────────────────────────────────────┘
```

---

<a id="layer-1-core-engine"></a>

## 第一层：Core 引擎

基础层提供核心原语：

### Event Bus（事件总线）
- 发布/订阅模式，实现解耦通信
- 事件类型：`intent.new`、`task.assigned`、`task.completed`、`task.failed`
- 支持同步与异步订阅者

### Scheduler（调度器）
- 三种调度策略：least-loaded、auction、global load-aware
- 管理 Worker 池中的任务分发
- 可配置并发上限

### Cell
- 监督树模式
- 管理 Worker 生命周期（启动、空闲、工作中、停止）
- 处理 Worker 失败恢复

### Blackboard（黑板）
- Agent 间通信的共享内存
- 基于权限的访问控制（读/写键）
- 多种后端：内存、Redis、加密

### Orchestrator（编排器）
- 静态工作流的 DAG 编排器
- 运行时计划生成的动态编排器
- 自适应路由的认知编排器

---

## 第二层：Agent 运行时

在 Core 之上提供智能 Agent 行为：

### ReAct Worker
- Reasoning + Acting 循环
- 通过 MCP 协议使用工具
- 失败时自我纠正

### Intent Parser（Intent 解析器）
- 将用户输入解析为结构化 Intent
- 提取所需 Skill 与上下文
- 支持多轮对话

### Memory Manager（内存管理器）
- 短期记忆（上下文窗口）
- 长期记忆（向量存储）
- 情景记忆（交互历史）

### Tools（工具）
- Blackboard 工具（读/写/搜索）
- 代码执行（沙箱）
- 文件 I/O
- HTTP 请求
- 网页搜索
- 记忆操作

---

## 第三层：Studio

可视化编排与管理平台：

### Backend（FastAPI）
- 面向所有操作的 RESTful API
- 实时流式 WebSocket
- SQLite/PostgreSQL/MongoDB 持久化

### Frontend（React + TypeScript）
- 可视化工作流构建器（基于节点）
- 分析仪表盘
- 插件市场
- LLM 配置管理
- 知识库管理
- 变量与触发器管理

---

## 安全模型

### 纵深防御

1. **Input Guards（输入守卫）**：验证并清洗所有入站数据
2. **Output Guards（输出守卫）**：过滤并验证所有出站数据
3. **Encrypted Blackboard（加密黑板）**：敏感数据采用 AES-256 加密
4. **Audit Logging（审计日志）**：完整记录所有操作
5. **Permission System（权限系统）**：细粒度读/写访问控制

---

## 可扩展性

### 自定义后端
实现以下抽象基类：
- `BlackboardBackend` — 自定义存储
- `CheckpointBackend` — 自定义状态持久化
- `Guard` — 自定义验证规则

### 自定义调度器
继承 `BaseScheduler` 实现自定义调度逻辑。

### 自定义 Worker
实现带专用工具集的自定义 Worker 类型。

### 插件系统
MCP 兼容插件，用于工具集成。

---

## 性能考量

- 全链路异步优先设计
- 外部服务连接池
- 可配置并发上限
- 基于 TTL 的缓存过期
- 大型数据结构的懒加载
