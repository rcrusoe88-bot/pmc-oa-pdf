# Changelog

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。
格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

## [1.0.0] - 2026-10-22

首个公开版本。

### Added

- `scripts/pmc_pdf.py`：从 PMC OA S3 桶下载全文 PDF，支持 DOI / PMID / PMCID / 标题四种输入。
- 精确 key 匹配，排除同目录下的补充材料 PDF（`*_MOESM*_ESM.pdf`）。
- 指数退避重试，避免并发下的慢响应被误判为"无全文"。
- `%PDF-` 魔数校验，防止错误页被当成 PDF 落盘。
- `--manifest` 输出 JSON 结果清单，含 `ok` / `no-pdf` / `no-pmcid` / `error` 四种状态。
- `scripts/selfcheck.py`：离线逻辑检查 + 联网端到端检查。
- 多端适配：Claude Code（`SKILL.md`）、Codex/ChatGPT（`agents/openai.yaml`）、
  WorkBuddy（`workbuddy/`）。
- GitHub Actions CI：3 平台 × 2 Python 版本，且不安装任何依赖（依赖一旦出现即失败）。

### Notes

- 实测覆盖率 98.7%（150 篇跨主题抽样）。
- 只访问 `www.ebi.ac.uk` 与 `pmc-oa-opendata.s3.amazonaws.com`，国内可直连。
