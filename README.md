# 小红书小工具开发者指南技能

这是一个面向 Codex 的小红书小工具开发技能。它依据官方《小工具容器能力清单》，帮助开发、审查和排查小工具中的运行环境、离线打包、资源加载、Web API、WebGL、媒体处理与端能力调用问题。

## 主要能力

- 根据官方指南回答小红书小工具开发问题。
- 检查 HTML、CSS、JavaScript 和第三方依赖是否符合容器限制。
- 指导使用 `postNote`、`saveImageToPhotosAlbum`、`writeTempFile` 等端能力。
- 在每天首次使用技能时检查官方页面，并自动更新本地指南。
- 更新失败时继续使用最近一次成功缓存，避免开发流程中断。

## 目录结构

```text
.
├── SKILL.md                         # 技能入口与工作流程
├── README.md                        # 项目说明
├── agents/
│   └── openai.yaml                 # Codex 界面信息
├── scripts/
│   └── update_guide.py             # 每日指南更新器
├── tests/
│   ├── test_update_guide.py        # 更新与转换回归测试
│   └── test_skill_structure.py     # 渐进式披露结构测试
└── references/
    ├── answering.md                 # 答疑与可行性判断分支
    ├── development.md               # 开发与修改分支
    ├── review-debug.md              # 审查与调试分支
    ├── guide.md                     # 便于检索的指南
    ├── guide.html                   # 官方页面原始副本
    └── .update-state.json           # 最近一次检查状态
```

## 使用方式

在 Codex 中调用 `$xhs-mini-tool-developer-guide`，然后提出开发、审查或兼容性问题。技能会先运行每日更新器，再检索本地指南中的相关章节。

技能采用渐进式披露：先加载 `SKILL.md` 的共通流程，再根据任务类型只读取一个分支文件，最后由分支文件按需定位 `guide.md` 的具体章节。跨类型任务才组合多个分支，避免每次加载全部说明。

手动检查更新：

```bash
python3 scripts/update_guide.py --force
```

查看更新器帮助：

```bash
python3 scripts/update_guide.py --help
```

## 每日更新机制

更新器以本地自然日为单位记录检查状态。每天第一次运行时，它会向官方页面发送条件请求，并使用 `ETag` 与 `Last-Modified` 判断内容是否变化。同一天后续调用直接使用本地缓存；传入 `--force` 可以立即复查。

下载成功后，更新器会在覆盖缓存前检查关键章节、端能力、表格和代码示例是否完整。页面异常、结构损坏或转换结果不完整时，原有 HTML 与 Markdown 缓存保持不变。

官方来源：<https://fe-video-qc.xhscdn.com/fe-platform-file/104101b8323q4m0uaga06277180ac7t8006ptl0e12ek1g>

## 运行测试

测试不访问网络，使用本地官方页面副本和模拟 HTTP 响应验证更新行为：

```bash
python3 -m unittest discover -s tests -v
```

测试覆盖有效页面更新、错误页回退、核心章节缺失、表格或代码示例损坏、304 响应下的缓存重建保护，以及分支指针完整性。

## 安装位置

本目录本身就是完整的技能目录。若需要让 Codex 自动发现，可将本目录复制或链接到：

```text
~/.codex/skills/xhs-mini-tool-developer-guide
```

作为源码保存时，本仓库目录可以使用当前名称；复制到 Codex 的技能目录时，安装目标目录请使用 `xhs-mini-tool-developer-guide`。
# xhs-minitool-guide-skill
