#!/usr/bin/env python3
"""PMC OA PDF downloader.

Downloads full-text PDFs from PubMed Central's official Open Access
subset on AWS S3, bypassing the proof-of-work gate on pmc.ncbi.nlm.nih.gov.

Stdlib only. No browser, no auth, no API key.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BUCKET = "https://pmc-oa-opendata.s3.amazonaws.com"
EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
UA = "pmc-oa-pdf/1.0 (+https://github.com/rcrusoe88-bot/pmc-oa-pdf)"
PDF_MAGIC = b"%PDF-"

# S3 sometimes closes connections under concurrency; without retry ~1.3% of
# articles get misreported as "no PDF" even though the file exists.
RETRIES = 4
TIMEOUT = 60


class ResolveError(Exception):
    """Input could not be mapped to a PMCID."""


def _get(url: str, rng: str | None = None, timeout: int = TIMEOUT) -> bytes:
    headers = {"User-Agent": UA}
    if rng:
        headers["Range"] = f"bytes={rng}"
    last: Exception | None = None
    for i in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001 - transport errors vary
            last = exc
            if i < RETRIES - 1:
                time.sleep(1.5 ** (i + 1))
    raise last  # type: ignore[misc]


def _europepmc_search(query: str, page_size: int = 5) -> list[dict]:
    url = (
        f"{EUROPEPMC}/search?query={urllib.parse.quote(query)}"
        f"&format=json&resultType=lite&pageSize={page_size}"
    )
    return json.loads(_get(url)).get("resultList", {}).get("result", [])


def resolve(identifier: str) -> str:
    """Map a DOI, PMID, PMCID or title to a PMCID.

    Raises ResolveError when nothing matches.
    """
    ident = identifier.strip()
    if not ident:
        raise ResolveError("empty identifier")

    # Already a PMCID. Verify it exists rather than trusting the caller's
    # digits -- a typo'd PMCID would otherwise reach S3 and come back as a
    # confusing "no PDF" instead of "no such article".
    m = re.fullmatch(r"(?:PMC)?(\d{5,9})", ident, re.I)
    if ident.upper().startswith("PMC") and m:
        pmcid = f"PMC{m.group(1)}"
        if not _europepmc_search(f"PMCID:{pmcid}"):
            raise ResolveError(f"{pmcid} not found in Europe PMC")
        return pmcid

    # DOI
    if re.match(r"^10\.\d{4,9}/", ident):
        rows = _europepmc_search(f'DOI:"{ident}"')
        for r in rows:
            if r.get("pmcid"):
                return r["pmcid"]
        raise ResolveError(f"DOI {ident} has no PMCID (not in PMC or not OA)")

    # PMID (bare number, not matched above)
    if re.fullmatch(r"\d{6,9}", ident):
        rows = _europepmc_search(f"EXT_ID:{ident} AND SRC:MED")
        for r in rows:
            if r.get("pmcid"):
                return r["pmcid"]
        raise ResolveError(f"PMID {ident} has no PMCID (not in PMC or not OA)")

    # Title
    rows = _europepmc_search(f'TITLE:"{ident}" AND OPEN_ACCESS:Y', page_size=5)
    hits = [(r["pmcid"], r.get("title", "")) for r in rows if r.get("pmcid")]
    if len(hits) == 1:
        return hits[0][0]
    if not hits:
        raise ResolveError(f"no PMC match for title: {ident[:60]}")
    listing = "\n".join(f"  {p}  {t[:80]}" for p, t in hits)
    raise ResolveError(
        f"title matched {len(hits)} papers, pass an explicit DOI or PMCID:\n{listing}"
    )


def find_pdf_key(pmcid: str) -> str | None:
    """Return the article-body PDF key, or None.

    The bucket directory also holds supplementary PDFs named like
    ``41467_2026_75923_MOESM1_ESM.pdf``; matching ``{PMCID}.{ver}.pdf``
    exactly is what keeps those out of the result.
    """
    url = f"{BUCKET}/?list-type=2&prefix={urllib.parse.quote(pmcid)}.&max-keys=200"
    keys = re.findall(r"<Key>([^<]+)</Key>", _get(url).decode("utf-8", "replace"))
    pat = re.compile(rf"^{re.escape(pmcid)}\.\d+/{re.escape(pmcid)}\.\d+\.pdf$")
    for key in keys:
        if pat.match(key):
            return key
    return None


def download(pmcid: str, outdir: str = "papers") -> str | None:
    """Download one article's PDF. Returns the path, or None if unavailable."""
    key = find_pdf_key(pmcid)
    if key is None:
        return None
    data = _get(f"{BUCKET}/{urllib.parse.quote(key)}")
    if not data.startswith(PDF_MAGIC):
        return None
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, f"{pmcid}.pdf")
    with open(path, "wb") as fh:
        fh.write(data)
    return path


def _one(identifier: str, outdir: str) -> tuple[str, str, str]:
    """Resolve + download one input. Returns (input, status, detail)."""
    try:
        pmcid = resolve(identifier)
    except ResolveError as exc:
        return identifier, "no-pmcid", str(exc)
    except Exception as exc:  # noqa: BLE001
        return identifier, "error", f"resolve failed: {exc}"

    try:
        path = download(pmcid, outdir)
    except Exception as exc:  # noqa: BLE001
        return identifier, "error", f"{pmcid}: {exc}"

    if path is None:
        return identifier, "no-pdf", f"{pmcid}: no body PDF on S3"
    return identifier, "ok", f"{pmcid} -> {path} ({os.path.getsize(path)} bytes)"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Download PMC Open Access full-text PDFs via the S3 open-data bucket."
    )
    ap.add_argument("identifiers", nargs="*", help="DOI, PMID, PMCID or exact title")
    ap.add_argument("-f", "--file", help="read one identifier per line from this file")
    ap.add_argument("-o", "--outdir", default="papers", help="output directory (default: papers)")
    ap.add_argument("-j", "--jobs", type=int, default=4, help="parallel downloads (default: 4)")
    ap.add_argument("--manifest", help="write a JSON result manifest to this path")
    args = ap.parse_args(argv)

    idents = list(args.identifiers)
    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            idents += [ln.strip() for ln in fh if ln.strip()]
    if not idents:
        ap.error("give at least one identifier, or use --file")

    results = []
    with cf.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {pool.submit(_one, i, args.outdir): i for i in idents}
        for fut in cf.as_completed(futures):
            ident, status, detail = fut.result()
            results.append({"input": ident, "status": status, "detail": detail})
            mark = {"ok": "OK  ", "no-pdf": "NOPDF", "no-pmcid": "SKIP", "error": "ERR "}[status]
            print(f"[{mark}] {ident}\n       {detail}", flush=True)

    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\n{ok}/{len(results)} downloaded to {args.outdir}/")
    if args.manifest:
        with open(args.manifest, "w", encoding="utf-8") as fh:
            json.dump({"total": len(results), "ok": ok, "results": results}, fh,
                      ensure_ascii=False, indent=2)

    # Non-zero only when something genuinely broke, not when a paper simply
    # is not in the OA subset (that is a valid, reportable outcome).
    return 1 if any(r["status"] == "error" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
