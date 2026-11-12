---
name: change-closeout
description: "Reconcile a substantive software change before delivery or commit: update affected current artifacts and task state, preserve useful rationale, and keep process notes out of deliverables. Use when closing out an existing change, especially when code, docs, examples, and history may disagree. Not for generic status questions, arbitrary repository cleanup, or automatically committing work."
---

# 变更收尾

让一项改动留下准确的当前成果、可理解的变化依据和清楚的剩余工作。沿用项目的载体，不建立新的台账或统一文档树。

## 确定这次变更

从用户请求、当前任务和相关差异确定本轮目标与范围，遵循目标项目约定。辨别已有的无关改动，不把整个工作区都归为本任务。范围不明时先定位或询问，不借收尾扩大功能。

## 同步真正受影响的对象

沿改动的实际依赖检查调用方、契约、配置示例、测试、当前文档和活动任务。只修改受本轮变化影响的部分；不能从局部搜索推断全局没有依赖。发现超出范围的影响时，指出具体缺口并继续独立事项。

区分目标行为、源码状态与实际部署。代码已完成，不意味着发布已发生，也不意味着相关使用者已经迁移。

## 整理当前成果与变化依据

根据内容的用途判断，不按“包含日期、TODO 或为什么”机械删除：

- 当前规则、接口行为、有效限制及理解它所必需的理由，留在相关成果中，并消除与本轮变化有关的旧描述。
- “本轮改了什么、改过几次、运行了哪些命令、任务完成汇报”等过程文字，通常不属于当前规格。只保留仍有价值的依据到合适历史或提交说明，不自动新建总结文件。
- 发布说明、迁移安排、事故时间线和明确的历史记录可以保留历史；不要为了正文整洁破坏它们的用途。
- 缺少依据时标明未知；不要替旧设计编造理由，也不要把有用限制和未决风险一起清掉。

已有任务载体时同步本轮完成、取消或剩余状态，保留其他任务。运行与改动相称的检查，结果只支持其覆盖范围。

## 准备交付或提交

检查最终相关差异，避免混入无关工作。按项目约定和本轮授权决定是否暂存、提交、推送或发布；技能本身不授权这些动作。

有提交授权时，按可解释且适合恢复的语义变更组织提交，说明难从 diff 恢复的重要目的与取舍。没有提交授权或用户明确要求暂不提交时，在回复中提供简短建议即可，不把拟提交说明写进正式文档。

汇报实际结果、检查覆盖范围和影响交付的剩余事项，不将“已提交”“已部署”“效果已确认”互相替代。
