# Repository workflow

- Before fetching, merging, rebasing, or mirroring the official repository,
  read UPSTREAM_SYNC.md in full and follow its branch model.
- main is the customized v4 production line. codex/v5-integration is the v5
  migration line. They do not share a mergeable implementation history; port
  required behavior onto v5 instead of merging main into codex/v5-integration.
- Preserve the private POST /api/parse and X-Internal-Token compatibility
  contract used by the existing 51use Worker. Run tests/unit/test_legacy_api.py
  after every upstream sync.
- Official v5 supports Douyin and TikTok. Keep the current Bilibili integration
  on v4 main unless a separate migration is explicitly requested.
- Keep upstream fetch-only. Push official mirrors and customized branches only
  to origin.
- After verified code or configuration changes, create a local commit. Push
  only when the user explicitly requests it.
