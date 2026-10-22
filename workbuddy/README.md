# pmc-oa-pdf · WorkBuddy 版

> 批量下 PMC 全文 PDF，不用浏览器，不会被 PoW 拦。

这是同一个技能的 **WorkBuddy 原生版本**。与根目录的 Claude Code / Codex 版共用同一套
下载逻辑与 `scripts/pmc_pdf.py`，仅针对 WorkBuddy 做了两点适配：

1. frontmatter 增加 `agent_created: true`，标记为 AI 创建的技能，后续可直接修改更新；
2. `description` 补充中文触发词，让 WorkBuddy 更准确地自动唤起。

`scripts/pmc_pdf.py` 零第三方依赖，WorkBuddy 的 Python 环境直接能跑。

## 安装

**方式一：💬 自然语言安装（推荐）**

在 WorkBuddy 对话窗口直接粘贴：

```
帮我在 WorkBuddy 上安装 pmc-oa-pdf 技能。
文件来自 https://github.com/rcrusoe88-bot/pmc-oa-pdf 仓库的 workbuddy/ 子目录和 scripts/ 子目录，
请装到我的个人技能目录（Windows：%USERPROFILE%\.workbuddy\skills\pmc-oa-pdf，
macOS/Linux：~/.workbuddy/skills/pmc-oa-pdf），
注意 scripts/pmc_pdf.py 也要一起放进去，装完告诉我重启 WorkBuddy 生效。
```

**方式二：🖥️ 命令行安装**

```bash
# Windows (PowerShell)
git clone https://github.com/rcrusoe88-bot/pmc-oa-pdf %TEMP%\pmc-oa-pdf
xcopy /E /I %TEMP%\pmc-oa-pdf\workbuddy %USERPROFILE%\.workbuddy\skills\pmc-oa-pdf
xcopy /E /I %TEMP%\pmc-oa-pdf\scripts  %USERPROFILE%\.workbuddy\skills\pmc-oa-pdf\scripts

# macOS / Linux
git clone https://github.com/rcrusoe88-bot/pmc-oa-pdf /tmp/pmc-oa-pdf
mkdir -p ~/.workbuddy/skills/pmc-oa-pdf
cp /tmp/pmc-oa-pdf/workbuddy/SKILL.md ~/.workbuddy/skills/pmc-oa-pdf/
cp -r /tmp/pmc-oa-pdf/scripts ~/.workbuddy/skills/pmc-oa-pdf/
```

装完重启 WorkBuddy。

## 触发

说「帮我批量下载这批文献的 PDF」「这些 DOI 下不到全文」「PMC 的 PDF 下不下来」
会自动唤起。也可手动 `@pmc-oa-pdf`。

## 目录结构

```
workbuddy/
├── SKILL.md            # 技能主文件（WorkBuddy 适配版）
└── README.md           # 本说明
```

`scripts/pmc_pdf.py` 从仓库根目录的 `scripts/` 复制过来，两版共用。

## 与根目录版的差异

| 项目 | 根目录（Claude Code / Codex） | workbuddy/ |
|---|---|---|
| frontmatter | `name` + `description` | 加 `agent_created: true`，描述含中文触发词 |
| 附属配置 | `agents/openai.yaml` | 无（WorkBuddy 不识别） |
| 调用语法 | 支持 `$pmc-oa-pdf` | 技能面板或 `@` 手动指定 |
| 下载脚本 | `scripts/pmc_pdf.py` | 同一份，复制过去 |

## 国内网络说明

本技能只访问 `www.ebi.ac.uk` 和 `pmc-oa-opendata.s3.amazonaws.com`，
两个域名在国内均可直连，**不需要代理**。

## License

[MIT](../LICENSE) © 2026 rcrusoe88-bot
