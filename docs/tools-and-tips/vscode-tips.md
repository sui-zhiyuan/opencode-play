# VS Code 使用技巧大全（2026 版）

---

## 一、核心键盘快捷键

> 按 `Ctrl+K Ctrl+S` 打开快捷键编辑器，可搜索/自定义所有快捷键。

### 1. 导航类

| 操作 | Windows/Linux | macOS |
|------|--------------|-------|
| 命令面板（一切入口） | `Ctrl+Shift+P` | `Cmd+Shift+P` |
| 快速打开文件 | `Ctrl+P` | `Cmd+P` |
| 跳转到行 | `Ctrl+G` | `Ctrl+G` |
| 跳转到符号（当前文件） | `Ctrl+Shift+O` | `Cmd+Shift+O` |
| 跳转到符号（工作区） | `Ctrl+T` | `Cmd+T` |
| 前进/后退（浏览历史） | `Alt+←/→` | `Ctrl+-` / `Ctrl+Shift+-` |
| 跳转到匹配括号 | `Ctrl+Shift+\` | `Cmd+Shift+\` |
| 在 `Ctrl+P` 后输入 `@` | — | 直接搜索当前文件符号 |
| 在 `Ctrl+P` 后输入 `:` | — | 直接跳转到行号 |

### 2. 编辑类

| 操作 | Windows/Linux | macOS |
|------|--------------|-------|
| 删除整行 | `Ctrl+Shift+K` | `Cmd+Shift+K` |
| 上/下移动行 | `Alt+↑/↓` | `Opt+↑/↓` |
| 上/下复制行 | `Shift+Alt+↑/↓` | `Shift+Opt+↑/↓` |
| 在下方插入空行 | `Ctrl+Enter` | `Cmd+Enter` |
| 在上方插入空行 | `Ctrl+Shift+Enter` | `Cmd+Shift+Enter` |
| 切换行注释 | `Ctrl+/` | `Cmd+/` |
| 切换块注释 | `Shift+Alt+A` | `Shift+Opt+A` |
| 格式化文档 | `Shift+Alt+F` | `Shift+Opt+F` |
| 折叠/展开代码块 | `Ctrl+Shift+[/]` | `Cmd+Opt+[/]` |
| 重命名符号 | `F2` | `F2` |
| 跳到定义 | `F12` | `F12` |
| 查看定义（浮窗） | `Alt+F12` | `Opt+F12` |
| 查找所有引用 | `Shift+F12` | `Shift+F12` |
| 快速修复 | `Ctrl+.` | `Cmd+.` |
| 切换自动换行 | `Alt+Z` | `Opt+Z` |

### 3. 搜索与替换

| 操作 | Windows/Linux | macOS |
|------|--------------|-------|
| 文件内搜索 | `Ctrl+F` | `Cmd+F` |
| 文件内替换 | `Ctrl+H` | `Cmd+H` |
| 全局搜索 | `Ctrl+Shift+F` | `Cmd+Shift+F` |
| 全局替换 | `Ctrl+Shift+H` | `Cmd+Shift+H` |
| 下一个/上一个结果 | `F3` / `Shift+F3` | `Cmd+G` / `Cmd+Shift+G` |
| 下一个/上一个错误 | `F8` / `Shift+F8` | `F8` / `Shift+F8` |
| 搜索技巧 | — | 开启正则 (`Alt+R`)、全字匹配 (`Alt+W`)、大小写 (`Alt+C`) |

### 4. 视图与窗口

| 操作 | Windows/Linux | macOS |
|------|--------------|-------|
| 切换侧边栏 | `Ctrl+B` | `Cmd+B` |
| 聚焦资源管理器 | `Ctrl+Shift+E` | `Cmd+Shift+E` |
| 聚焦搜索 | `Ctrl+Shift+F` | `Cmd+Shift+F` |
| 聚焦源代码管理 | `Ctrl+Shift+G` | `Cmd+Shift+G` |
| 聚焦调试 | `Ctrl+Shift+D` | `Cmd+Shift+D` |
| 聚焦扩展 | `Ctrl+Shift+X` | `Cmd+Shift+X` |
| 切换终端 | `Ctrl+`` | `Ctrl+`` |
| 新建终端 | `Ctrl+Shift+`` | `Ctrl+Shift+`` |
| 拆分编辑器 | `Ctrl+\` | `Cmd+\` |
| 切换编辑器组 | `Ctrl+1/2/3` | `Cmd+1/2/3` |
| 关闭编辑器 | `Ctrl+W` | `Cmd+W` |
| 关闭所有编辑器 | `Ctrl+K Ctrl+W` | `Cmd+K Cmd+W` |
| 禅模式（专注） | `Ctrl+K Z` | `Cmd+K Z` |
| 缩放 | `Ctrl+=/-` | `Cmd+=/-` |

### 5. 调试

| 操作 | 快捷键 |
|------|--------|
| 切换断点 | `F9` |
| 开始/继续 | `F5` |
| 单步跳过 | `F10` |
| 单步进入 | `F11` |
| 单步跳出 | `Shift+F11` |
| 停止 | `Shift+F5` |

---

## 二、多光标编辑（杀手级功能）

这是 VS Code 相比终端编辑器的核心优势，学会后重构效率大幅提升。

| 操作 | Windows/Linux | macOS |
|------|--------------|-------|
| 选中下一个相同词 | `Ctrl+D` | `Cmd+D` |
| 跳过当前选中 | `Ctrl+K Ctrl+D` | `Cmd+K Cmd+D` |
| 选中所有相同词 | `Ctrl+Shift+L` | `Cmd+Shift+L` |
| 点击添加光标 | `Alt+Click` | `Opt+Click` |
| 上方/下方添加光标 | `Ctrl+Alt+↑/↓` | `Cmd+Opt+↑/↓` |
| 每行末尾添加光标 | `Shift+Alt+I` | `Shift+Opt+I` |
| 列选择（拖拽鼠标） | `Shift+Alt+拖拽` | `Shift+Opt+拖拽` |
| 列选择（键盘） | `Ctrl+Shift+Alt+方向键` | `Cmd+Shift+Opt+方向键` |
| 撤销上一个光标 | `Ctrl+U` | `Cmd+U` |

**经典组合技**：选中变量名 → 重复按 `Ctrl+D` 选中每个实例 → 输入新名字 → 全部同步修改。

### 文本变换命令（Command Palette 中搜索）

- `Transform to Uppercase` — 转大写
- `Transform to Lowercase` — 转小写
- `Transform to Title Case` — 转标题大小写
- `Transform to Snake Case` — 转 snake_case
- `Transform to Kebab Case` — 转 kebab-case

---

## 三、推荐 Settings（settings.json）

> `Ctrl+,` 打开设置 → 点击右上角 JSON 图标直接编辑 `settings.json`。

```json
{
  // === 编辑器行为 ===
  "editor.fontFamily": "'JetBrains Mono', 'Fira Code', monospace",
  "editor.fontSize": 14,
  "editor.fontLigatures": true,
  "editor.lineHeight": 1.6,
  "editor.minimap.enabled": false,          // 关闭小地图，省空间
  "editor.bracketPairColorization.enabled": true, // 内置括号着色
  "editor.guides.bracketPairs": "active",
  "editor.stickyScroll.enabled": true,      // 滚动时固定当前函数/类名
  "editor.linkedEditing": true,             // 自动重命名配对的 HTML 标签
  "editor.renderWhitespace": "boundary",    // 显示边界空白字符
  "editor.cursorBlinking": "smooth",
  "editor.cursorSmoothCaretAnimation": "on",
  "editor.wordWrap": "on",
  "editor.tabSize": 2,

  // === 保存时自动处理 ===
  "editor.formatOnSave": true,
  "editor.formatOnPaste": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": "explicit",
    "source.organizeImports": "explicit"
  },
  "editor.defaultFormatter": "esbenp.prettier-vscode",

  // === 文件管理 ===
  "files.autoSave": "onFocusChange",        // 失去焦点时自动保存
  "files.trimTrailingWhitespace": true,
  "files.insertFinalNewline": true,
  "files.exclude": {
    "**/.git": true,
    "**/node_modules": true,
    "**/dist": true,
    "**/.next": true
  },

  // === 工作台 ===
  "workbench.startupEditor": "none",         // 启动不显示欢迎页
  "workbench.editor.enablePreview": false,   // 关闭预览模式（单击文件不再被替换）
  "workbench.tree.indent": 16,
  "explorer.compactFolders": false,          // 不压缩单子文件夹显示

  // === 终端 ===
  "terminal.integrated.fontFamily": "'JetBrains Mono'",
  "terminal.integrated.fontSize": 13,

  // === 搜索排除 ===
  "search.exclude": {
    "**/node_modules": true,
    "**/dist": true,
    "**/coverage": true
  },

  // === 性能优化 ===
  "files.watcherExclude": {
    "**/node_modules/**": true,
    "**/.git/objects/**": true,
    "**/.git/subtree-cache/**": true
  },
  "extensions.autoCheckUpdates": false,

  // === 遥测（关闭） ===
  "telemetry.telemetryLevel": "off"
}
```

**五个最重要的设置**：
1. 关闭 minimap（`editor.minimap.enabled: false`）— 省水平空间
2. 开启 Sticky Scroll — 滚动时始终知道自己在哪个函数里
3. 关闭预览模式 — 单击文件不再被覆盖
4. 保存时自动格式化 — 格式化不再是有意识的行为
5. `files.watcherExclude` — 在 monorepo 中单行改动可大幅降低 CPU

---

## 四、必装扩展（少而精）

每个扩展都有启动成本，装真正需要的 5-10 个，不要装 50 个。

### 通用扩展（不分语言）

| 扩展 | 用途 |
|------|------|
| **Error Lens** | 内联显示错误/警告，无需悬停查看 |
| **GitLens** | Git blame、行历史、文件历史、分支对比 |
| **Prettier** | 代码格式化 |
| **ESLint** | JS/TS linting |
| **EditorConfig** | 团队统一的缩进/换行规则 |
| **Todo Tree** | 扫描 TODO/FIXME/HACK 注释，树状展示 |
| **Code Spell Checker** | 拼写检查 |

### 语言专用

| 语言 | 扩展 |
|------|------|
| Python | `ms-python.python` + Pylance + Ruff |
| Rust | `rust-analyzer` |
| Go | 官方 Go 扩展 |
| TypeScript | 内置 + Pretty TypeScript Errors |
| Tailwind CSS | Tailwind CSS IntelliSense |

### AI 编程

| 扩展 | 特点 |
|------|------|
| **GitHub Copilot** | 官方 AI 补全 + Chat + Agent 模式（2026 年有可用免费层） |
| **Continue** | 开源，支持任意 LLM / 本地 Ollama 模型 |
| **Cline** (原 Claude Dev) | 自主 Agent，计划→执行循环，支持 MCP |
| **Claude Code** | Anthropic 终端 Agent 的 VS Code 扩展 |

### 主题

- One Dark Pro / Catppuccin / Material Icon Theme

### 不该装的扩展（已内置）

- ❌ Bracket Pair Colorizer → VS Code 已内置
- ❌ Path Intellisense → VS Code 已内置路径补全
- ❌ Settings Sync → 已内置通过 GitHub/Microsoft 账号同步
- ❌ 各语言单独的 beautifier → 用 Prettier 统一格式化

---

## 五、高级功能

### 1. Remote Development（远程开发）

VS Code 最大优势之一。UI 在本地运行，语言服务器/终端/调试器在远端运行。

- **Remote-SSH**：SSH 连接到任意服务器，如同编辑本地文件
- **Dev Containers**：在 Docker 容器中开发，`.devcontainer/devcontainer.json` 定义环境
- **WSL**：Windows 上获得原生 Linux 开发体验
- **GitHub Codespaces**：云端开发环境

### 2. 调试器

VS Code 内置一流调试器（基于 Debug Adapter Protocol），支持条件断点、logpoints（打印不暂停）、行内变量值显示。

- `F5` 开始调试，`F9` 设断点
- 配置文件：`.vscode/launch.json`
- 条件断点：右键断点 → 编辑条件表达式
- Logpoint：断点处打印消息但不暂停执行
- `preLaunchTask`：调试前自动构建
- `compounds`：同时启动多个调试配置（如前后端一起调试）

### 3. Tasks（任务）

在 `.vscode/tasks.json` 中定义，通过 `Ctrl+Shift+B` 运行默认构建任务。

- Problem Matcher：将编译器/linter 输出变成 Problems 面板中可点击的错误
- `dependsOn` + `dependsOrder`：编排任务链（串行或并行）
- 后台任务：`isBackground: true` + background matcher 检测 watcher 就绪

### 4. 内置 Git

`Ctrl+Shift+G` 打开源代码管理面板。功能完整：暂存、提交、分支、合并、推送/拉取。

**进阶 Git 技巧**：
- **暂存选定行**：在 diff 视图中选中行 → 右键 Stage Selected Ranges
- **与剪贴板对比**：`Ctrl+Shift+P` → "Compare Active File with Clipboard"
- **选中两个文件对比**：在 Explorer 中 Ctrl+点击两个文件 → 右键 "Compare Selected"
- **Timeline 面板**：Explorer 底部，查看文件本地保存历史和 Git 提交
- `git.autofetch: true`：自动刷新远程状态

### 5. 多根工作区

将多个仓库合并到同一个窗口：

```json
// myproject.code-workspace
{
  "folders": [
    { "path": "./frontend" },
    { "path": "./backend" },
    { "path": "./shared-lib" }
  ],
  "settings": { "editor.tabSize": 2 },
  "extensions": { "recommendations": ["dbaeumer.vscode-eslint"] }
}
```

### 6. Profiles（配置集）

为不同场景（Python 数据科学、TypeScript 前端、纯写作）创建独立的扩展+设置+快捷键组合，一键切换。

### 7. Snippets（代码片段）

`Ctrl+Shift+P` → "Configure User Snippets" → 选择语言或全局。

### 8. Emmet

HTML/JSX 中内置，输入缩写后按 Tab 展开。如 `div.container>ul>li*5` 一键生成。

---

## 六、生产力技巧

1. **Command Palette 模糊匹配**：输入首字母即可，如 `ttt` → "Transform to Title Case"
2. **打开搜索结果到编辑器**：全局搜索后点击 "Open in Editor"，在大窗口中查看
3. **关闭所有编辑器**：`Ctrl+K Ctrl+W` — 快速清理工作区
4. **重新打开已关闭标签**：`Ctrl+Shift+T`
5. **Zen Mode 可自定义**：`zenMode.hideLineNumbers`、`zenMode.centerLayout` 等
6. **Breadcrumbs**：编辑器顶部路径导航，`Ctrl+Shift+;` 聚焦
7. **Outline 视图**：侧边栏显示当前文件所有符号结构
8. **Screencast Mode**：演示/结对编程时显示按键操作浮层
9. **Markdown 实时预览**：`Ctrl+Shift+V`（侧边预览 `Ctrl+K V`）
10. **复制文件路径**：`Ctrl+K P`
11. **在资源管理器中显示**：`Ctrl+K R`
12. **重新加载窗口**：`Ctrl+Shift+P` → "Developer: Reload Window"（不关闭服务）
13. **重启 TS 服务器**：`Ctrl+Shift+P` → "TypeScript: Restart TS Server"
14. **扩展二分排查**：`Ctrl+Shift+P` → "Help: Start Extension Bisect" 找出拖慢编辑器的扩展
15. **Timeline 恢复删除文件**：`Ctrl+Shift+P` → "Local History: Find Entry to Restore"

---

## 七、团队协作配置

### `.vscode/settings.json`（工作区设置）
提交到 Git，团队共享格式化规则、语言特定设置等。

### `.vscode/extensions.json`（推荐扩展）
```json
{
  "recommendations": [
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode",
    "eamodio.gitlens",
    "usernamehw.errorlens"
  ]
}
```

### `.editorconfig`
跨编辑器统一的缩进/换行/编码规则。

---

## 八、总结

VS Code 生产力的三大支柱：
1. **保存时自动格式化** — 不再思考格式问题
2. **多光标编辑** — 重构快 10 倍
3. **5-10 个精选扩展** — 不是 50 个

**先学会这 10 个快捷键，效率直接翻倍**：
`Ctrl+P`、`Ctrl+Shift+P`、`Ctrl+D`、`Alt+↑/↓`、`F2`、`Ctrl+/`、`Ctrl+Shift+K`、`Ctrl+\`、`Ctrl+B`、`Ctrl+``
