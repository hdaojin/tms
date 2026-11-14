# TMS 管理员辅助密码重置功能实施计划

> **文档类型**：Codex 可执行实施 Plan\
> **目标项目**：`hdaojin/tms`\
> **目标分支**：`develop`\
> **技术基线**：Django 6、Python 3.13、django-htmx、Tailwind CSS
> 4、DaisyUI 5、Alpine.js CSP、Iconify\
> **方案版本**：1.0\
> **日期**：2026-11-14

------------------------------------------------------------------------

## 1. 实施目标

在现有 TMS `accounts` APP
中增加安全、轻量的密码管理与管理员辅助密码重置功能。

TMS 当前不能使用学校内部 SMTP，也不计划在本阶段接入
SMTP、短信或第三方身份认证服务。用户忘记密码时，由管理员通过线下或其他可信沟通方式核实用户身份，然后在
TMS
中为指定用户签发一个短时、一次性密码重置链接，并通过一对一私密渠道发送给用户。用户打开链接后自行设置新密码。

本功能还应提供登录用户主动修改自己密码的入口。

### 1.1 最终用户流程

**用户主动修改密码**

1.  用户登录 TMS。
2.  从个人资料/账号入口进入修改密码页面。
3.  输入当前密码、新密码及确认密码。
4.  服务端使用 Django 原生密码验证机制完成修改。
5.  当前会话保持有效，其他既有会话按 Django 原生认证哈希机制失效。

**忘记密码，由管理员辅助恢复**

1.  用户联系管理员申请重置密码。
2.  管理员通过当面沟通等线下方式核实用户身份。
3.  管理员在该用户详情页点击"生成密码重置链接"。
4.  管理员确认已核实身份，提交签发操作。
5.  系统生成 256 bit 随机令牌，令牌有效期 30 分钟。
6.  系统只在本次响应中向管理员展示一次完整链接；数据库只保存令牌摘要。
7.  管理员通过微信等一对一私密渠道将链接发送给用户。
8.  用户打开链接，设置并确认新密码。
9.  服务端原子地消费令牌、更新密码并撤销该用户其他未使用的重置授权。
10. 用户使用新密码重新登录。

### 1.2 明确不做的内容

-   不接入 SMTP、邮件、短信或第三方消息服务。
-   不实现邮箱验证。
-   不实现用户备用恢复码、TOTP、MFA 或安全问题。
-   不提供匿名用户自行申请重置链接的入口。
-   不允许管理员查看、设置或接收用户的新密码。
-   不新增独立 APP。
-   不修改 Django 默认 `auth.User` 用户模型。
-   不修改现有角色、业务权限包或权限投影体系。
-   不引入第三方密码重置依赖。
-   不顺手重构与本功能无关的账号管理代码。

------------------------------------------------------------------------

## 2. 开始实施前必须审阅的项目代码

Codex 执行时必须先读取目标分支最新代码和项目规范，不得仅依赖本 Plan
中的文件路径或历史代码片段。

至少审阅：

-   `AGENTS.md`
-   `accounts/models.py`
-   `accounts/forms.py`
-   `accounts/views.py`
-   `accounts/urls.py`
-   `accounts/services/profiles.py`
-   `accounts/templates/accounts/login.html`
-   `accounts/templates/accounts/login_form.html`
-   `accounts/templates/accounts/profile.html`
-   `accounts/templates/accounts/user_detail.html`
-   `accounts/templates/accounts/partials/user_info_card.html`
-   `core/utils/decorators.py`
-   `tmsproject/urls.py`
-   `tmsproject/settings.py`
-   现有 `accounts` 测试文件
-   `templates/layouts/app.html`
-   `templates/layouts/auth.html`
-   `templates/components/` 中的表单、字段、按钮和提示组件
-   `docs/developer/ui.md`
-   `docs/user-manual/` 中与登录、个人资料、账号管理有关的文档

重点确认：

1.  项目继续使用 Django 默认 `auth.User`。
2.  全局启用了
    `LoginRequiredMiddleware`，公开重置页面必须显式允许匿名访问。
