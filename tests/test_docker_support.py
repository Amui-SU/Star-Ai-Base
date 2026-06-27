from pathlib import Path


def test_docker_support_files_define_backend_frontend_and_compose():
    project_root = Path(__file__).resolve().parents[1]
    backend_dockerfile = project_root / "Dockerfile.backend"
    frontend_dockerfile = project_root / "frontend" / "Dockerfile"
    compose_file = project_root / "docker-compose.yml"
    dockerignore = project_root / ".dockerignore"

    for path in [backend_dockerfile, frontend_dockerfile, compose_file, dockerignore]:
        assert path.exists(), path

    backend_content = backend_dockerfile.read_text(encoding="utf-8")
    assert "uvicorn" in backend_content
    assert "app.main:app" in backend_content
    assert "EXPOSE 8000" in backend_content
    frontend_content = frontend_dockerfile.read_text(encoding="utf-8")
    assert "npm ci" in frontend_content
    assert "npm run build" in frontend_content
    assert "nginx" in frontend_content

    compose_content = compose_file.read_text(encoding="utf-8")
    assert "backend:" in compose_content
    assert "frontend:" in compose_content
    assert "path: .env.example" in compose_content
    assert "path: .env.local" in compose_content
    assert "required: false" in compose_content
    assert "8000:8000" in compose_content
    assert "3000:80" in compose_content

    ignored = dockerignore.read_text(encoding="utf-8")
    for entry in [".env.local", "data/", "logs/", "frontend/node_modules/"]:
        assert entry in ignored


def test_production_docs_require_gateway_verification_code_rate_limit():
    project_root = Path(__file__).resolve().parents[1]
    readme = (project_root / "README.md").read_text(encoding="utf-8")
    release_checklist = (project_root / "docs" / "移动端发布检查清单.md").read_text(
        encoding="utf-8"
    )
    maintenance_plan = (project_root / "docs" / "大版本完善执行方案.md").read_text(
        encoding="utf-8"
    )
    combined = "\n".join([readme, release_checklist, maintenance_plan])

    assert "POST /system-auth/send-code" in combined
    assert "网关限流" in combined or "反向代理限流" in combined
    assert "X-Forwarded-For" in combined
    assert "真实客户端 IP" in combined
    assert "per-IP" in combined


def test_release_maintenance_docs_are_aligned_with_current_boundaries():
    project_root = Path(__file__).resolve().parents[1]
    readme = (project_root / "README.md").read_text(encoding="utf-8")
    apk_docs = (project_root / "frontend" / "APK-打包说明.md").read_text(
        encoding="utf-8"
    )
    feature_outline = (project_root / "docs" / "功能大纲.md").read_text(
        encoding="utf-8"
    )
    maintenance_plan = (project_root / "docs" / "大版本完善执行方案.md").read_text(
        encoding="utf-8"
    )

    assert "少量共享 demo/local/glass 样式" not in maintenance_plan
    assert (
        "残余 demo、empty hero、glass action、user message action 与 `fadeUp` 已迁入"
        in maintenance_plan
    )
    assert "不会自动恢复或重试" in maintenance_plan
    assert "启动时标记为 `interrupted`" in maintenance_plan
    assert "本地与局域网来源" in readme
    assert "宽松配置" not in readme
    assert "POST /system-auth/send-code" in apk_docs
    assert "网关限流" in apk_docs or "反向代理限流" in apk_docs
    assert "可信 `X-Forwarded-For`" in apk_docs
    assert "legacy 兼容导出" in feature_outline
