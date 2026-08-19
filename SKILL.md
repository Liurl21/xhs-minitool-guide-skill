---
name: xhs-mini-tool-developer-guide
description: 依据最新的小红书小工具容器指南开发、审查和排查小工具。用于离线打包、CSP 与资源限制、Web API 和 WebGL 兼容性、媒体处理、window.xhs.miniTool 端能力及第三方库可行性判断；每天首次调用时自动更新指南。
---

# 工作流程

1. **更新指南**：回答或修改代码前运行 `python3 <技能目录>/scripts/update_guide.py`。读到状态行后继续；刷新失败且存在缓存时继续使用，仅在时效影响结论时说明。
2. **选择分支**：只读取与当前任务匹配的文件；任务跨分支时再按需组合。
   - 回答能力问题或判断方案可行性：读取 `references/answering.md`。
   - 开发或修改小工具：读取 `references/development.md`。
   - 审查代码、排查故障或兼容性问题：读取 `references/review-debug.md`。
3. **执行任务**：按照分支文件定位 `references/guide.md` 的相关章节。仅在 Markdown 格式有疑义时查 `references/guide.html`。
4. **交付结果**：给出结论或合规实现，引用对应章节和客户端版本要求。没有合规实现时，说明限制并提供最接近的替代方案。

## 关键约束

- 默认采用完全离线、自包含的实现。
- 区分普通浏览器预览与小红书容器行为；调用前检测 `window.xhs?.miniTool`。
- 严格遵循 Promise、回调和参数校验约定。
- 仅在用户要求立即复查或诊断更新器时运行 `python3 <技能目录>/scripts/update_guide.py --force`。