3.  当前用户详情页的账号管理操作仅向有效超级管理员展示，后端也必须进行相同级别的权限校验。
4.  现有 `superuser_required` 装饰器的行为和使用方式。
5.  项目当前使用的模板布局、表单组件、消息提示、图标和复制文本交互方式。
6.  项目生产环境的 HTTPS 反向代理配置，确认 `request.is_secure()` 在
    Caddy 代理后能够正确识别 HTTPS。
7.  项目测试组织方式和现有认证测试工具。

如实际代码结构与上述路径不同，以目标分支当前代码为准，选择最小、符合现有架构的接入点。

------------------------------------------------------------------------

## 3. 方案与安全边界

### 3.1 管理员权限

-   仅有效超级管理员可以签发重置链接。
-   必须在服务端校验 `request.user.is_active` 和
    `request.user.is_superuser`。
-   不得把 `accounts.view_all_profiles`、普通 Django Permission
    或模板中隐藏按钮作为签发权限。
-   用户详情页可以显示操作入口，但后端必须独立校验权限。
-   签发操作必须是 POST 请求，并启用 CSRF 保护。
-   不允许通过 GET 请求签发、撤销或消费重置授权。

### 3.2 身份核验确认

管理员签发页面必须要求勾选确认项：

> 我已通过当面沟通或其他可信方式核实该用户身份，确认本次密码重置申请属于该用户本人。

未勾选不得提交。

可提供一个简短的"核验备注"字段，非必填，长度不超过 200
字。不要收集身份证号、证件照片等不必要的敏感信息。

系统记录签发管理员、目标用户、签发时间和核验备注。系统本身不声称能够验证线下身份，身份核验责任属于签发管理员。

### 3.3 重置链接规则

  项目                 规则
  -------------------- ----------------------------------------------------
  随机令牌             `secrets.token_urlsafe(32)`，提供 256 bit 随机熵
  公开标识             使用 UUID 作为授权记录 ID
  有效期               30 分钟
  使用次数             成功设置密码后一次性失效
  同一用户未使用链接   同一时间最多保留一个有效授权
  再次签发             自动撤销该用户此前所有未使用授权，再创建新授权
  目标账号             只能重置授权记录绑定的用户
  账号状态             签发和最终消费时均要求目标用户 `is_active=True`
  管理员交付           由管理员通过一对一私密渠道发送
  失败处理             无效、过期、已使用、已撤销的链接统一显示不可用提示

链接属于 Bearer
Credential：任何获得完整链接的人都可能重置对应账号密码。因此必须通过一对一私密渠道发送，不得在群聊或公开渠道发送。管理员发送错误时，可重新签发；重新签发会使旧链接失效。

### 3.4 令牌不得出现在服务端 URL 日志

不要把原始令牌放在 URL path 或 query string 中。

采用 URL fragment 传递令牌：

``` text
https://tms.example.internal/accounts/password-reset/<grant-uuid>/#<raw-token>
```

浏览器访问时，fragment 不会被发送到服务器，因此不会进入 Django
请求路径、Caddy access log 或 HTTP Referer。

重置页面加载后，由一个外置静态 JavaScript 文件：

1.  从 `window.location.hash` 读取令牌。
2.  将令牌写入表单隐藏字段。
3.  使用 `history.replaceState()` 清除地址栏中的 fragment。
4.  用户提交表单时，通过 POST body 将令牌发送给 Django。
5.  不使用 query string 传递令牌。
6.  不将令牌写入 localStorage、sessionStorage、Cookie 或服务器 session。

如果项目当前 CSP 不允许某种脚本加载方式，应遵循现有 CSP 规则，将逻辑放在
`static/js/` 外置脚本中，不要为了该功能放宽全站 CSP。

### 3.5 HTTPS

-   生产环境必须通过 HTTPS 访问签发和重置页面。
-   签发视图在 `DEBUG=False` 且 `request.is_secure()` 为 False
    时必须拒绝签发，不能生成 HTTP 重置链接。
