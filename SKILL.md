---
name: pmc-oa-pdf
description: |
  从 PubMed Central 官方开放数据通道批量下载全文 PDF，绕开 PMC 页面的工作量证明拦截。
  实测 150 篇跨主题抽样覆盖率 98.7%，纯 HTTP、无鉴权、无浏览器。
  触发条件：
  - 用户要批量下载文献 PDF / 全文
  - 用户给了 DOI、PMID、PMCID 列表或文献清单文件
  - 用户说"下不到全文"、"PMC 被拦"、"批量下文献"
  - 用户输入 /pmc-oa-pdf
---

# PMC OA 全文 PDF 下载

## 为什么不用浏览器

PMC 的 PDF 直链不是被指纹检测拦的，是被**工作量证明（PoW）**拦的：

```
GET https://pmc.ncbi.nlm.nih.gov/articles/PMC13598902/pdf/DDR-87-e70392.pdf
→ 200, content-type: text/html, 1814 bytes   ← 不是 PDF
```

返回的是挑战页，要求找到 nonce 使 `sha256(challenge + nonce)` 以 `0000` 开头，
通过后写 `cloudpmc-viewer-pow` cookie 再 `location.reload()`。

这意味着：**换浏览器指纹、换反检测库、接管登录态，全都不解决问题。**
每篇都要重跑一次挑战，批量时还叠加限速。

PMC 的开放获取内容有官方 S3 桶，无鉴权、无 PoW、无 cookie：

```
https://pmc-oa-opendata.s3.amazonaws.com/PMC13598902.1/PMC13598902.1.pdf
→ 200, 1,975,365 bytes, 2.2s
```

本 skill 走这条通道。

## 快速使用

```bash
python scripts/pmc_pdf.py 10.1002/ddr.70392 PMC13415181 -o papers/
python scripts/pmc_pdf.py -f dois.txt -o papers/ -j 8 --manifest result.json
python scripts/pmc_pdf.py "Lipid nanoparticle mRNA delivery" -o papers/
```

输入可以是 DOI、PMID、PMCID 或标题。标题会走 Europe PMC 检索，
**匹配到多篇时脚本会报错并列出候选，不会替你猜**。

## 流程

### 1. 归一化到 PMCID

用 Europe PMC REST（比 NCBI E-utilities 快且不需要 API key）：

| 输入 | 查询式 |
|---|---|
| DOI | `DOI:"10.xxxx/..."` |
| PMID | `EXT_ID:<pmid> AND SRC:MED` |
| PMCID | `PMCID:PMCxxxxxxx`（**要校验存在性**，别盲信用户给的号） |
| 标题 | `TITLE:"..." AND OPEN_ACCESS:Y` |

### 2. 定位正文 PDF 的 S3 key

```bash
curl -s "https://pmc-oa-opendata.s3.amazonaws.com/?list-type=2&prefix=PMC13598902.&max-keys=200"
```

**不要硬拼 `PMCID.1.pdf`** —— 修订过的文章是 `.2`/`.3`，要 list 探测。

**不要取目录里第一个 `.pdf`** —— 同一目录混着补充材料：

```
PMC13522490.1/PMC13522490.1.pdf                    ← 正文，要这个
PMC13522490.1/41467_2026_75923_MOESM1_ESM.pdf      ← 补充材料，不要
```

必须精确匹配 `^{PMCID}\.\d+/{PMCID}\.\d+\.pdf$`。

### 3. 下载并校验

前 5 字节必须是 `%PDF-`，否则当失败处理（防止 S3 返回错误 XML 被误判成功）。

## 必须保留的两个防御

**retry**：S3 在并发下偶发慢响应。不加 retry 会把 1.3% 的正常文献误判成"无全文"
（实测 10 并发下 2/150 失败，串行重试立刻 200）。

**精确 key 正则**：见上，否则拿到补充材料 PDF 而不自知。

## 覆盖率与降级

实测（2026-10，三主题各抽 50 篇，Range GET + `%PDF-` 校验）：

| 主题 | S3 有正文 PDF |
|---|---|
| LNP/mRNA | 50/50 = 100% |
| CAR-T | 50/50 = 100% |
| circRNA | 48/50 = 96%* |
| **合计** | **148/150 = 98.7%** |

\* 那 2 篇实际有 PDF，是并发超时误判；加 retry 后为 100%。

降级顺序：

| 情况 | 处理 |
|---|---|
| S3 有正文 PDF（≈99%） | 直接下 |
| 在 PMC 但 S3 无正文 PDF | 取 `fullTextXML` 自行渲染成 PDF，**并告知用户这是重建版** |
| 不在 PMC / 非 OA | 交给别的通道：出版社 TDM 接口 → 机构登录态 |

**本 skill 只交付 PDF，不交付 XML。** XML 只在需要重建 PDF 时作为中间产物。

## 输出

默认落到 `papers/`，文件名 `{PMCID}.pdf`。

`--manifest` 会写 JSON，含每篇的 `status`：`ok` / `no-pdf` / `no-pmcid` / `error`。
退出码只在真正出错（`error`）时为非零；文献不在 OA 子集属于正常结果，不算失败。

## 批量建议

- 并发 `-j 8` 比较稳，再高收益递减且更容易触发超时
- 单篇 2–4 秒，100 篇约 1 分钟
- 不要对同一篇反复重试超过 4 次，S3 的 404 是真的没有

## 自检

```bash
python scripts/selfcheck.py            # 含网络
python scripts/selfcheck.py --offline  # 仅逻辑
```

## 合规

只访问 PMC 官方 Open Access 子集（作者已授权开放获取的内容）。
不绕过付费墙，不访问 Sci-Hub 类站点。下载后请遵守各篇的 CC 许可条款。
