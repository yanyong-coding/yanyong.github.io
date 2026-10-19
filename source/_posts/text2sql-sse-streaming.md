---
title: Text2SQL 对话问答改造为 SSE 流式输出
date: 2026-10-11 22:00:00
tags:
  - Text2SQL
  - SSE
  - Spring Boot
  - Vue3
  - 架构设计
categories:
  - 设计文档
---

> 本文记录 **Text2SQL 智能查询系统** 对话问答模块从「同步阻塞 HTTP」改造为「SSE 流式输出」的设计方案与落地结果。

## 一、背景与目标

改造前，对话问答是**同步阻塞**链路：

```
ChatController.send() → ChatService.send()(@Transactional)
   → Text2SqlService.query()  // Schema 采集 → Linking → 提示词 → 生成 → 校验 → 执行 → 失败回喂
   → 一次性返回
```

整条管线要跑十几秒，前端只能转圈，**中间过程完全不可见**。

企业级 Text2SQL 产品需要三点能力：

- **过程可见**：每一步在做什么（采集 Schema、召回相关表、组装提示词、生成、执行……）；
- **结果渐显**：SQL 逐字生成，而非一次性蹦出；
- **可中断**：用户可随时停止本次生成。

因此将对话改造为 **SSE（Server-Sent Events）流式**：

- 后端按管线阶段实时推送 `stage` 事件；
- SQL 生成过程逐字推送 `token` 事件；
- 最终以 `sql` / `result` / `done` 事件下发结构化结果。

**关键决策**：流式粒度 = 「阶段进度 + SQL 逐字流式」；**移除原同步接口，全部走流式**。

**技术约束**：后端是 Spring MVC（`spring-boot-starter-web`，**没有 WebFlux**），所以采用 `SseEmitter` + 业务线程池异步执行；管线本身是阻塞式的（JDBC 采集/执行、模型网关调用），必须在独立线程运行，避免占用 Web 容器线程。

## 二、总体架构

```
浏览器 (fetch + ReadableStream)
    │  POST /api/chat/stream   (Accept: text/event-stream)
    ▼
ChatController.stream()  ──► 返回 SseEmitter
    │  chatSseExecutor.execute(...)          ← 独立线程池，不占用容器线程
    ▼
ChatService.stream(req, listener)
    │  落库 user 消息
    ▼
Text2SqlService.queryStream(..., listener)
    │  schema → retrieve → prompt → generate → executing（失败则 repair 回喂）
    ▼
SqlGatewayRouter → MockSqlGateway / AgentScopeSqlGateway
    │  生成过程中逐块 emit("token", ...)
    ▼
listener.emit(event, data)  ──► ObjectMapper 序列化 ──► SseEmitter.send()
```

核心是**一处抽象、两条链路复用**：`SqlProgressListener` 作为进度回调契约，非流式调用传入 `NOOP` 即可零成本忽略。

## 三、SSE 事件契约

前后端约定的完整事件表：

| event | 时机 | data |
|---|---|---|
| `meta` | 会话解析/创建后立即发 | `{sessionId, question}` |
| `stage` | 管线各阶段 | `{stage, message, ...extras}` |
| `token` | SQL 生成中 | `{text}` |
| `sql` | 得到 SQL | `{sql, explanation, strategy, provider, linkedTables, repairCount}` |
| `result` | 执行成功 | `{columns, rows, rowCount, truncated}` |
| `done` | 收尾 | `{success, costMs, repairCount, messageId, sessionId}` |
| `error` | 失败/入参非法 | `{message}` |

`stage` 的取值：`schema`（采集 Schema）、`retrieve`（Schema Linking 召回）、`prompt`（组装提示词）、`generate`（调用模型生成）、`executing`（安全校验 + 受限执行）、`repair`（执行失败回喂重写）。

## 四、后端设计

### 4.1 进度回调抽象

```java
public interface SqlProgressListener {
    void emit(String event, Object data);

    /** 空实现：评测、同步调用直接使用，零成本忽略 */
    SqlProgressListener NOOP = (event, data) -> {};
}
```

最简契约：事件名 + 任意可 JSON 序列化的数据。序列化交给 SSE 层，管线不感知传输细节。

### 4.2 网关的流式能力与降级

在网关接口上以 **default 方法** 扩展流式重载，保证已有的匿名实现（如测试里的 fake 网关）不受影响：

```java
default SqlGenResult generate(SqlGenRequest request, SqlProgressListener listener) {
    return generate(request);   // 默认不支持流式 → 自动降级为非流式
}
```

