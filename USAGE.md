# Repo Continuity

在陌生项目或新会话中接手已有工作，取得当前目标、约束和状态，继续用户实际任务，并只留下必要的接续信息。

## 安装与调用

需要 Python 3.8 或更高版本，以及支持本地技能的 Codex。解压分发包或在源码目录执行：

```bash
python3 scripts/manage_skill.py install
python3 scripts/manage_skill.py status
```

默认安装到用户级 `~/.agents/skills/repo-continuity`，复制完整技能及必要参考，不依赖源码仓库继续存在。不会修改全局 AGENTS、Codex 配置或目标项目文件。

在另一个 repo 启动新 Codex session，显式调用：

```text
Use $repo-continuity to resume the active task in this repository.
```

也可以描述“接手这个项目，继续尚未完成的工作”，让 Codex 按技能描述选择。按需选择不保证每次发生；需要确定使用时显式调用。若技能尚未出现，启动新 session 再检查。

该技能不要求目标项目有 Git、AGENTS 或某套文档结构；任务和关键背景确实缺失时，会提出具体问题。普通局部修改和一般问答无需接续流程。

## 更新与退出

在新的分发源码中再次执行 `install` 即更新；内容相同不会重写。安装器只管理有自己所有权凭据且内容未被本地修改的安装。遇到同名外来技能、本地修改或符号链接会拒绝覆盖，需要先人工保留和协调。

停止未来新 session 使用本技能，可执行：

```bash
python3 scripts/manage_skill.py uninstall
```

已在当前 session 加载的指令不会被卸载操作追溯移除；结束该 session 后生效。卸载不删除目标项目成果，也不修改其他技能。暂时退出可用卸载后按需重装；如需保留安装文件但禁用技能，可在用户 Codex 配置中添加对应条目，然后启动新 session：

```toml
[[skills.config]]
path = "/absolute/path/to/repo-continuity/SKILL.md"
enabled = false
```

将示例路径替换为 `status` 返回的安装目录下的 `SKILL.md`；重新启用时只修改对应条目，不覆盖其他技能配置。

可用 `--skills-dir 路径` 指定隔离测试或其他明确的技能安装目录。该参数不会自动修改 Codex 的发现路径，目录本身必须是运行环境支持的位置。

## 构建离线分发包

```bash
python3 scripts/manage_skill.py bundle --output dist/repo-continuity.zip
```

包包含技能、必要参考、安装器和本说明，不包含研究论文、个人偏好、项目授权、测试会话或本机绝对路径。它是原生技能分发包，不声称已经提供插件市场安装入口。

## 权限与信息

技能帮助完成本轮任务，不授予额外权限。目标项目的有效约定与用户请求决定动作范围；不自动提交、推送、发布或创建总结文件。用户请求只分析或交接时，不自行实施。

目标项目的事实与决定留在其原有载体中，技能只分发方法。部署等现场状态需要相应访问条件，不能从旧提交或摘要中猜测。

源码中的实现契约见 `capability.md`，理论依据留在研究材料中；安装和使用不依赖这些文件。

## 开发检查

以下检查在源码仓库执行；离线分发包不包含测试目录。

```bash
python3 -m unittest discover -s tests -v
```

源码中的 `tests/run_codex_checks.py` 可按指定用例启动独立 Codex CLI session，需要有效的现有登录与 Python 3.11 或更高版本。它使用正常用户配置和模型，不继承父会话；运行素材和原始输出写入显式指定的 scratchpad，不进入目标项目成果。单元测试不会自动运行这些模型调用。

```bash
python3 tests/run_codex_checks.py implicit --scratch-dir /path/to/session/scratchpad
```

运行条件与已检查范围见源码中的 `checks.md`；离线安装包不包含研究材料或原始模型输出。