-   检查 Caddy 反向代理是否正确传递 `X-Forwarded-Proto`。
-   仅在可信反向代理会覆盖客户端传入的转发头时，才启用现有
    `TRUST_X_FORWARDED_PROTO` 配置。
-   通过 `request.build_absolute_uri()` 构建链接前，确保 Host 已经由
    Django `ALLOWED_HOSTS` 校验；不得直接信任用户提交的 host、Referer
    或任意 `next` 参数。
-   不为本功能引入新的公开域名或外部服务。

### 3.6 响应安全头

签发结果页和匿名重置页面均设置：

-   `Cache-Control: no-store`
-   `Pragma: no-cache`
-   `Referrer-Policy: no-referrer`
-   `X-Robots-Tag: noindex, nofollow`

可以复用 Django `never_cache` 等现有机制，并在必要时补充响应头。

重置页面不得加载外部统计脚本、外部图片、第三方字体或其他非必要第三方资源。

------------------------------------------------------------------------

## 4. 数据模型

在现有 `accounts/models.py` 中新增 `PasswordResetGrant`。不新增 APP。

建议字段：

  ------------------------------------------------------------------------------------------------------
  字段                    类型                                    说明
  ----------------------- --------------------------------------- --------------------------------------
  `id`                    UUIDField，主键                         对外公开的随机授权 ID

  `user`                  FK 到 `settings.AUTH_USER_MODEL`        被重置密码的目标用户

  `token_digest`          CharField(max_length=64)，唯一          原始令牌的 SHA-256 十六进制摘要

  `issued_by`             FK 到 `settings.AUTH_USER_MODEL`，可空  签发管理员；删除管理员后保留授权记录

  `created_at`            DateTimeField                           签发时间

  `expires_at`            DateTimeField                           过期时间

  `used_at`               DateTimeField，可空                     成功消费时间

  `revoked_at`            DateTimeField，可空                     撤销时间

  `reason`                CharField(max_length=200)，blank=True   管理员核验备注
  ------------------------------------------------------------------------------------------------------

实现要求：

1.  `id` 使用 `uuid.uuid4`。
2.  `user`
    删除时按项目现有账号数据策略处理；优先避免产生无法解释的孤立授权记录。
3.  `issued_by` 使用 `SET_NULL`，保留记录本身。
4.  为用户与创建时间建立适当索引，避免用户详情页查询授权历史时产生全表扫描。
5.  不额外增加冗余的 `status` 字段；状态根据
    `used_at`、`revoked_at`、`expires_at` 和目标用户状态计算。
6.  可以增加 `CheckConstraint`，确保 `expires_at > created_at`。
7.  不保存原始令牌、完整重置链接或新密码。
8.  不把原始令牌放入模型 `__str__`、日志、异常信息或 Django Admin 展示。

有效授权判断：

``` text
used_at IS NULL
AND revoked_at IS NULL
AND expires_at > now
AND user.is_active = True
```

过期状态由时间判断，不要求定时任务清理。保留授权记录用于审计；本次不实现自动清理任务。

### 4.1 令牌摘要

生成：

``` python
raw_token = secrets.token_urlsafe(32)
token_digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
```

校验时：

``` python
candidate_digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
is_valid = hmac.compare_digest(grant.token_digest, candidate_digest)
```

令牌具有 256 bit 随机熵，因此 SHA-256
摘要适合本场景；不要把普通用户密码的低熵哈希方案直接套用于该随机令牌。

------------------------------------------------------------------------

## 5. 服务层设计

新增：

``` text
accounts/services/password_reset.py
```

服务层集中实现签发、消费和撤销规则，视图不得自行拼接数据库写入流程。

建议提供以下服务函数，具体命名可根据项目现有 service 风格调整：

### 5.1 `issue_password_reset_grant(...)`

输入：

-   `actor`：当前管理员。
-   `target_user_id`：目标用户 ID。
-   `reason`：可选核验备注。

