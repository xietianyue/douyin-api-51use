# 51use 视频链接解析服务

本目录基于 [Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API)（Apache-2.0）收敛而成，保留抖音、TikTok、哔哩哔哩的单条内容解析能力。

## 保留与移除

- 保留：三平台单视频/图文链接解析、标题、作者、封面和媒体直链结果。
- 移除：网页界面、接口文档、多平台完整 API、帐号列表、评论、批量接口、下载转发与 Cookie 更新接口。

## 服务接口

- `GET /healthz`：健康检查，无需令牌。
- `POST /api/parse`：统一解析接口。

`/api/parse` 必须带 `X-Internal-Token` 请求头，JSON 请求体示例：

```json
{"url":"https://v.douyin.com/example/"}
```

服务只返回解析结果，绝不下载或转存视频。

## 服务器部署（稍后执行）

1. 将本目录上传到服务器，例如 `/opt/douyin-api`。
2. 仅在服务器上将 `.env.example` 复制为 `.env`，填入 `INTERNAL_API_TOKEN`；各平台 Cookie 按需要填写。TikTok Cookie 应编码为 UTF-8 Base64 后写入 `TIKTOK_COOKIE_B64`，避免原始 Cookie 中的引号、空格或 $ 被 Docker env-file 语法解释。
3. 执行：`docker compose -f docker-compose.production.yml up -d --build`
4. 验证：`curl http://127.0.0.1:9010/healthz`

Docker 只绑定 `127.0.0.1:9010`。之后由 Nginx 的独立 `douyin-api.51use.cn` 虚拟主机转发；不要将 `.env` 提交到 Git。
