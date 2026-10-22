---
name: pmc-oa-pdf
description: |
  批量下载 PubMed Central 开放获取全文 PDF，绕开 PMC 页面的工作量证明拦截。
  实测覆盖率 98.7%，纯 HTTP、无鉴权、无浏览器、国内可直连。
  触发词：批量下载文献、下不到全文、PMC 被拦、DOI 转 PDF、文献 PDF 下载、全文获取。
  当用户给出 DOI / PMID / PMCID 列表、文献清单文件，或要求下载论文全文时使用。
agent_created: true
---

# PMC OA 全文 PDF 下载

## 为什么不用浏览器

PMC 的 PDF 直链不是被指纹检测拦的，是被**工作量证明（PoW）**拦的：

```
GET https://pmc.ncbi.nlm.nih.gov/articles/PMC13598902/pdf/DDR-87-e70392.pdf
→ 200, content-type: text/html, 1814 bytes   ← 不是 PDF
```

返回的是挑战页，要求找到 nonce 使 `sha256(challenge + nonce)` 以 `0000` 开头，
通过后写 `pmc-viewer-pow` cookie 再刷新页面。

所以换浏览器指纹、用反检测库、接管登录态，**全都不解决问题**。

PMC 的开放获取内容有官方 S3 桶，无鉴权、无 PoW：

```
https://pmc-oa-opendata.s3.amazonaws.com/PMC13598902.1/PMC13598902.1.pdf
→ 200, 1,975,365 bytes, 2.2s
```

本技能走这条通道。

## 使用

```bash
python scripts/pmc_pdf.py 10.1002/ddr.70392 PMC13415181 -o papers/
python scripts/pmc_pdf.py -f dois.txt -o papers/ -j 8 --manifest result.json
python scripts/pmc_pdf.py "Lipid nanoparticle mRNA delivery" -o papers/
```

输入可以是 DOI、PMID、PMCID 或标题。标题匹配到多篇时脚本会报错并列出候选，
不会替你猜。

## 流程

### 1. 归一化到 PMCID

用 Europe PMC REST（不需要 API key）：

| 输入 | 查询式 |
|---|---|
| DOI | `DOI:"10.xxxx/..."` |
| PMID | `EXT_ID:<pmid> AND SRC:MED` |
| PMCID | `PMCID:PMCxxxxxxx`，**要校验存在性** |
| 标题 | `TITLE:"..." AND OPEN_ACCESS:Y` |

### 2. 定位正文 PDF 的 S3 key

```bash
curl -s "https://pmc-oa-opendata.s3.amazonaws.com/?list-type=2&prefix=PMC13598902.&max-keys=200"
```

不要硬拼 `PMCID.1.pdf`——修订过的文章是 `.2`/`.3`。
不要取目录里第一个 `.pdf`——同一目录混着补充材料：

```
PMC13522490.1/PMC13522490.1.pdf                  ← 正文
PMC13522490.1/41467_2026_75923_MOESM1_ESM.pdf    ← 补充材料，不要
```

必须精确匹配 `^{PMCID}\.\d+/{PMCID}\.\d+\.pdf$`。

### 3. 下载并校验

前 5 字节必须是 `%PDF-`，否则当失败处理。

## 必须保留的两个防御

**retry**：S3 并发下偶发慢响应。不加 retry 会把约 1.3% 的正常文献误判成"无全文"。

**精确 key 正则**：见上，否则会拿到补充材料 PDF 而不自知。

## 覆盖率与降级

实测三主题各 50 篇：LNP/mRNA 100%、CAR-T 100%、circRNA 96%，合计 **98.7%**。
（circRNA 那 2 篇"缺失"是并发超时误判，加 retry 后为 100%。）

| 情况 | 处理 |
|---|---|
| S3 有正文 PDF（≈99%） | 直接下 |
| 在 PMC 但 S3 无正文 PDF | 取 `fullTextXML` 渲染成 PDF，**告知用户是重建版** |
| 不在 PMC / 非 OA | 换通道：出版社 TDM → 机构登录态 |

**本技能只交付 PDF，不交付 XML。**

## 输出

默认落到 `papers/`，文件名 `{PMCID}.pdf`。
`--manifest` 写 JSON，含每篇 `status`：`ok` / `no-pdf` / `no-pmcid` / `error`。

退出码只在真出错时为非零；文献不在 OA 子集是正常结果，不算失败。

## 批量建议

- 并发 `-j 8` 较稳，再高收益递减
- 单篇 2–4 秒，100 篇约 1 分钟
- 同一篇别重试超过 4 次，S3 的 404 是真的没有

## 国内网络

只访问 `www.ebi.ac.uk` 和 `pmc-oa-opendata.s3.amazonaws.com`，
两个域名国内均可直连，**不需要代理**。

## 合规

只访问 PMC 官方 Open Access 子集。不绕过付费墙，不访问 Sci-Hub 类站点。
下载后请遵守各篇的 CC 许可条款。