输出：

-   新建的 `PasswordResetGrant`。
-   本次生成的原始令牌。

规则：

1.  在服务层再次验证 actor 为有效超级管理员。
2.  使用事务锁定目标用户行（`select_for_update()`），串行化同一用户的并发签发操作。
3.  检查目标用户存在且处于激活状态。
4.  撤销该用户所有尚未使用、尚未撤销的历史授权，包括已过期但尚未标记撤销的授权。
5.  生成新的随机令牌。
6.  仅保存摘要，创建有效期 30 分钟的授权记录。
7.  返回原始令牌一次，供视图构建链接并展示。
8.  不记录原始令牌或完整链接。

不要在模型 `save()` 中隐式生成或返回原始令牌。

### 5.2 `consume_password_reset_grant(...)`

输入：

-   `grant_id`
-   `raw_token`
-   新密码表单数据

规则：

1.  使用 `transaction.atomic()`。
2.  使用 `select_for_update()` 锁定授权记录。
3.  再次检查授权存在、未使用、未撤销、未过期。
4.  锁定目标用户，并再次检查 `is_active=True`。
5.  通过 SHA-256 摘要和 `hmac.compare_digest()` 验证令牌。
6.  使用 Django `SetPasswordForm(user=locked_user, data=...)`
    验证新密码。
7.  如果新密码验证失败，不得消费令牌；允许用户在有效期内重新提交。
8.  密码验证成功后，通过 `SetPasswordForm.save()` 保存密码。
9.  在同一事务中设置当前授权 `used_at`。
10. 在同一事务中撤销该用户其余未使用授权。
11. 事务成功提交后才向视图返回成功。

并发安全是本功能的核心：同一个授权被两个请求同时提交时，只允许一个请求成功。第二个请求取得数据库锁后必须重新检查
`used_at`，并被拒绝。

不要只在事务外先检查 `used_at`，然后在事务内直接保存密码。

### 5.3 失败尝试

-   不因一次无效 token 请求而改变授权状态。
-   不允许通过提交错误 token
    将合法授权主动撤销，避免简单的拒绝服务攻击。
-   不向日志写入 token 或密码。
-   可以复用项目已有的共享限流设施；若当前只有进程内缓存，不得宣称其能跨
    Gunicorn worker 限流。
-   256 bit 随机令牌已经使暴力猜测不可行，不为此引入
    Redis、第三方限流包或复杂失败计数模型。

------------------------------------------------------------------------

## 6. 表单设计

在 `accounts/forms.py` 中新增或定义：

### 6.1 `PasswordResetLinkIssueForm`

字段：

-   `identity_verified`：必选 BooleanField。
-   `reason`：可选 CharField，最多 200 字。

要求：

-   复用 `StyledFormMixin` 和项目表单样式。
-   未勾选身份核验确认时不得通过验证。
-   不接受用户 ID、签发人 ID、过期时间、授权状态等由客户端控制的字段。

### 6.2 密码修改表单

使用 Django 内置：

-   `PasswordChangeForm`：已登录用户主动修改密码。
-   `SetPasswordForm`：通过管理员签发链接重置密码。

不要重复实现密码一致性、密码强度和密码保存逻辑。

------------------------------------------------------------------------

## 7. URL 与视图

所有 URL 继续放在 `accounts/urls.py`，使用现有 `app_name = "accounts"`
namespace。

建议 URL：

  --------------------------------------------------------------------------------------------------------------------
  方法              URL                                               名称                           访问范围
  ----------------- ------------------------------------------------- ------------------------------ -----------------
  GET/POST          `/accounts/password-change/`                      `password_change`              登录用户

  GET               `/accounts/password-change/done/`                 `password_change_done`         登录用户

  POST              `/accounts/users/<int:pk>/password-reset-link/`   `admin_password_reset_issue`   有效超级管理员

  GET/POST          `/accounts/password-reset/<uuid:grant_id>/`       `password_reset_grant`         匿名可访问
  --------------------------------------------------------------------------------------------------------------------

