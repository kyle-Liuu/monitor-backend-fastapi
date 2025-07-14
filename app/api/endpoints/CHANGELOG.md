# API 端点变更日志

## 2025-07-14

### 修复

- **auth.py**: 修复登录接口参数问题

  - 思考过程：登录接口支持两种登录方式（OAuth2 表单和 JSON 请求体），但 login_data 参数没有正确设置为可选参数，导致在仅使用表单方式登录时出现验证错误。
  - 修改内容：将 login_data 参数从`login_data: LoginParams = None`修改为`login_data: LoginParams = Body(None)`，确保参数正确解析并且允许为空。

- **auth.py**: 修改 JSON 登录接口响应格式

  - 思考过程：前端登录后报错"Login failed - no token received"，经分析发现是后端返回的响应格式与前端期望的不一致。前端期望 token 和 refreshToken 在 data 对象内，但后端将它们放在了顶层。
  - 修改内容：调整 JSON 登录接口的响应格式为符合前端期望的格式，将 token 和 refreshToken 放入 data 对象中。

- **users.py**: 统一用户相关 API 响应格式

  - 思考过程：API 响应格式需要统一为`{code, data, msg}`结构，但用户信息和用户列表接口的响应不符合这个格式。
  - 修改内容：
    1. 将`get_user_info`接口响应格式调整为统一格式
    2. 将`get_user_list`接口响应格式调整为统一格式
    3. 移除不必要的 response_model 限制，避免 Pydantic 验证错误

- **auth.py**: 修复表单登录接口响应格式

  - 思考过程：将登录接口分为两个后，表单登录接口（/login/OAuth2）响应格式不符合 OAuth2 标准，导致 Swagger UI 无法正确处理登录。
  - 修改内容：简化表单登录接口返回格式，仅保留 OAuth2 标准要求的字段：access_token、token_type 和 refresh_token，移除了额外字段。

- **menu.py**: 修复菜单接口响应格式

  - 思考过程：前端报错"Cannot read properties of undefined (reading 'menuList')"，原因是菜单接口返回的 message 字段与前端期望的 msg 字段不一致。
  - 修改内容：
    1. 修改 MenuResponse 模型，将 message 字段改为 msg
    2. 修改菜单接口响应中的字段名，保持与其他接口一致
    3. 调整前端 menuApi.ts 中响应类型定义，将 message 改为 msg

- **utils.py**: 修复 Swagger UI 认证问题

  - 思考过程：Swagger UI 认证失败（Unprocessable Entity 错误），是因为将登录接口分拆后，OAuth2 的 tokenUrl 指向的路径已经不正确。
  - 修改内容：将 OAuth2PasswordBearer 的 tokenUrl 从 "/api/auth/login" 更新为 "/api/auth/login/OAuth2"，使其与表单登录接口路径一致。

- **menu.py**: 修复普通用户菜单权限问题
  - 思考过程：普通用户登录时出现"local variable 'parent' referenced before assignment"错误，分析发现在构建菜单树时，代码尝试访问可能未初始化的 parent 变量。
  - 修改内容：
    1. 修改菜单树构建逻辑，先获取 parent 变量，再判断是否存在
    2. 增加对找不到父菜单情况的处理逻辑，添加详细警告日志
    3. 保持菜单权限规则：菜单 roles 为空的所有用户可访问，不为空的只有角色匹配才能访问

### 优化

- **auth.py**: 将登录接口分为两个独立的端点
  - 思考过程：在单个登录接口同时支持表单和 JSON 请求体的情况下，FastAPI 的 Swagger UI 只显示表单选项，没有 JSON 选项。这是因为 OAuth2PasswordRequestForm 依赖项会覆盖 JSON 请求体的解析。
  - 修改内容：
    1. 创建`/login/OAuth2`端点专门处理表单登录（供 Swagger UI 使用）
    2. 保留`/login`端点专门处理 JSON 登录（供前端应用使用）
    3. 两个端点分别记录不同的日志信息，便于问题排查
