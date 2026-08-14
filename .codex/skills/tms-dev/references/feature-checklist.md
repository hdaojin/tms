# TMS Feature Checklist

这是一份 `$tms-dev` 的实施/review 检查表。项目规则不要复制到这里；具体约束始终以根目录 `AGENTS.md` 为准。

## 1. 需求与领域

- [ ] 已明确使用者、入口、成功结果和失败行为。
- [ ] 已确认涉及哪些 APP、模型和外部数据源。
- [ ] 涉及领域术语/统计口径时已阅读 `CONTEXT.md` 和相关 ADR。
- [ ] 没有重新引入旧 APP、旧菜单体系或已经废弃的业务概念。

## 2. 现有链路探索

- [ ] 已沿 `urls -> view -> form/table -> service/selector -> model -> template -> navigation -> tests` 追过现有实现。
- [ ] 已检查 `core` 是否有可复用 mixin、table、form field、upload、permission 或 component。
- [ ] 已阅读相关 migration/tests，确认兼容约束。

## 3. 数据模型与一致性

- [ ] 能用数据库表达的唯一性/完整性已优先使用 constraint。
- [ ] 并发下必须成立的规则没有只靠 `.exists()` 预检查。
- [ ] Model 只保留实体自身不变量，没有把跨模型工作流塞入 `save()`。
- [ ] 非 ModelForm 的写入入口需要完整模型校验时，已有显式校验策略。
- [ ] GenericForeignKey 的目标类型和业务归属有明确校验。
- [ ] Schema 变化已生成、检查 migration，并考虑已有数据升级路径。

## 4. Service / Import / Transaction

- [ ] 跨模型写操作已放到清晰的 service 入口。
- [ ] 需要原子性的写流程使用 `transaction.atomic()`，事务范围不过度扩大。
- [ ] 导入采用解析/校验/确认等明确阶段，而不是 parser 直接零散落库。
- [ ] 原始文件/快照/校验报告按业务需要留存。
- [ ] 重复提交或重复导入的幂等行为已定义。
- [ ] 已有正式下游数据时的覆盖/拒绝策略已定义。
- [ ] 失败路径有测试证明不会留下半成品数据。

## 5. Query / Selector / Performance

- [ ] 可复用复杂查询或统计口径已集中到 selector/manager，而不是散落多个 view。
- [ ] 列表页检查了 `select_related()` / `prefetch_related()`。
- [ ] django-tables2 accessor/renderer 不会逐行触发额外查询。
- [ ] 树形/递归逻辑没有在每个节点上重新查询 children。
- [ ] 大数据汇总没有不必要的重复扫描。
- [ ] 大文件普通更新不会无条件重复读取、解析或计算哈希。

## 6. 权限

- [ ] 登录要求正确；真正公开的 view 才使用 `login_not_required`。
- [ ] 查看、新增、修改、删除、审核分别有正确后端权限。
- [ ] 直接访问 URL 不能绕过模板按钮隐藏。
- [ ] 对象级 owner/跨组访问规则有测试。
- [ ] 需要业务授权组合时已复用/更新 permission bundle。
- [ ] 业务授权只检查 Django Permission，未依赖 Group 名称/codename；对象范围由 selector/policy 收窄。

## 7. 文件与归档

- [ ] 上传扩展名、大小、storage 复用 `core.uploads` / `core.constants`。
- [ ] 敏感文件使用 private storage，不直接暴露目录。
- [ ] 主领域原始试题、评分表、结果包、训练资料等按需登记 `ArchiveAsset`。
- [ ] 文件替换/删除清理机制存在并有测试。
- [ ] 文件名、URL、MIME/图片展示等输入没有引入明显安全风险。

## 8. URL / Navigation / UI

- [ ] APP URL 使用 namespace，并在 `tmsproject/urls.py` 正确 include。
- [ ] 导航只修改 `core/config/navigation.yml`。
- [ ] 新页面使用正确 `templates/layouts/*`，优先复用 common/components。
- [ ] CBV/表单/table 复用当前项目已有基础类。
- [ ] 页面文案、表单错误和帮助文本使用中文。

## 9. HTMX / Tailwind / DaisyUI / Alpine / Iconify

- [ ] HTMX full-page 与 fragment 共享相同业务逻辑。
- [ ] 使用 `request.htmx` 判断请求；缓存差异响应时处理 `Vary: HX-Request`。
- [ ] CSRF 与权限在 HTMX 请求中同样有效。
- [ ] Tailwind/Iconify class 是完整静态字符串，没有模板动态拼接。
- [ ] DaisyUI 组件与现有主题保持一致。
- [ ] Alpine 写法兼容 CSP build；没有新增原始 inline script、`onclick=` 或 `javascript:` URL。
- [ ] 新增样式/icon class 后执行了 `npm run build:css`。

## 10. Tests / Docs / Delivery

- [ ] 核心成功路径有测试。
- [ ] 关键失败、权限和边界条件有测试。
- [ ] 运行了受影响范围的 `uv run pytest ...`。
- [ ] 运行了受影响路径 Ruff 和 `uv run manage.py check`。
- [ ] 模型变化运行了 `uv run manage.py makemigrations --check --dry-run`。
- [ ] 跨 APP/core/权限/统计口径变化最终运行了全量 `uv run pytest`。
- [ ] UI class 变化运行了 `npm run build:css`。
- [ ] 用户可见行为已更新 `docs/user-manual/`。
- [ ] 领域语义变化已更新 `CONTEXT.md`；长期架构决策已更新 ADR。
- [ ] diff 中没有无关重构、密钥、临时文件或本地环境产物。