- `MockSqlGateway`：先按规则命中模板 SQL，再按块（每 4 字符）`emit("token", Map.of("text", chunk))`，块间加极短延时，制造可视化「打字机」效果；
- `AgentScopeSqlGateway`：调用 `agent.stream(...)` 订阅增量事件，逐段 `emit("token", ...)`，最终解析 JSON 得到 `sql`/`explanation`。**若上游流式 API 形态不符，则回退到默认非流式方法**（此时仅 `stage` 流式，`token` 不流）。

`SqlGatewayRouter` 增加一行转发重载，路由层无需改动选择逻辑。

### 4.3 管线埋点

`Text2SqlService` 新增 `queryStream(datasource, question, strategy, listener)`，把原 `query()` 改为委托 `queryStream(..., NOOP)`——**公开签名与行为完全不变**，评测引擎 `EvalService` 与原有测试继续用 `query()`。

在 `generateInternal` 与失败回喂循环中埋点：

```java
// Schema 采集完成后
listener.emit("stage", stage("schema", "采集数据源 Schema", Map.of("tables", allTables.size())));
// Schema Linking 召回后
listener.emit("stage", stage("retrieve", "Schema Linking 召回相关表",
    Map.of("tables", topTables.stream().map(t -> t.table.getTableName()).toList(),
           "columns", topTables.stream().mapToInt(t -> t.columns.size()).sum())));
// 得到 SQL 后
listener.emit("sql", Map.of("sql", gen.getSql(), "explanation", ..., "repairCount", round));
```

一个细节：`Map.of()` 不允许 null 值，因此对 `explanation` 等可空字段统一用 `StrUtil.nullToEmpty(...)` 兜底，列表字段用 `List.of()` 兜底。

### 4.4 对话服务与控制器

`ChatService` 的改造要点：

- **移除** `@Transactional`，改为 `ChatSendResponse stream(ChatSendRequest req, SqlProgressListener listener)`；
- 流程：`emit(meta)` → 落库 user 消息 → `queryStream(...)` → 落库 assistant 消息 → `emit(result)` / `emit(error)` → `emit(done)`；
- 入参非法（数据源/会话不存在）**不抛给 SSE**，而是 `emit("error", ...)` 后正常返回失败响应。

**事务取舍**：流式方法跨秒级，不能用 `@Transactional` 包住整段；三次 insert（会话 + user 消息 + assistant 消息）各自自动提交，聊天场景可接受。

控制器**移除** `POST /api/chat`，新增：

```java
@PostMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
public SseEmitter stream(@RequestBody ChatSendRequest req) {
    SseEmitter emitter = new SseEmitter(180_000L);
    emitter.onTimeout(emitter::complete);
    SqlProgressListener listener = (event, data) -> {
        try {
            // 关键：先用 ObjectMapper 序列化成 JSON 字符串，避免二次编码
            emitter.send(SseEmitter.event().name(event)
                .data(objectMapper.writeValueAsString(data)));
        } catch (Exception e) {
            // 客户端断开或已完成：忽略，避免中断业务线程
        }
    };
    chatSseExecutor.execute(() -> {
        try { chatService.stream(req, listener); emitter.complete(); }
        catch (Exception e) { emitter.completeWithError(e); }
    });
    return emitter;
}
```

`GET /sessions`、`GET /session/{id}/history` 保持不变。

### 4.5 专用线程池

```java
@Bean("chatSseExecutor")
public Executor chatSseExecutor() {
    ThreadPoolTaskExecutor e = new ThreadPoolTaskExecutor();
    e.setCorePoolSize(4);
    e.setMaxPoolSize(16);
    e.setQueueCapacity(64);
    e.setThreadNamePrefix("chat-sse-");
    e.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
    e.initialize();
    return e;
}
```

每个 SSE 请求提交一个任务；不启用 `@EnableAsync`，手动 submit，边界更清晰。

## 五、前端设计

### 5.1 SSE 客户端

`EventSource` **不支持 POST 携带 body**，而我们的问答需要 JSON 请求体，因此用 `fetch` + `ReadableStream` 手写 SSE 帧解析：

```js
export async function streamChat(payload, { onEvent, signal } = {}) {
  const resp = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(payload),
    signal                       // AbortSignal：支持「停止」
  })
  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    buffer = buffer.replace(/\r\n/g, '\n')
    let idx
    while ((idx = buffer.indexOf('\n\n')) >= 0) {   // SSE 以空行分隔帧
      dispatch(buffer.slice(0, idx))
      buffer = buffer.slice(idx + 2)
    }
  }
  if (buffer.trim()) dispatch(buffer)               // 收尾残留帧
}
```

