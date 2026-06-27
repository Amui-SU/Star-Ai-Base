# 智库云 APK 打包说明

## 当前方案

本项目使用 Capacitor 将现有 Next.js 前端封装成 Android APK。

- Web 端继续使用同一套前端代码
- APK 默认内置静态前端资源，不再写死某个局域网 IP
- 手机端通过“连接设置”保存电脑端后端地址，例如 `http://192.168.1.23:8000`
- 后端继续使用同一套 FastAPI API，所以 Web / APK 数据互通

## 已添加文件

- `frontend/capacitor.config.ts`
- `frontend/android/`

## 本地开发

先启动后端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 start -SkipFrontend
```

如果你只想手动跑后端：

```powershell
C:\ProgramData\anaconda3\envs\bilibili-rag\python.exe -m uvicorn app.main:app --app-dir "G:\gitbase\智库云 - 手机版\star-base-main" --host 0.0.0.0 --port 8000
```

再启动前端：

```powershell
cd frontend
npm run dev
```

## 默认本地静态 APK

默认打包方式适合本地局域网使用。先导出前端静态资源并同步 Android 工程：

```powershell
cd frontend
npm run build
npx cap sync android
```

然后构建 APK：

```powershell
cd android
.\gradlew.bat assembleDebug
```

APK 常见输出位置：

```text
frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

安装后，手机端点“连接设置”，填写电脑端后端地址：

```text
http://<电脑局域网 IP>:8000
```

例如：

```text
http://192.168.1.23:8000
```

## 本地手机预览

如果 Android 手机和电脑在同一局域网，启动脚本会打印手机端可填写的地址：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 start
```

看到类似下面这一行后，在 APK 的“连接设置”里填写它：

```text
Mobile local connection address: http://192.168.1.23:8000
```

如果手机浏览器也要预览 Web 端，可以打开：

```text
http://192.168.1.23:3000
```

## 线上 Web 模式

如果以后部署到公网 HTTPS，有两种做法：

- 保持默认内置静态 APK，只在“连接设置”里填写公网 API 域名。
- 或者显式使用 `CAPACITOR_SERVER_URL` 加载线上 Web 页面。

使用线上 Web 页面时：

```powershell
cd frontend
$env:CAPACITOR_SERVER_URL='https://app.zhikuyun.com'
npx cap sync android
```

完成后可以打开 Android Studio 构建：

```powershell
npx cap open android
```

## 重要说明

- 默认 APK 不再依赖 `CAPACITOR_SERVER_URL`
- 本地局域网换了以后，只需要在手机端“连接设置”里更新后端地址
- 线上 Web / APK 应指向同一个后端域名
- 生产环境建议使用 HTTPS
- 生产外发时，网关限流或反向代理限流必须覆盖 `POST /system-auth/send-code`，按真实客户端 IP 做 per-IP 限制，并向后端保留可信 `X-Forwarded-For`
- 手机端本地静态 APK 使用 bearer token 登录态，Web 端继续兼容 Cookie 登录
