# 试用与问题反馈 / Support

先阅读 [README](README.md) 与[确定性业务查询说明](docs/business-workflow.md)。可先运行 README 中的离线命令：

```bash
uv sync --locked --extra dev
uv run --locked python scripts/business_query_demo.py
```

该样例使用虚构解析结果，不加载模型或调用 API。默认后端检索为 BM25；混合检索、vLLM 与真实企微服务需分别配置和验收。GitHub Pages 默认 Demo 页面也不能证明后端已部署。

在[项目 Issues](https://github.com/dev-belly/wecom-agent-platform/issues)说明：

- 使用离线业务样例、前端 Demo、Live 后端还是企微回调，以及源码 commit。
- Python / Node.js / 操作系统，执行步骤、预期结果和脱敏后的错误。
- 涉及索引时附 `index_revision` 与[快照说明](docs/index-snapshots.md)中对应阶段；使用虚构合同或持仓构造最小样例。

企微回调的本地验签、解密与主动发送回复是不同边界；当前 README 明确主动回复尚未接通。不要将缺少该链路当作已部署服务异常。合同、客户、凭据或安全问题先读 [Security](SECURITY.md)。

Start with the offline business demo. State which integration is involved and include synthetic inputs and redacted diagnostics.