### 7.1 主动修改密码

优先使用 Django `PasswordChangeView` 和 `PasswordChangeDoneView`：

-   使用 Django 原生 `PasswordChangeForm`。
-   使用项目自己的模板和布局。
-   成功后使用 Django 原生 `update_session_auth_hash()`
    行为，使当前用户不被自己主动修改密码的操作登出。
-   当前密码验证失败时不得修改密码。
-   用户资料是否锁定不影响修改密码。

### 7.2 管理员签发视图

新增独立视图，例如：

``` python
admin_password_reset_issue(request, pk)
```

要求：

-   仅 POST。
-   使用项目现有 `superuser_required` 装饰器或等价的明确后端检查。
-   获取目标用户时使用 `get_object_or_404()`。
-   表单必须验证 `identity_verified`。
-   调用 `issue_password_reset_grant()`。
-   检查 HTTPS 条件。
-   使用 `reverse()` 生成授权页面路径。
-   使用可信请求 origin 构建绝对 URL。
-   把原始 token 放在 URL fragment，而不是 path/query。
-   直接渲染一次性链接结果页面，不把 token 存入数据库、Django
    session、Cookie、消息系统或日志。
-   响应设置 `no-store` 和 `no-referrer`。

建议生成：

``` text
https://<trusted-tms-host>/accounts/password-reset/<grant-uuid>/#<raw-token>
```

不要把 token 作为 POST 响应后的重定向参数。

### 7.3 匿名重置视图

`password_reset_grant` 必须显式使用 Django 6 的
`login_not_required`，以通过项目的 `LoginRequiredMiddleware`。

GET：

1.  根据 UUID 查找授权。
2.  检查授权是否存在、未使用、未撤销、未过期，且用户仍然激活。
3.  有效时显示设置新密码页面。
4.  无效时显示统一的链接失效页面。
5.  不消费授权，不修改用户或授权记录。
6.  设置 `no-store`、`no-referrer` 等安全响应头。

POST：

1.  使用 CSRF 保护。
2.  从 POST body 读取隐藏字段 `token`。
3.  调用 `consume_password_reset_grant()`。
4.  成功时显示密码重置成功页面，并提示重新登录。
5.  密码不符合策略时，保留表单错误；只要授权仍有效，就允许重新提交。
6.  token
    无效、授权过期、已使用、已撤销或目标用户停用时，显示统一的不可用提示。
7.  不自动登录目标用户。
8.  不调用 `update_session_auth_hash()`。

GET 不能消费
token，以免微信等即时通讯软件的链接预览、浏览器预取或安全扫描访问链接时提前使链接失效。

------------------------------------------------------------------------

## 8. 前端页面与交互

遵循 TMS 现有视觉和组件规范：

-   使用 `layouts/app.html` 展示已登录用户的密码修改页面。
-   使用 `layouts/auth.html` 展示匿名密码重置页面。
-   优先复用 `templates/components/` 中的表单字段、按钮和提示组件。
-   使用 DaisyUI 5、Tailwind CSS 4 和现有 Iconify 图标。
-   不引入新的 CSS 框架或 UI 组件库。
-   页面保持简洁，避免增加不必要的步骤。

### 8.1 登录页面

在 `accounts/templates/accounts/login_form.html`
或合适的登录页面位置增加提示：

> 忘记密码？请联系系统管理员核实身份后获取一次性密码重置链接。

不要提供匿名输入用户名后直接生成链接的入口。

### 8.2 用户个人页面

在用户本人个人资料页增加"修改密码"入口，跳转到主动修改密码页面。

不要把修改密码入口放入他人资料查看页面。

### 8.3 管理员用户详情页面

在 `accounts/templates/accounts/user_detail.html`
现有超级管理员专属用户管理操作区域增加：

-   "生成密码重置链接"按钮。
-   点击后展示确认表单或 DaisyUI modal。
-   必须勾选"已核实用户身份"。
-   可填写核验备注。
-   提交后展示本次完整重置链接。
-   显示醒目但克制的安全提示：

