# API 端点模块变更记录

## 2024-12-19

### 重大重构：方案 2 架构实施 - analyzer.py 为主统一业务接口

**思考过程：**
经过详细分析，发现 analyzer.py、streams.py、tasks.py、alarms.py 存在大量功能重复，导致：

- 前端调用混乱，不知道该调用哪个接口
- 代码重复维护，增加开发成本
- API 响应格式不统一
- 功能职责不清晰

基于用户的 AI 监控告警场景（算法检测 → 条件匹配 → 触发告警 → 自动保存告警视频/图片），决定采用方案 2：**analyzer.py 为主统一业务接口**。

**修改内容：**

#### 1. 重构 analyzer.py - 统一业务接口

**集成功能：**

- **系统控制**：保留原有的分析器启动/停止/状态接口
- **流管理**：集成 streams.py 的完整流管理功能（CRUD + start/stop）
- **任务管理**：集成 tasks.py 的任务管理功能，增强告警配置支持
- **告警管理**：集成 alarms.py 的基础告警查询和处理功能
- **输出管理**：保留原有的输出管理功能

**新增接口：**

- `PUT /analyzer/tasks/{task_id}/alarm_config` - 更新任务告警配置
- `GET /analyzer/alarms/{alarm_id}/media` - 获取告警媒体文件信息

**接口整合：**

```
/analyzer/start                    # 系统控制
/analyzer/stop
/analyzer/status

/analyzer/streams                  # 流管理（集成自streams.py）
/analyzer/streams/{id}
/analyzer/streams/{id}/start
/analyzer/streams/{id}/stop

/analyzer/tasks                    # 任务管理（集成自tasks.py）
/analyzer/tasks/{id}
/analyzer/tasks/{id}/alarm_config

/analyzer/alarms                   # 告警管理（集成自alarms.py基础功能）
/analyzer/alarms/{id}
/analyzer/alarms/{id}/process
/analyzer/alarms/{id}/media

/analyzer/outputs                  # 输出管理（原有功能）
```

#### 2. 创建 alarm_processor.py - 告警自动处理服务

**核心功能：**

- 处理 AI 检测结果，自动判断是否触发告警
- 自动保存告警媒体文件（前后 N 秒视频 + 检测图片）
- 发送实时 WebSocket 通知
- 告警冷却机制，避免频繁告警

**关键方法：**

- `process_detection_result()` - 处理检测结果主流程
- `_save_alarm_media()` - 自动保存媒体文件
- `_save_alarm_video()` - 保存告警前后 N 秒视频
- `_send_alarm_notification()` - 发送实时通知

#### 3. 优化 video_recorder.py - 支持告警视频自动保存

**新增方法：**

- `save_alarm_video_segment()` - 从循环缓冲区提取指定时间段视频
- `_merge_video_segments()` - 合并多个视频段

**功能增强：**

- 支持指定输出路径的视频保存
- 支持自定义前后 N 秒时长
- 自动创建告警目录结构

#### 4. 重构路由配置 (router.py)

**新的架构层次：**

**基础平台层：**

- `/auth/*` - 认证管理
- `/users/*` - 用户管理
- `/menu/*` - 菜单权限

**主要业务层：**

- `/analyzer/*` - AI 分析器统一业务接口

**独立专业层：**

- `/algorithms/*` - 算法包管理（独立功能）
- `/ws/*` - WebSocket 实时通信（独立功能）

#### 5. 清理废弃文件

**删除的文件：**

- `streams.py` - 功能已集成到 analyzer.py
- `tasks.py` - 功能已集成到 analyzer.py
- `alarms.py` - 功能已集成到 analyzer.py

#### 6. 自动化告警流程设计

**完整流程：**

```
1. 系统启动 → 添加监控流 → 创建分析任务（包含告警配置）
2. AI算法检测 → alarm_processor自动处理 → 判断告警条件
3. 满足条件 → 自动保存前后N秒视频 + 检测图片 → WebSocket通知
4. 前端查看 → 获取告警列表和详情 → 处理告警
```

**告警配置参数：**

```json
{
  "alarm_config": {
    "enabled": true,
    "conditions": ["person", "vehicle"],
    "confidence_threshold": 0.8,
    "pre_seconds": 5,
    "post_seconds": 5,
    "save_video": true,
    "save_images": true,
    "cooldown_seconds": 30
  }
}
```

#### 7. 架构优势

- **统一入口**：analyzer.py 成为 AI 分析业务的唯一入口
- **自动化程度高**：告警检测到保存媒体文件全自动
- **配置灵活**：告警前后秒数、条件、阈值都可配置
- **职责清晰**：业务接口 vs 专业模块 vs 平台功能分层明确
- **向后兼容**：保留所有核心功能，不破坏现有业务

**影响范围：**

- analyzer.py - 重大重构，成为主要业务接口
- router.py - 路由架构调整
- 新增 alarm_processor.py
- 优化 video_recorder.py
- 删除 streams.py、tasks.py、alarms.py

**前端调用变化：**

```javascript
// 重构前：分散调用
await api.post("/streams/add", streamData);
await api.post("/tasks", taskData);
await api.get("/alarms/list");

// 重构后：统一调用
await api.post("/analyzer/streams", streamData);
await api.post("/analyzer/tasks", taskData);
await api.get("/analyzer/alarms");
```

**向前兼容性：** 功能完全兼容，接口路径有变化但功能增强

---

## 历史记录

### 2024-12-19 - 分层 API 架构实现（已废弃）

**思考过程：** 最初考虑分层架构（业务层+技术层），但发现过于复杂，不符合项目现状...

### 2025-07-14 - 早期接口问题修复

**修复内容：** auth.py 登录接口、users.py 响应格式、menu.py 权限问题等...
