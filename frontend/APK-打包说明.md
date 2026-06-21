# 智库云 APK 打包说明

## 当前方案

本项目使用 Capacitor 将现有 Next.js 前端封装成 Android APK。

- Web 端继续使用同一套前端代码
- APK 通过 `CAPACITOR_SERVER_URL` 加载线上 Web 页面
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

## 线上 Web 模式打包 APK

1. 先把前端部署到公网 HTTPS，例如：

```text
https://app.zhikuyun.com
```

2. 打包时指定线上地址：

```powershell
cd frontend
$env:CAPACITOR_SERVER_URL='https://app.zhikuyun.com'
```

3. 同步 Android 工程：

```powershell
npx cap sync android
```

4. 打开 Android Studio：

```powershell
npx cap open android
```

5. 在 Android Studio 里选择：

```text
Build -> Build APK(s)
```

APK 常见输出位置：

```text
frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

## 本地手机预览

如果 Android 手机和电脑在同一局域网，先查电脑局域网 IP，例如 `192.168.1.23`，然后用：

```powershell
cd frontend
$env:CAPACITOR_SERVER_URL='http://192.168.1.23:3000'
npx cap sync android
npx cap open android
```

同时前端接口也不要指向手机自己的 `localhost`，应改成电脑或服务器地址：

```powershell
$env:NEXT_PUBLIC_API_URL='http://192.168.1.23:8000'
npm run dev
```

## 如果要做本地静态包

当前 `capacitor.config.ts` 使用的是 `webDir = "out"`。
如果你以后想改成离线静态包，需要先让 Next.js 导出 `out/`，然后再执行：

```powershell
cd frontend
npm run build
npx cap sync android
```

## 重要说明

- APK 里不要再用 `http://localhost:8000`
- 线上 Web / APK 必须指向同一个后端域名
- 生产环境建议使用 HTTPS
- 如果后端 Cookie 登录在 Android WebView 里有兼容问题，再改成 token 登录