> 此链接等同于临时密码凭据，仅能使用一次，有效期 30
> 分钟。请通过一对一私密渠道发送给用户，不要在群聊中分享。重新生成链接会使此前链接失效。

### 8.4 一次性链接展示页面

建议新增模板，例如：

``` text
accounts/templates/accounts/password_reset_link_issued.html
```

页面只在管理员签发成功的 POST 响应中展示完整链接：

-   提供只读文本框。
-   提供"复制链接"按钮。
-   复制成功后才显示成功反馈。
-   如果 Clipboard API 不可用或复制失败，允许手动选择文本复制。
-   不在用户详情页、普通消息或审计列表中再次显示原始链接。
-   页面设置 `Cache-Control: no-store`、`Referrer-Policy: no-referrer`。
-   不将原始链接写入 session 或 Django messages。

优先检查项目现有复制文本工具；没有合适工具时，新增小型外置脚本，不要引入依赖。

### 8.5 匿名重置页面的 fragment 处理

新增外置脚本，例如：

``` text
static/js/accounts/password-reset-grant.js
```

脚本只负责：

1.  从 URL fragment 读取 token。
2.  检查 token 非空。
3.  写入隐藏表单字段。
4.  使用 `history.replaceState()` 清除 fragment。
5.  token 缺失时显示提示并禁用提交。

脚本不得把 token 写入 localStorage、sessionStorage 或 Cookie。

如果密码校验失败，服务端可将本次 POST 中的 token
重新放入隐藏字段，以便用户在本页修正密码后重试；响应必须禁止缓存。不要在页面可见文本中显示
token。

------------------------------------------------------------------------

## 9. 模板与文件清单建议

根据实际项目结构调整，避免机械创建重复模板。

可能涉及：

``` text
accounts/
├── models.py
├── forms.py
├── views.py
├── urls.py
├── services/
│   └── password_reset.py
├── templates/
│   └── accounts/
│       ├── login_form.html
│       ├── profile.html
│       ├── user_detail.html
│       ├── password_change_form.html
│       ├── password_change_done.html
│       ├── password_reset_link_issued.html
│       ├── password_reset_grant_form.html
│       └── password_reset_grant_done.html
├── migrations/
└── tests/
    └── ...
static/
└── js/
    └── accounts/
        └── password-reset-grant.js
```

测试文件优先沿用当前 `accounts` APP
的测试组织方式；不要为了形式统一而搬迁大量既有测试。

------------------------------------------------------------------------

## 10. 测试要求

必须增加自动化测试，至少覆盖以下场景。

### 10.1 权限测试

-   普通用户不能签发重置链接。
-   只有查看他人资料权限、但不是超级管理员的用户不能签发。
-   未登录用户不能签发。
-   普通用户不能通过直接 POST URL 绕过前端隐藏。
-   已停用管理员不能签发。
-   目标用户不存在时返回 404。
-   已停用目标用户不能获得重置链接。
-   匿名用户可以访问重置页面，不被 `LoginRequiredMiddleware` 重定向。

### 10.2 签发测试

-   正确勾选身份核验后成功签发。
-   未勾选身份核验时拒绝签发。
-   原始 token 只在签发响应中出现。
-   数据库中只保存摘要，不保存原始 token。
-   授权有效期为 30 分钟。
-   同一用户重新签发后，旧授权立即撤销。
-   不同用户的授权互不影响。
-   签发记录保存管理员、目标用户、时间和备注。
-   `DEBUG=False` 且请求不是 HTTPS 时拒绝签发。
-   不能使用用户提交的任意 Host 构造重置链接。

### 10.3 链接与 GET 测试

-   正确 UUID 对应的有效授权显示重置页面。
-   无效 UUID、过期、已使用、已撤销及用户停用时显示不可用页面。
-   GET 不得修改 `used_at`、`revoked_at` 或用户密码。
-   多次 GET 不消耗授权，模拟微信预览访问。
-   token 位于 URL fragment，不在 path 或 query 中。
-   响应包含 `Cache-Control: no-store` 和
    `Referrer-Policy: no-referrer`。

