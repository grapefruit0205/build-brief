# Click — 为编码代理提供 revision-aware evidence

[English](README.md) | [한국어](README.ko.md) | 简体中文

[![CI](https://github.com/grapefruit0205/click/actions/workflows/ci.yml/badge.svg)](https://github.com/grapefruit0205/click/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 让验证结果始终和当前代码对应。

Click 的核心是 **revision-aware evidence**。

它记录的不是“测试以前通过过”，而是 **哪一版代码执行了哪项检查，以及结果现在是否仍然有效**。

你可以照常让 AI 工作。Click 会记住：

- 用户提出了什么请求；
- workspace 何时发生变化；
- 哪些检查真正执行过；
- 旧结果现在能否安全复用。

Click 不规定模型如何思考，也不限制它读取文件的顺序。

## 一个例子

~~~text
revision 12  修改认证代码 → 运行认证测试 → 通过
revision 13  只改 README   → 认证输入未变 → 复用结果
revision 14  再改认证代码 → 旧结果过期 → 重新测试
~~~

没有可靠记录时，代理可能在代码变化后继续相信旧测试，也可能因为无关改动重新运行很大的测试套件。

Click 只会在证明所依赖的输入仍然一致时复用结果。无法确认时，就重新检查。

这就是 Click 最重要的功能。

## 三种模式

| 模式 | 适用场景 | 使用体验 |
| --- | --- | --- |
| **Evidence**（默认） | 日常编码 | 不增加 Click 批准步骤，正常工作并获得 evidence receipt。 |
| **Guarded** | 付款、认证、删除等边界重要的工作 | 先确认一份简短 contract，再在范围内执行。 |
| **Off** | 不需要 Click 的工作 | 执行权限完全交给 host。 |

### Evidence：日常默认

Evidence 使用 Codex 或 host 已提供的权限。Click 不会假装自己批准了任务。

receipt 会明确写出：

~~~text
approval_bound: false
execution_authority: host
~~~

### Guarded：风险较高时使用

用户看到的是四个容易理解的部分，而不是原始 JSON：

~~~text
目标
完成后应该得到什么？

变更范围
允许修改什么？

保持不变
什么必须兼容或不能触碰？

完成检查
怎样确认任务完成？
~~~

原始 JSON 只是可选技术细节。批准发生在后续用户 turn；批准后，原范围内的细节调整无需反复批准。

## 安装

~~~bash
codex plugin marketplace add grapefruit0205/click
codex plugin add click@click
~~~

重启 Codex 以重新加载 Hook，然后开始新任务。

新安装默认使用 Evidence。

~~~text
click-gate default evidence
click-gate default guarded
click-gate default off
~~~

Evidence 模式下直接提出普通请求即可：

~~~text
重构认证解析器，并保持公开行为不变。
~~~

也可以明确选择 Guarded：

~~~text
@Click 添加订单取消功能，并防止重复退款。
~~~

## 更新

当前版本：**v0.50.0**

~~~bash
codex plugin marketplace upgrade click
codex plugin add click@click
~~~

更新后请开始一个新任务。

版本历史见 [Release Notes](RELEASE_NOTES.md)。

## evidence 何时可以复用？

以下信息必须继续匹配：

- 执行的检查；
- 与检查相关的文件和内容；
- 当前 workspace 状态；
- 环境和可执行文件；
- host Hook coverage。

任何一项不明确，Click 都会重新执行检查。

跨 revision 复用可以选择使用已提交的依赖映射：

~~~text
.click/evidence-dependencies.json
~~~

已提交的映射决定每项检查的复用权限。明确列出的文件始终是硬依赖；当
baseline 观察完整时，`*`、`**` 和目录前缀等扩展模式会收窄到检查实际读取的
输入，并一起写入 receipt 的哈希。仅存在于工作区的映射修改不能缩小已提交的
策略。如果观察不可用、失败、读取了外部输入，或未覆盖完整的子进程树，Click
会在 mutation 之后重新执行检查。该文件仍非必需；没有映射时也会重新检查。

## 完成 receipt

当前代码所需的 evidence 完整后，可以导出并验证 receipt：

~~~text
click-gate receipt export
click-gate receipt verify ./completion-receipt.json
~~~

receipt 会绑定请求链路、mutation revision、最终 workspace、检查结果、环境、可执行文件、host coverage 和复用来源。

当前验证报告为 **unsigned-integrity-only**：可以检查 receipt 是否被修改，但还不能证明发布者身份。

## Click 强制保证什么？

- Guarded 的批准和 contract ID；
- one-use 执行与 replay 防护；
- mutation revision 与过期 evidence 失效；
- 实际验证结果的 receipt；
- managed service 清理；
- receipt 完整性。

探索次数、计划方式、重试次数和模型推理策略不会被阻断，只会在必要时收到建议。

## Antigravity

仓库还包含实验性的 Google Antigravity 适配器：

~~~bash
agy plugin install ./dist/antigravity
~~~

适配器在 Antigravity 提供的 Hook 范围内支持 Evidence 和 Guarded。无法观察的路径不会被描述成已经独立观察。

详见 [Antigravity 适配器说明](platforms/antigravity/README.md)。

## 限制

Click 是 workflow guardrail，不是操作系统 sandbox。

它不能证明隐藏推理、语义正确性、未接入 Hook 的外部工具行为，也不能判断模型选择的测试是否足够好。请继续配合代码审查、CI、branch protection 和部署控制。

## 技术文档

README 有意保持简单。协议和架构细节放在以下文档：

- [产品宪法](PRODUCT_CONSTITUTION.md)
- [Guard 分类](GUARD_CLASSIFICATION.md)
- [运行模式](skills/click/references/modes.md)
- [Guarded contract 格式](skills/click/references/directive-format.md)
- [验证 profile](skills/click/references/verification-profiles.md)
- [Capability protocol](skills/click/references/capability-protocol.md)
- [Anti-loop policy](skills/click/references/anti-loop-policy.md)

## 许可证

[MIT](LICENSE)
