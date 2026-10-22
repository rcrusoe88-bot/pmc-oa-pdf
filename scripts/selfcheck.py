#!/usr/bin/env python3
"""Self-checks for pmc_pdf. No test framework, no fixtures.

Offline checks always run. Network checks run unless --offline is passed.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import pmc_pdf as m  # noqa: E402


def check_offline() -> None:
    # A bare number is a PMID, not a PMCID. This is why resolve() must not
    # treat "13598902" as a PMCID even though the digits overlap.
    assert re.fullmatch(r"\d{6,9}", "13598902")

    # Body PDF key must match; supplementary PDFs in the same bucket
    # directory must not. This is the guard that stops us shipping SI.
    pat = re.compile(r"^PMC13522490\.\d+/PMC13522490\.\d+\.pdf$")
    assert pat.match("PMC13522490.1/PMC13522490.1.pdf")
    assert not pat.match("PMC13522490.1/41467_2026_75923_MOESM1_ESM.pdf")
    assert not pat.match("PMC13522490.1/PMC13522490.1.txt")
    assert not pat.match("PMC13522490.1/PMC13522490.1.pdf.bak")

    print("offline checks OK")


def check_network() -> None:
    # Known-good articles spanning three topics; all were verified to have
    # a body PDF on S3 when this repo was created.
    cases = ["PMC13338314", "PMC13415181", "PMC13598902"]
    with tempfile.TemporaryDirectory() as tmp:
        for pmcid in cases:
            path = m.download(pmcid, tmp)
            assert path, f"{pmcid}: no PDF"
            with open(path, "rb") as fh:
                assert fh.read(5) == m.PDF_MAGIC, f"{pmcid}: not a PDF"
            assert os.path.getsize(path) > 50_000, f"{pmcid}: suspiciously small"
            print(f"  {pmcid} OK ({os.path.getsize(path):,} bytes)")

        # DOI -> PMCID -> PDF, the path most callers will take
        assert m.resolve("10.1002/ddr.70392") == "PMC13598902"
        print("  DOI resolution OK")

        # A PMCID passthrough must still be verified, not trusted blindly
        assert m.resolve("PMC13598902") == "PMC13598902"
        assert m.resolve("pmc13598902") == "PMC13598902"
        print("  PMCID verification OK")

        # A non-existent PMCID must fail loudly, not silently download junk
        try:
            m.resolve("PMC99999999")
        except m.ResolveError:
            pass
        else:
            raise AssertionError("PMC99999999 should not resolve")

    print("network checks OK")


if __name__ == "__main__":
    check_offline()
    if "--offline" not in sys.argv:
        check_network()
    print("all checks passed")