### 10.4 重置成功测试

-   正确 token + 合规新密码能够成功重置。
-   新密码通过现有 `AUTH_PASSWORD_VALIDATORS`。
-   成功后 `used_at` 被写入。
-   成功后同一用户其他未使用授权全部撤销。
-   成功后用户使用新密码可以登录。
-   成功后旧密码不能登录。
-   重置成功不自动登录用户。
-   重置成功后目标用户其他既有会话失效。
-   重置链接不能修改其他用户密码。

### 10.5 失败与边界测试

-   错误 token 不修改密码、不消费授权。
-   过期 token 不修改密码。
-   已使用 token 不能再次使用。
-   已撤销 token 不能使用。
-   用户在签发后被停用，链接不能继续重置密码。
-   密码确认不一致时不修改密码，授权仍可重试。
-   新密码不符合现有密码策略时不修改密码，授权仍可重试。
-   缺少 token 时拒绝提交。
-   GET 不消费 token。
-   不在日志和错误信息中泄露 token 或密码。

### 10.6 并发测试

使用适合当前数据库的测试方式验证：

-   同一授权同时提交两次，最多只有一个请求成功。
-   同一用户并发签发时，最终只有一个未撤销授权。
-   使用 `select_for_update()` 的测试应在支持行级锁的数据库（生产
    PostgreSQL）上验证；SQLite 的 `select_for_update()`
    不提供相同锁语义，不得仅凭 SQLite 测试宣称并发安全。

### 10.7 主动修改密码测试

-   正确旧密码可以修改。
-   错误旧密码不能修改。
-   不符合密码策略不能修改。
-   成功后当前用户会话仍然有效。
-   其他已登录会话失效。
-   个人资料锁定不影响密码修改。

------------------------------------------------------------------------

## 11. 文档与配置

### 11.1 不需要增加的配置

本功能不需要增加：

-   SMTP 配置。
-   邮箱地址或邮箱验证字段。
-   短信服务商密钥。
-   第三方身份认证配置。
-   Redis 或第三方限流依赖。

### 11.2 现有 HTTPS 配置检查

检查：

-   `tmsproject/settings.py` 中的 `TRUST_X_FORWARDED_PROTO`。
-   生产环境 `.env` 中的 HTTPS 配置。
-   Caddy 是否正确设置可信的 `X-Forwarded-Proto`。
-   `ALLOWED_HOSTS` 是否限制为实际使用的 TMS 域名。

不读取、打印或提交服务器 `.env` 中的任何密钥。

### 11.3 用户文档

在 `docs/user-manual/` 中查找现有账号或个人资料说明：

-   增加用户主动修改密码的操作说明。
-   增加忘记密码后联系管理员的说明。
-   说明管理员必须先核实用户身份。
-   说明重置链接 30 分钟有效、只能使用一次。
-   说明链接必须私密发送，不要转发给他人。

如果当前没有合适的账号使用文档，新增一份简短说明，不创建重复的文档目录体系。

------------------------------------------------------------------------

## 12. 验收标准

只有同时满足以下条件，功能才算完成：

-   [ ] 不依赖 SMTP、邮箱、短信或外部服务。
-   [ ] 不新增 APP，不替换 Django 默认 User。
-   [ ] 用户可以在登录后修改自己的密码。
-   [ ] 管理员只能在核实身份后签发重置链接。
-   [ ] 非超级管理员不能通过任何直接请求签发链接。
-   [ ] 重置链接随机性足够，30 分钟后失效。
-   [ ] 同一用户重新签发会使旧链接失效。
-   [ ] GET、预览和预取不会消耗链接。
-   [ ] 原始 token 不进入 URL path、query、数据库、session、Cookie
    和日志。
