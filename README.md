# pmc-oa-pdf

**批量下载 PubMed Central 开放获取全文 PDF，绕开 PMC 的工作量证明拦截。**

纯标准库，无浏览器、无鉴权、无 API key。实测跨主题抽样覆盖率 **98.7%**，单篇 2–4 秒。

---

## 它解决什么问题

如果你用 Playwright / browser-use 批量下 PMC 的 PDF，大概率会遇到：明明页面能打开，PDF 却下不下来，或者下回来是个 HTML。

**根因不是反爬检测，是工作量证明（PoW）：**

```
GET https://pmc.ncbi.nlm.nih.gov/articles/PMC13598902/pdf/DDR-87-e70392.pdf
→ 200, content-type: text/html, 1814 bytes
```

```js
const POW_CHALLENGE  = "VwR3BGV2ZmZ2AQthAGx0Zwtv:86ti8ed_...";
const POW_DIFFICULTY = "4";   // 找 nonce 使 sha256(challenge+nonce) 以 "0000" 开头
const POW_COOKIE_NAME = "cloudpmc-viewer-pow";
// 通过后写 cookie → window.location.reload()
```

每篇 PDF 都要重跑一次挑战。所以：

- 换浏览器指纹 ❌ 无效
- 用 patchright / camoufox / nodriver 等反检测库 ❌ 无效
- 接管日常浏览器的登录态 ❌ 无效
- 提高并发 ❌ 更糟，叠加限速

**正确的做法是换一层**：PMC 的开放获取内容在 AWS S3 上有官方镜像，无鉴权、无 PoW、无 cookie。

```
https://pmc-oa-opendata.s3.amazonaws.com/PMC13598902.1/PMC13598902.1.pdf
→ 200, 1,975,365 bytes, 2.2s
```

本项目就是这条路。

---

## 安装

### Claude Code

```bash
# 个人技能目录
git clone https://github.com/rcrusoe88-bot/pmc-oa-pdf ~/.claude/skills/pmc-oa-pdf
```

或者直接把 `SKILL.md` 和 `scripts/` 放进 `~/.claude/skills/pmc-oa-pdf/`。

### ChatGPT / Codex

把 `agents/openai.yaml` 和 `SKILL.md` 一起导入你的自定义 agent。
`agents/openai.yaml` 里定义了展示名、简介和默认 prompt。

### WorkBuddy

见 [`workbuddy/README.md`](workbuddy/README.md)，有自然语言安装话术。

### 任何 agent（包括国内网络环境）

**这个项目不需要翻墙**。它只访问两个域名：

- `www.ebi.ac.uk`（Europe PMC 检索）
- `pmc-oa-opendata.s3.amazonaws.com`（PDF 下载）

两个域名在国内均可直连，不需要代理。如果你有代理，走代理也不影响。

### 手动使用（不需要任何 agent）

```bash
git clone https://github.com/rcrusoe88-bot/pmc-oa-pdf
cd pmc-oa-pdf
python scripts/pmc_pdf.py 10.1002/ddr.70392 -o papers/
```

只要 Python 3.9+，零第三方依赖。

---

## 用法

```bash
# 单个或多个
python scripts/pmc_pdf.py 10.1002/ddr.70392 PMC13415181 -o papers/

# 从文件批量（每行一个 DOI / PMID / PMCID / 标题）
python scripts/pmc_pdf.py -f dois.txt -o papers/ -j 8 --manifest result.json

# 按标题（匹配到多篇会报错并列出候选，不会替你猜）
python scripts/pmc_pdf.py "Lipid nanoparticle mRNA delivery" -o papers/
```

| 参数 | 说明 |
|---|---|
| `-f, --file` | 从文件读标识符，每行一个 |
| `-o, --outdir` | 输出目录，默认 `papers/` |
| `-j, --jobs` | 并发数，默认 4，建议 8 |
| `--manifest` | 写 JSON 结果清单 |

### 退出码

`0` = 没有真正出错。文献不在 OA 子集属于正常结果，记在 manifest 的 `no-pmcid` 里。
`1` = 有 `error`（网络、解析等真故障）。

### manifest 结构

```json
{
  "total": 3,
  "ok": 2,
  "results": [
    {"input": "PMC13415181", "status": "ok", "detail": "PMC13415181 -> papers/PMC13415181.pdf (3365120 bytes)"},
    {"input": "10.1016/j.jpba.2026.117633", "status": "no-pmcid", "detail": "DOI ... has no PMCID (not in PMC or not OA)"}
  ]
}
```

`status` 取值：`ok` / `no-pdf` / `no-pmcid` / `error`。

---

## 覆盖率实测

2026-10 实测，三个主题各随机抽 50 篇，用 Range GET + `%PDF-` 魔数校验：

| 主题 | 命中数 | S3 有正文 PDF |
|---|---|---|
| LNP/mRNA | 8,396 | 50/50 = 100% |
| CAR-T | 43,791 | 50/50 = 100% |
| circRNA | 19,340 | 48/50 = 96% |
| **合计** | — | **148/150 = 98.7%** |

那 2 篇"缺失"实际有 PDF，是 10 并发下的超时误判，串行重试立刻 200。
**所以并发必须配 retry**——不加会把 1.3% 的正常文献误报成"无全文"。

### 不在 OA 子集怎么办

| 情况 | 处理 |
|---|---|
| 在 PMC 但 S3 无正文 PDF | 取 `fullTextXML` 渲染成 PDF，告知用户是重建版 |
| 不在 PMC / 非 OA | 换通道：出版社 TDM → 机构登录态 |

**本项目只交付 PDF，不交付 XML。** XML 只在重建 PDF 时作中间产物。

---

## 两个容易踩的坑

### 1. 目录里混着补充材料 PDF

```
PMC13522490.1/PMC13522490.1.pdf                  ← 正文
PMC13522490.1/41467_2026_75923_MOESM1_ESM.pdf    ← 补充材料
```

取"目录里第一个 .pdf"会拿到 SI。必须精确匹配 `^{PMCID}\.\d+/{PMCID}\.\d+\.pdf$`。

### 2. 版本号不一定是 1

修订过的文章是 `.2` / `.3`。要 list prefix 探测，不能硬拼 `PMCID.1.pdf`。

---

## 自检

```bash
python scripts/selfcheck.py            # 含网络（下载 3 篇真实文献验证）
python scripts/selfcheck.py --offline  # 仅逻辑检查
```

---

## 合规

只访问 PMC 官方 Open Access 子集——即作者与出版方已授权开放获取的内容。
不绕过任何付费墙，不访问 Sci-Hub 类站点。下载后请遵守各篇的 CC 许可条款。

---

## 相关

如果你要的是**检索 → 筛选 → 分层 → 下载**的完整文献挖掘流程，看
[lit-mining](https://github.com/rcrusoe88-bot) 系列。本项目是其中"下载"这一环的专用实现。

## License

[MIT](LICENSE)