不走 axios 拦截器——SSE 的 `data` 不是统一的 `Result{code,message,data}` 包装，需要原始的逐帧事件。

### 5.2 流式渲染与交互

`ChatView` 的 `send()` 重写为事件驱动：先 push 一条 assistant 占位消息（含 `stages: []`、`sqlPreview: ''`、`streaming: true`），再创建 `AbortController`，把事件分发到消息对象的相应字段：

| 事件 | 前端处理 |
|---|---|
| `meta` | 记录 `sessionId`，刷新会话列表 |
| `stage` | push 进消息的 `stages` 数组 |
| `token` | `sqlPreview += text` |
| `sql` | 填充 SQL / 解释 / 策略 / 关联表 / 修复次数 |
| `result` | 填充列、行、行数、截断标记 |
| `done` | 收尾，`streaming = false` |
| `error` | 记录错误信息 |

UI 新增三块：

- **「执行过程」时间线**：用 `el-timeline` 渲染 `stages`，进行中显示「进行中」标签，完成后变「已完成」——即把「思考过程」可视化；
- **SQL 逐字预览块**：流式期间展示 `sqlPreview` 与闪烁光标，`sql` 事件到达后替换为最终 SQL；
- **停止按钮**：流式中「发送」变为红色「停止」，点击调用 `abort()`。

> 一个实践中的小坑：`el-timeline-item` 的 `size` 属性只接受 `normal` / `large`，传 `small` 会触发控制台告警——移除即可（默认 `normal` 已满足紧凑需求）。

## 六、关键设计取舍

1. **SseEmitter vs WebFlux**：现有栈是 Spring MVC，引入 WebFlux 会带来双栈复杂度；`SseEmitter` + 线程池足以支撑，改动面最小。
2. **网关流式用 default 方法**：接口向后兼容，旧实现零改动、自动降级，避免「一刀切」改所有实现。
3. **`query()` 保留并委托 `queryStream()`**：评测引擎与大量既有测试无需改动，行为不变。
4. **去掉 `@Transactional`**：流式跨秒级，长事务不可取；聊天场景下多条消息分开自动提交可接受。
5. **JSON 先序列化再 send**：避免 `SseEmitter` 对字符串再做一次编码导致双层引号。

## 七、验证与结果

**后端回归**：`mvn test` → **83/83 通过**（含改后的 `ChatServiceTest` 与新增的 `Text2SqlServiceStreamTest`）。

**SSE 直连**（`curl -N -X POST /api/chat/stream`）实测事件序列：

```
event:meta      data:{"sessionId":5,"question":"一共有多少个订单"}
event:stage     data:{"stage":"schema","message":"采集数据源 Schema","tables":5}
event:stage     data:{"stage":"retrieve",...,"tables":["orders","payments","products","stores","users"]}
event:stage     data:{"stage":"prompt","message":"组装提示词（Schema 线性化 + Few-shot）"}
event:stage     data:{"stage":"generate","message":"调用模型生成 SQL","round":0}
event:token     data:{"text":"SELE"}   ...（共 11 个 token 帧）...   data:{"text":"rs"}
event:sql       data:{"sql":"SELECT COUNT(*) AS order_count FROM orders","strategy":"L2",...}
event:stage     data:{"stage":"executing","message":"安全校验 + 受限执行"}
event:result    data:{"columns":["order_count"],"rows":[{"order_count":24}],"rowCount":1,"truncated":false}
event:done      data:{"success":true,"costMs":537,"repairCount":0,"messageId":10,"sessionId":5}
```

**前端**：`npm run build` 通过；浏览器实测时间线逐步推进、SQL、结果表格（`order_count=24`）均正确渲染，控制台与网络无错误。

> 说明：由于 Mock 网关约 0.5s 即返回，浏览器截图间隔内流已结束，「逐字打字 + 停止按钮」的中间态难以捕捉；这是响应过快所致，接入真实模型后 token 流会持续数秒，动效将清晰可见。

## 八、后续规划

- 接入真实模型（`text2sql.llm.provider=agentscope`）后，`token` 事件由模型自身增量产出，无需再模拟分块；
- 可进一步把「错误回喂」的每一轮候选也通过事件外推，形成完整的「自愈」可视化；
- 事件契约保持稳定，后续新增事件（如 `plan`、`candidates`）只需扩展 `event` 枚举，前后端解耦。