-   [ ] 用户只能重置链接所绑定的账号。
-   [ ] 成功重置后链接一次性失效。
-   [ ] 密码校验复用 Django 原生机制。
-   [ ] 成功重置后原有用户会话失效。
-   [ ] 用户不能通过重置链接自动登录。
-   [ ] 管理员签发、用户使用等信息可审计。
-   [ ] 相关测试通过。
-   [ ] 模板符合 TMS 现有视觉规范。
-   [ ] 生产环境只通过 HTTPS 签发链接。
-   [ ] 用户手册得到适当更新。

------------------------------------------------------------------------

## 13. 实施顺序

Codex 按以下顺序实施，每个阶段完成后检查结果：

1.  **代码审阅**：读取 `AGENTS.md` 和本 Plan 第 2
    节列出的文件，确认现有代码结构。
2.  **模型与迁移**：新增 `PasswordResetGrant`，生成并检查 migration。
3.  **服务层**：实现签发、撤销旧授权、校验和原子消费服务。
4.  **表单与视图**：实现主动修改密码、管理员签发、匿名重置。
5.  **URL**：在 `accounts/urls.py` 中注册路由，确认匿名路由允许
    `LoginRequiredMiddleware` 放行。
6.  **模板与脚本**：实现管理员操作、一次性链接展示、匿名重置页面和
    fragment 处理脚本。
7.  **安全响应**：补齐 HTTPS 检查、缓存控制、Referrer-Policy
    和错误处理。
8.  **自动化测试**：覆盖权限、令牌生命周期、并发、密码策略和会话失效。
9.  **文档**：更新用户手册。
10. **验证**：执行与本次改动范围匹配的测试和构建命令，并报告结果。

不要一次性改动无关 APP 或大范围重构账号体系。

------------------------------------------------------------------------

## 14. 验证命令

遵循仓库 `AGENTS.md` 的验证策略。至少执行：

``` bash
uv run pytest <本次新增或修改的 accounts 测试文件>
uv run ruff check accounts
uv run manage.py makemigrations --check --dry-run
uv run manage.py check
npm run build:css
```

如果新增外置 JavaScript
且项目已有对应前端测试，补充运行相关测试。不要为了本次功能机械执行无关的全量前端依赖安装或升级。

模型迁移发生变化时，检查迁移文件内容；不要在本地开发过程中擅自对生产数据库执行迁移。

如果并发测试使用
PostgreSQL，确保在与生产一致的数据库后端上运行相关测试。SQLite
测试结果不能代替 PostgreSQL 行锁验证。

------------------------------------------------------------------------

## 15. 交付要求

完成后向用户报告：

1.  实际修改的文件清单。
2.  数据模型及迁移说明。
3.  管理员签发链接和用户重置密码的实际操作流程。
4.  令牌存储、有效期、一次性消费和并发控制实现方式。
5.  HTTPS 与反向代理识别情况。
6.  测试命令及实际结果。
7.  尚未完成的事项或环境限制。

不要只报告"功能已完成"；必须明确说明测试是否真正执行、哪些测试通过、哪些测试因环境原因未执行。

------------------------------------------------------------------------

## 16. Django 官方文档参考

实施时以 Django 6.0 当前文档和项目实际依赖版本为准：

-   Authentication
    system：<https://docs.djangoproject.com/en/6.0/topics/auth/default/>
-   Password
    management：<https://docs.djangoproject.com/en/6.0/topics/auth/default/#changing-passwords>
-   Session invalidation on password
    change：<https://docs.djangoproject.com/en/6.0/topics/auth/default/#session-invalidation-on-password-change>
-   `login_not_required`
    与认证视图：<https://docs.djangoproject.com/en/6.0/topics/auth/default/#the-login-not-required-decorator>
-   Django
    security：<https://docs.djangoproject.com/en/6.0/topics/security/>
-   Django
    settings：<https://docs.djangoproject.com/en/6.0/ref/settings/>

如果 Django 6.0 对应章节路径或 API
在实际安装版本中有调整，优先以当前依赖版本的官方文档和源码为准。
