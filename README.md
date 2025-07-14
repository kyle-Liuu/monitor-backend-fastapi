# AI 智能监控系统后端 API

基于 FastAPI 实现的 AI 智能监控系统后端 API。本项目提供视频监控、行为分析和报警管理等功能的后端服务。

## 技术栈

- **框架**：FastAPI
- **数据库**：SQLite3
- **通信**：HTTP RESTful API + WebSocket
- **认证**：JWT (JSON Web Token)，双令牌机制
- **文档**：Swagger/OpenAPI
- **ID 生成**：自定义唯一 ID (如 user_id, menu_id)
- **日志系统**：集成多级日志记录和轮转功能

## 功能特点

- **用户认证与权限管理**：支持超级管理员、管理员和普通用户三种角色
- **双令牌认证机制**：访问令牌(8 天)和刷新令牌(30 天)分离，提高安全性
- **动态菜单配置**：根据用户角色权限动态生成前端菜单
- **视频监控管理**：提供视频流信息管理、虚拟绑定和组织架构
- **算法管理**：支持 YOLO11 等 AI 算法配置和管理
- **数据仓库**：支持人脸库和开放库资源管理
- **日志记录**：API 访问日志、用户操作日志、数据库操作日志和应用日志

## 快速开始

### 使用批处理脚本（Windows）

项目提供了便捷的批处理脚本 `start.bat`，可以选择启动服务或重置数据库：

#### 方法一：双击启动

1. 在文件资源管理器中导航到 `backend` 目录
2. 双击 `start.bat` 文件运行脚本

#### 方法二：命令行启动

```bash
# 进入后端目录
cd backend

# 运行批处理脚本
start.bat

# 或者使用完整路径运行
D:\path\to\backend\start.bat
```

#### 脚本选项说明

脚本启动后会提供以下选项：

1. **启动服务**：直接启动后端 API 服务，保留现有数据库
2. **重置数据库并启动服务**：删除现有数据库，创建新数据库并初始化默认数据，然后启动服务
3. **退出**：关闭脚本不执行任何操作

选择选项 2 重置数据库时，脚本会进一步要求确认操作，以防止意外删除数据。

#### 故障排除

如果启动脚本时出现错误，请检查：

- 确保您位于正确的目录下（backend 目录）
- 确保已安装 Python 及所有依赖包（见下方手动安装说明）
- 检查数据库文件是否可访问（非只读模式）
- 检查端口 8000 是否被占用

### 手动安装与运行

1. 安装依赖：

```bash
cd backend
pip install -r requirements.txt
```

2. 重置数据库（可选）：

```bash
python reset_db.py
```

3. 运行服务：

```bash
python run.py
```

或者使用 uvicorn 直接启动：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 默认用户

系统初始化后会创建以下默认用户：

- **超级管理员**：用户名 `super`，密码 `123456`
- **管理员**：用户名 `admin`，密码 `123456`
- **普通用户**：用户名 `user`，密码 `123456`

## JWT 认证机制

系统采用双令牌机制进行认证：

- **访问令牌(token)**：用于 API 请求验证，有效期 8 天
- **刷新令牌(refreshToken)**：用于获取新的访问令牌，有效期 30 天
- **令牌黑名单**：支持令牌撤销，用户登出时令牌会被加入黑名单
- **定期清理**：系统会自动清理过期的黑名单令牌

### 认证接口

- `POST /api/auth/login`：用户登录，获取令牌对
- `POST /api/auth/refresh`：使用刷新令牌获取新的令牌对
- `POST /api/auth/logout`：用户登出，使当前令牌失效

## 日志系统

系统集成了完善的日志记录功能，所有日志文件保存在 `logs` 目录下：

- **app.log**：应用主日志，记录系统启动、关闭和主要操作
- **access.log**：API 访问日志，记录所有请求、响应状态码和处理时间
- **user.log**：用户操作日志，记录用户登录、权限验证等操作
- **db.log**：数据库操作日志，记录数据库连接、查询和事务

日志特性：

- 支持按大小轮转和按时间轮转
- 自动创建日志目录
- 多级日志等级（debug、info、warning、error、critical）
- 日志包含时间戳、代码位置和详细信息

查看日志示例：

```
2023-06-25 12:30:45 - INFO - app - main.py:20 - 应用启动，开始初始化数据库...
2023-06-25 12:30:46 - INFO - db - database.py:50 - 数据库表创建完成
2023-06-25 12:30:47 - INFO - user - auth.py:45 - 用户登录成功: admin - 角色: R_ADMIN - 来自: 127.0.0.1
2023-06-25 12:31:25 - INFO - access - [127.0.0.1] - GET /api/menu/list - 200
```

## API 接口

### 认证接口

- `POST /api/auth/login`: 用户登录

  - 请求参数：`{ "userName": "xxx", "password": "xxx" }`
  - 响应：包含 token、refreshToken、用户信息和权限

- `POST /api/auth/refresh`: 刷新令牌

  - 请求参数：`{ "refresh_token": "xxx" }`
  - 响应：包含新的 token 和 refreshToken

- `POST /api/auth/logout`: 用户登出
  - 请求头：需要包含有效的 Authorization Bearer Token
  - 响应：登出成功消息

### 用户接口

- `GET /api/user/info`: 获取当前用户信息

  - 响应：用户 ID、用户名、角色、按钮权限等

- `GET /api/user/list`: 获取用户列表（需管理员权限）
  - 请求参数：`current`, `size`, `keyword`（可选）
  - 响应：分页的用户列表

### 菜单接口

- `GET /api/menu/list`: 获取菜单列表
  - 响应：根据用户权限的菜单树结构

## 项目结构

```
backend/
├── app/                    # 主应用目录
│   ├── api/                # API接口
│   │   └── endpoints/      # API端点实现
│   ├── core/               # 核心配置
│   ├── db/                 # 数据库模型和连接
│   ├── schemas/            # Pydantic模型
│   └── utils/              # 工具函数
│       ├── logger.py       # 日志工具模块
│       └── token_cleanup.py # 令牌清理模块
├── logs/                   # 日志文件目录
├── requirements.txt        # 依赖包列表
├── reset_db.py             # 数据库重置脚本
├── run.py                  # 运行脚本
└── start.bat               # 启动批处理脚本
```

## API 文档

启动服务后，访问以下 URL 查看 API 文档：

- **Swagger 文档**：http://127.0.0.1:8000/docs
- **ReDoc 文档**：http://127.0.0.1:8000/redoc

## 开发说明

- 唯一 ID 生成：系统使用格式为"前缀+随机字符串"的方式生成唯一 ID，如`user_id`和`menu_id`
- 角色权限：使用`R_SUPER`、`R_ADMIN`和`R_USER`三种角色
- 数据库：使用 SQLite3 作为轻量级数据库，生产环境可考虑切换到 PostgreSQL 等
- 日志级别：开发环境可设置为 debug 级别，生产环境建议设置为 info 或 warning 级别
