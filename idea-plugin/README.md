# Reverb Agent IDEA Plugin

此插件专为 JetBrains 系列 IDE（包括 IntelliJ IDEA、Android Studio、WebStorm、PyCharm 等）设计。它会在后台默默监听您的代码编辑活动（如文件切换、代码输入等），并将这些上下文事件通过 WebSocket 实时推送给本地运行的 Reverb Agent，帮助模型理解您的编程思路和工作流。

## 事件拦截说明

目前本插件会自动拦截并上报以下 IDE 核心事件：

1. **文件打开与获得焦点 (`file_focus`)**
   - **拦截时机**: 当您在编辑器中新打开一个文件，或者点击切换到某个已打开的文件标签页时。
   - **上报内容**: 文件的绝对路径、文件名。
   - **作用**: 让 Reverb 知道您目前正在关注和阅读哪段代码。

2. **文件关闭 (`file_closed`)**
   - **拦截时机**: 当您关闭一个代码标签页时。
   - **上报内容**: 文件的绝对路径、文件名。
   - **作用**: Reverb 可以感知您完成了对某部分的阅读或修改。

3. **代码输入与编辑 (`user_action: edit`)**
   - **拦截时机**: 当您在代码编辑器中输入任何字符、粘贴代码或进行删除操作时。
   - **防抖机制**: 为了避免每次按键都触发海量请求，该事件默认带有 **1000毫秒 (1秒)** 的防抖处理。只有当您连续敲击键盘停顿后，才会上报。
   - **上报内容**: 当前正在编辑的文件名，事件类型标记为 `edit`。出于隐私和性能考虑，目前**不会**上报完整的代码文档内容，只上报“您正在编辑文件”的行为。
   - **作用**: 帮助模型分析您停留在某个文件上不仅是阅读，而是正在积极修改逻辑。

> **WebSocket 连接说明**: 插件会在 IDE 启动时自动尝试连接到本地地址 `ws://127.0.0.1:19997`。如果 Agent CLI 没有运行，插件也会默默工作并等待重连，不会影响您写代码的心情。

---

## 编译与安装指南

本插件使用现代的 Gradle Kotlin DSL (`build.gradle.kts`) 构建。

### 1. 导入项目到 IDE
1. 打开您的 IntelliJ IDEA。
2. 点击菜单栏的 `File -> Open`，并选择当前这整个 `idea-plugin` 目录。
3. IDEA 会自动识别出这是一个 Gradle 工程。此时右下角可能会出现同步提示，允许 IDEA 自动下载所需的 Gradle Wrapper 和相关的 IntelliJ Plugin SDK 依赖。*(第一次同步下载可能需要几分钟，请耐心等待)*

### 2. 本地沙盒调试 (强烈推荐)
在将插件安装到自己平时干活的 IDE 之前，您可以先通过沙盒环境安全地测试：
1. 展开 IDEA 最右侧的 **Gradle** 工具窗口。
2. 依次展开目录：`Tasks -> intellij -> runIde`。
3. **双击 `runIde`** 任务。
4. 这时会自动弹出一个全新的、干净的 IntelliJ IDEA（即沙盒实例），其中已自动预装了本插件。
5. 在终端运行 `reverb observe --observers intellij`，然后在沙盒 IDEA 里随便敲几行代码或切换文件，您就能在 Web 控制台实时看到被拦截的上报事件了。

### 3. 编译打包成安装包
如果您觉得测试没问题，需要把它打包起来发给别人，或是安装到自己的主力 IDE：
1. 在 IDEA 底部打开 **Terminal (终端)**。
2. 执行构建命令：
   ```bash
   ./gradlew buildPlugin
   ```
   *(或者您也可以在右侧的 Gradle 工具窗口中双击 `Tasks -> intellij -> buildPlugin` 任务)*。
3. 构建成功后，安装包会生成在这个路径下：
   `idea-plugin/build/distributions/reverb-idea-plugin-1.0-SNAPSHOT.zip`

### 4. 安装到主力 IDE
1. 打开您的主力 IDE 的 `Settings / Preferences` (设置) -> `Plugins` (插件)。
2. 点击顶部右侧的齿轮图标 ⚙️。
3. 选择 **Install Plugin from Disk... (从磁盘安装插件)**。
4. 在弹出的文件选择器中，选中您刚才编译出来的 `.zip` 压缩包文件。
5. 点击确认后，按提示**重启 IDE**。大功告成！