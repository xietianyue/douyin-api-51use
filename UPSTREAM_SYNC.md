# 上游同步与定制迁移手册

本仓库同时保留官方代码和 51use 定制代码。每次同步前先读本文件，避免把
“合并上游”误做成覆盖生产分支。

## 分支和远程职责

- upstream：官方仓库，只允许 fetch，push URL 已禁用。
- origin：xietianyue/douyin-api-51use，用于保存官方镜像分支和定制分支。
- main：仍是当前 v4 生产线，包含 Bilibili、Cookie 热更新和旧部署方式。
- codex/v5-integration：官方 v5 基线加 51use 兼容改造，是新解析服务迁移线。
- upstream/main、upstream/v4、upstream/release：推送到 origin 的官方分支镜像。
- custom-v4-production-2026-10-10：迁移前 v4 生产基线，可用于回滚和对照。

官方 v5 是完全重写，与 v4 没有可直接合并的共同代码历史。因此首次迁移采用
“以 v5 为基线，逐项移植定制能力”，不要把 v4 main merge 到 v5。

## 本次首次迁移的操作记录

本次已经完成以下仓库治理，后续无需重复：

1. 添加官方远程 upstream；
2. 把 upstream 的 push URL 设置为 no_push，防止误推官方仓库；
3. 扩展 origin 的 fetch 规则，使它能读取全部分支；
4. 从官方 upstream/main 创建 codex/v5-integration；
5. 把官方 main、v4、release 和修复分支镜像到 origin/upstream/name；
6. 在旧 v4 生产提交上创建 custom-v4-production-2026-10-10 标签；
7. 在 v5 集成分支重新实现旧 Worker 所需的私有接口，而不是合并无共同历史
   的 v4 文件树。

首次建立同类仓库时使用：

    git remote add upstream https://github.com/Evil0ctal/Douyin_TikTok_Download_API.git
    git remote set-url --push upstream no_push
    git config remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*"
    git fetch upstream --prune --tags
    git switch -c codex/v5-integration upstream/main

生产标签必须落在当时实际运行的 v4 提交上，不能凭分支名猜测：

    git tag -a custom-v4-production-YYYY-MM-DD <production-commit>
    git push origin custom-v4-production-YYYY-MM-DD

## 已移植与暂不移植

已移植：

1. POST /api/parse 兼容接口；
2. X-Internal-Token 内部鉴权；
3. v5 内容模型到旧 Worker 返回格式的转换；
4. INTERNAL_API_TOKEN 与同步等待时间配置。

无需按 v4 方式移植 Cookie 热更新。v5 使用身份池，Cookie/代理由控制台导入和
轮换，更新后无需重建镜像。

Bilibili 暂留在 v4 main。官方 v5 只支持 Douyin/TikTok；把 Bilibili 代码直接
塞入 v5 会扩大每次上游同步的冲突面。迁移期间应让 Bilibili 请求继续走 v4 服务，
或后续拆成独立服务。

## 后续同步官方更新

先确保工作区干净，再执行：

    git switch codex/v5-integration
    git fetch upstream --prune --tags
    git push origin refs/remotes/upstream/main:refs/heads/upstream/main --force-with-lease
    git push origin refs/remotes/upstream/v4:refs/heads/upstream/v4 --force-with-lease
    git push origin refs/remotes/upstream/release:refs/heads/upstream/release --force-with-lease
    git merge --no-ff upstream/main

如果上游新增了分支，只在确实需要长期保留时建立同名 upstream/name 镜像，
不要把临时 Dependabot 分支全部复制到 origin。

## 冲突处理顺序

1. 先保留官方 v5 的数据模型、任务队列、身份池和安全中间件；
2. 再恢复 src/dtk/api/routes/legacy.py 的旧协议兼容；
3. 检查 src/dtk/api/routes/__init__.py 中 legacy.router 是否仍被注册；
4. 检查 .env.example 中内部令牌说明是否仍存在；
5. 不从 v4 复制 crawler、依赖锁文件或 Dockerfile 覆盖 v5；
6. Bilibili 相关冲突在 v4 main 单独处理。

## 每次同步后的验证

    uv sync --extra dev
    uv run ruff check src tests
    uv run pytest tests/unit/test_legacy_api.py tests/unit/test_openapi_contract.py
    uv run pytest tests/unit

部署前还要在测试服务器完成：

1. 初始化 PostgreSQL、Redis、API、Worker 和 browser profile；
2. 从控制台导入 Douyin/TikTok 身份，确认池状态可用；
3. 设置 .env 的 INTERNAL_API_TOKEN，必须与 Cloudflare Worker 的
   DOUYIN_API_TOKEN secret 相同；
4. 用真实链接请求 /api/parse，再从现有小程序完整走一次解析和媒体代理；
5. 成功后再切换生产域名；失败则切回 v4 服务，不要删除 v4 数据和配置。

v5 不再使用旧的单容器 docker-compose.production.yml。测试服务器从仓库根目录
启动官方多服务栈：

    Copy-Item .env.example .env
    # 填写 DTK_SECRET_KEY、POSTGRES_PASSWORD、REDIS_PASSWORD、
    # INTERNAL_API_TOKEN，并按现有反向代理设置 DTK_BIND_PORT。
    docker compose --env-file .env -p dtk -f docker/compose.yml --profile browser up -d --build
    docker compose --env-file .env -p dtk -f docker/compose.yml ps

旧服务器上的 .env 不能直接覆盖新模板。应逐项迁移值；其中旧的
DOUYIN_COOKIE/TIKTOK_COOKIE 改为启动后从 v5 控制台导入身份池。

## 提交和推送

每次上游同步和冲突解决完成后先提交，再推送集成分支：

    git add src tests .env.example UPSTREAM_SYNC.md
    git commit -m "merge: sync upstream v5 and preserve 51use compatibility"
    git push origin codex/v5-integration

不要直接推送到官方 upstream。不要强推 main 或 codex/v5-integration；只有
origin 中的官方镜像分支允许使用 --force-with-lease 跟随官方历史。
