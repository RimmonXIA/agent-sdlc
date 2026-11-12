# Agent SDLC Skills

| 技能 | 何时使用 | 实际作用 |
|---|---|---|
| `problem-framing` | 问题与投入方向未明确 | 界定问题、价值、假设与最小下一步 |
| `change-contract` | 选定问题准备进入实现 | 明确行为、边界与可核对的完成条件 |
| `design-decision` | 新设计取舍或旧约束复审 | 推荐选择、保留理由与重议条件 |
| `work-decomposition` | 工作需要拆分、交接或协调 | 形成有产出、依赖和整合责任的任务图 |
| `repo-continuity` | 接手陌生项目或跨会话续做 | 恢复当前目标、约束和状态并推进任务 |
| `change-impact` | 接口、数据或共享语义将改变或已改变 | 定位语义依赖、必要处理与待查范围 |
| `contract-check` | 需要对照有效要求核对行为 | 给出可复现差异与检查覆盖边界 |
| `semantic-integration` | 多份独立结果准备组合 | 协调共享假设，核对端到端组合行为 |
| `change-closeout` | 实质改动完成，准备交付或提交 | 同步相关成果和任务，整理必要依据 |
| `migration-plan` | 旧新接口、数据或依赖需要共存和切换 | 规划阶段条件、兼容、恢复与退役 |
| `release-status` | 准备判断发布或交付完成情况 | 区分实现、构建、部署、激活与行为观测 |
| `incident-diagnosis` | 发生运行异常或回归 | 只读定位，区分观察与原因假设并建议恢复 |
| `outcome-review` | 改变已产生真实使用或反馈 | 对照原目标评价效果、成本和替代解释 |
| `context-boundary` | 反复出现上下文与协调负担 | 定位语义耦合并推荐有界结构调整 |

各项独立使用，不是每次开发都要经过的 14 道步骤。输入、行动边界、完成与停止条件写在各自 `SKILL.md`；没有强制的跨技能依赖。

## 安装与调用

需要 Python 3.8 或更高版本，以及支持本地技能的 Codex。解压分发包或在源码目录执行：

```bash
python3 scripts/manage_skill.py install --skill change-contract
python3 scripts/manage_skill.py status --skill change-contract
```

源码目录包含全部 14 项技能；可只安装需要的项。安装全部时，在源码目录执行以下循环；任何一项失败都会停止，已经安装成功的项保留，不声称整批原子回滚：

```bash
for skill in problem-framing change-contract design-decision work-decomposition \
  repo-continuity change-impact contract-check semantic-integration \
  change-closeout migration-plan release-status incident-diagnosis \
  outcome-review context-boundary; do
  python3 scripts/manage_skill.py install --skill "$skill" || break
done
```

单技能离线包只运行它对应的命令。安装到用户级 `~/.agents/skills/技能名`，复制完整技能及必要参考，不依赖源码仓库继续存在。省略 `--skill` 时保持 `repo-continuity` 的既有默认行为。不会修改全局 AGENTS、Codex 配置或目标项目文件。

在另一个 repo 启动新 Codex session，显式调用：

```text
Use $repo-continuity to resume the active task in this repository.

Use $change-impact to analyze the consumers affected by this proposed change. Analysis only.

Use $change-closeout to close out this change and prepare delivery. Do not commit yet.
```

也可以描述相应任务，让 Codex 按技能描述选择。每项技能的隐式选择都需要实际使用反馈，不因一个技能选中过就推断其他技能同样可靠。按需选择不保证每次发生；需要确定使用时显式调用。若技能尚未出现，启动新 session 再检查。

技能不强制目标项目采用 Git、AGENTS 或特定文档结构。任务需要的代码、消费者、数据或运行环境必须实际可取得；缺少关键输入时会指出具体缺口，不能凭技能正文补造现场事实。普通局部修改无需套用全流程。

## 更新与退出

在新的分发源码中再次执行 `install` 即更新；内容相同不会重写。安装器只管理有自己所有权凭据且内容未被本地修改的安装。遇到同名外来技能、本地修改或符号链接会拒绝覆盖，需要先人工保留和协调。

停止未来新 session 使用本技能，可执行：

```bash
python3 scripts/manage_skill.py uninstall --skill change-closeout
```

已在当前 session 加载的指令不会被卸载操作追溯移除；结束该 session 后生效。卸载不删除目标项目成果，也不修改其他技能。暂时退出可用卸载后按需重装；如需保留安装文件但禁用技能，可在用户 Codex 配置中添加对应条目，然后启动新 session：

```toml
[[skills.config]]
path = "/absolute/path/to/selected-skill/SKILL.md"
enabled = false
```

将示例路径替换为 `status` 返回的安装目录下的 `SKILL.md`；重新启用时只修改对应条目，不覆盖其他技能配置。

可用 `--skills-dir 路径` 指定隔离测试或其他明确的技能安装目录。该参数不会自动修改 Codex 的发现路径，目录本身必须是运行环境支持的位置。

## 构建离线分发包

```bash
python3 scripts/manage_skill.py bundle --skill change-contract --output dist/change-contract.zip
```

将 `--skill` 和输出文件名替换为表中任意技能，即可分别构建全部 14 项。

每个包只包含选定技能、必要参考、安装器和本说明，不包含研究论文、个人偏好、项目授权、测试会话或本机绝对路径。当前使用原生本地技能；安装生命周期采用 Python 标准库工具，不增加日常运行时服务或强制 hooks，也未提供插件市场入口。

## 权限与信息

技能帮助完成本轮任务，不授予额外权限。目标项目的有效约定与用户请求决定动作范围；不自动提交、推送、发布或创建总结文件。用户请求只分析或交接时，不自行实施。

目标项目的事实与决定留在其原有载体中，技能只分发方法。部署等现场状态需要相应访问条件，不能从旧提交或摘要中猜测。

每项技能的输入、行动与停止条件以其 `SKILL.md` 为准。理论依据留在研究材料中，安装和使用不依赖研究文件。

## 开发检查

以下检查在源码仓库执行；离线分发包不包含测试目录。

```bash
python3 -m unittest discover -s tests -v
```

单元测试覆盖安装保护、独立卸载及离线包换目录安装，不发起模型调用。已有手动行为检查驱动与实际结果见源码中的 `checks.md`；它们不随安装或单元测试启动，离线包不包含原始模型输出。
