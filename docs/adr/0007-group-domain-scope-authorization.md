# ADR 0007：Group 技术领域范围授权

- 状态：已接受
- 日期：2026-08-23

## 背景

原有 TechnicalDomainMembership 把领域职责直接绑定到 User，角色型 Permission Bundle 又跨多个 APP 聚合“技术教练”“项目管理员”能力。若分别汇总用户全部 Group 的 Permission 与全部领域范围，还会把不同 Group 的授权串联成未明确授予的能力。

## 决策

1. Group 是管理员定义业务角色的主要载体；Permission Bundle 只是在单个 APP 内投影相关 Django Permission 的小粒度能力集合，不承载角色名称。
2. TechnicalDomain 范围通过 `TechnicalDomainGroupScope` 绑定 Group，不配置 User 级领域范围。
3. 普通用户的领域授权要求存在同一个 Group，同时拥有目标 Django Permission 与目标 TechnicalDomain Scope；不同 Group 的 Permission 与 Scope 不得串联。
4. Django Permission 仍是运行时能力事实，selector/policy 负责对象范围；业务代码不判断 Bundle code、Group 名称或 `GroupProfile.codename`。
5. superuser 是唯一全局绕过者。删除项目管理员角色、`standards.manage_all_technical_domains` 和 `TechnicalDomainMembership`，不引入通用 Scope、deny/override 或第三方对象权限框架。
6. 标准体系有相应 view Permission 时全项目可查看；长期 Skill 按 `primary_domain` 维护，当前技能树节点按版本所属 TechnicalDomain 维护。SkillProject、TechnicalDomain、SkillTreeVersion 与 WSOS 治理现阶段仅允许 superuser。

## 后果

管理员需要先创建 Group，组合 APP 内 Permission Bundle 或显式权限，再配置 TechnicalDomain Scope 并加入成员。用户直接权限可继续用于不需要领域范围的能力，但不能绕过领域写入限制。旧 User Membership 不自动推断到 Group；部署前应导出旧关系供人工参考，迁移后重新配置 Group 并运行权限投影对账。
