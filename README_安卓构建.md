# LanShare Android（Chaquopy 嵌入版）

把现有 LanShare Python 服务（零重写）打包成可安装的安卓 APK。本机无需装任何 Android 工具链——**编译在 GitHub Actions 云端自动完成**。

## 目录结构

```
LanShare-Android-App/
├── settings.gradle / build.gradle / gradle.properties
├── app/
│   ├── build.gradle                # Chaquopy + AGP 配置
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/cn/lanshare/app/MainActivity.kt   # App 壳（WebView 管理面板）
│       ├── python/                 # ★ 内嵌的 Python 代码
│       │   ├── main.py             #    Chaquopy 入口 → launch_android()
│       │   ├── LanShare.py         #    服务本体（跨平台版）
│       │   └── templates.py        #    前端页面
│       └── res/values/strings.xml
└── .github/workflows/build-apk.yml # ★ 云端自动编译
```

## 🚀 三步出 APK

### 1. 建仓库
浏览器打开 https://github.com/new → 仓库名 `LanShare-Android`（Public 即可，Public 仓库 Actions 免费额度更高）→ 创建。**不要勾选**任何初始化文件（README/gitignore），保持空仓库。

### 2. 推送代码（浏览器已登录 GitHub，push 时自动弹出授权，点允许即可）
在本机执行（我来执行或按下面命令）：
```bash
cd C:\Users\17834\Desktop\LanShare-Android-App
git init
git add -A
git commit -m "LanShare Android app (Chaquopy)"
git branch -M main
git remote add origin https://github.com/<你的用户名>/LanShare-Android.git
git push -u origin main
```

### 3. 等云端编译 & 下载
1. 打开 https://github.com/<你的用户名>/LanShare-Android/actions
2. 首次 push 会自动触发 `Build LanShare APK`，约 **8-15 分钟**（Chaquopy 需下载 Python 运行时）
3. 变绿后进入该次运行 → 底部 **Artifacts → LanShare-apk.zip** → 下载
4. 解压得到 `app-debug.apk`，传到手机安装（需允许"安装未知应用"）

## 📱 安装后使用

1. 打开 App → 自动启动服务（首次约 3-8 秒）
2. 顶部显示**共享地址**（如 `http://192.168.1.8:8766`），其他设备浏览器访问即可下载
3. App 内嵌管理面板：换共享目录、改权限、看日志
4. 默认共享手机 `Download` 目录（只读）

### Android 版本兼容
- Android 12 及以下：打开 App 时弹窗授权"读写存储"，允许即可
- **Android 13+**：点界面上的「文件权限」按钮 → 系统设置授予"所有文件访问"→ 返回重开

## 🔧 修改要点

| 想改什么 | 改哪里 |
|---|---|
| 默认共享目录 | `python/LanShare.py` 的 `launch_android()`（改 `/sdcard/Download`） |
| 默认权限 | 同上函数里 `CFG["permission"] = "read"` |
| 端口 | `python/LanShare.py` DEFAULT_CONFIG |
| App 名字 | `app/src/main/res/values/strings.xml` |
| Python 版本 | `app/build.gradle` 的 `python { version }` |

## ⚠️ 已知限制
- 熄屏/退出 App 后服务停止（如需常驻后台，后续加前台服务）
- 编译需 GitHub Actions 免费额度（Public 仓库无限）
- 首次构建 Chaquopy 下载较大，耐心等 8-15 分钟
