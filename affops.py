#!/usr/bin/env python3
"""AffOps CLI — freemium affiliate / content ops toolkit."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from affops_lib import (
    __version__,
    batch_utm_from_csv,
    build_utm_url,
    check_disclosure,
    has_pro,
    validate_affiliate_csv,
    BRAND_PRESETS_FREE,
    BRAND_PRESETS_PRO,
)


def apply_preset(name: str, pro: bool) -> dict:
    presets = BRAND_PRESETS_PRO if pro else BRAND_PRESETS_FREE
    if name not in presets:
        available = ", ".join(sorted(presets))
        raise SystemExit(
            f"Unknown preset {name!r}. Available ({'PRO' if pro else 'free'}): {available}"
            + ("" if pro else " — unlock more with PRO (see PRO.md)")
        )
    return dict(presets[name])


def emit_report(report, fmt: str, pro: bool, out_path: Optional[Path]) -> None:
    if fmt in ("md", "html", "json") and fmt != "text":
        if not pro and out_path:
            print(
                "Report export to file is a PRO feature. Printing text to stdout instead.\n"
                "See PRO.md — set AFFOPS_LICENSE=pro_xxxx",
                file=sys.stderr,
            )
            print(report.to_text())
            return
    if fmt == "json":
        body = report.to_json()
    elif fmt == "md":
        body = report.to_markdown()
    elif fmt == "html":
        body = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>{report.title}</title></head><body>"
            f"<pre>{report.to_text()}</pre></body></html>"
        )
    else:
        body = report.to_text()

    if out_path and pro:
        out_path.write_text(body + "\n", encoding="utf-8")
        print(f"Wrote {out_path}", file=sys.stderr)
    else:
        print(body)


def cmd_utm(args: argparse.Namespace) -> int:
    pro = has_pro(args.license)
    preset = apply_preset(args.preset, pro) if args.preset else {}
    source = args.source or preset.get("utm_source")
    medium = args.medium or preset.get("utm_medium")
    campaign = args.campaign or preset.get("utm_campaign")
    content = args.content or preset.get("utm_content")
    term = args.term or preset.get("utm_term")

    try:
        result = build_utm_url(
            args.url,
            source=source,
            medium=medium,
            campaign=campaign,
            content=content,
            term=term,
            overwrite=args.overwrite,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(result)
    return 0


def cmd_disclosure(args: argparse.Namespace) -> int:
    pro = has_pro(args.license)
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.text:
        text = args.text
    else:
        text = sys.stdin.read()

    phrases = None
    if args.rules:
        if not pro:
            print(
                "Custom rule packs require PRO. Using built-in phrases.\n"
                "See PRO.md",
                file=sys.stderr,
            )
        else:
            phrases = [
                line.strip()
                for line in Path(args.rules).read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]

    report = check_disclosure(text, phrases)
    emit_report(report, args.format, pro, Path(args.out) if args.out else None)
    return 0 if report.ok else 1


def cmd_validate(args: argparse.Namespace) -> int:
    pro = has_pro(args.license)
    report = validate_affiliate_csv(Path(args.csv), pro=pro)
    emit_report(report, args.format, pro, Path(args.out) if args.out else None)
    return 0 if report.ok else 1


def cmd_batch(args: argparse.Namespace) -> int:
    pro = has_pro(args.license)
    report, urls = batch_utm_from_csv(Path(args.csv), pro=pro, overwrite=args.overwrite)
    emit_report(report, args.format, pro, Path(args.out) if args.out else None)
    if urls and args.print_urls:
        print("---")
        for u in urls:
            print(u)
    return 0 if report.ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="affops",
        description="AffOps — UTM builder + affiliate disclosure / CSV checks (freemium MIT).",
    )
    p.add_argument("--version", action="version", version=f"affops {__version__}")
    p.add_argument(
        "--license",
        default=None,
        help="PRO license key (or set AFFOPS_LICENSE). Placeholder: pro_********",
    )

    sub = p.add_subparsers(dest="command", required=True)

    utm = sub.add_parser("utm", help="Build a single UTM-tagged URL")
    utm.add_argument("url", help="Base URL")
    utm.add_argument("--source", "-s")
    utm.add_argument("--medium", "-m")
    utm.add_argument("--campaign", "-c")
    utm.add_argument("--content")
    utm.add_argument("--term")
    utm.add_argument("--preset", help="Brand preset (free: generic, newsletter)")
    utm.add_argument("--overwrite", action="store_true", help="Replace existing utm_* params")
    utm.set_defaults(func=cmd_utm)

    disc = sub.add_parser("disclosure", help="Scan text for affiliate disclosure phrases")
    disc.add_argument("--file", "-f", help="Path to markdown/HTML/text")
    disc.add_argument("--text", "-t", help="Inline text to scan")
    disc.add_argument("--rules", help="PRO: path to custom regex phrases (one per line)")
    disc.add_argument("--format", choices=("text", "md", "json", "html"), default="text")
    disc.add_argument("--out", help="PRO: write report to file")
    disc.set_defaults(func=cmd_disclosure)

    val = sub.add_parser("validate", help="Validate an affiliate link spreadsheet (CSV)")
    val.add_argument("csv", help="CSV with at least url,name columns")
    val.add_argument("--format", choices=("text", "md", "json", "html"), default="text")
    val.add_argument("--out", help="PRO: write report to file")
    val.set_defaults(func=cmd_validate)

    batch = sub.add_parser("batch", help="Batch-build UTM URLs from CSV (free: 10 rows)")
    batch.add_argument("csv", help="CSV with url + optional utm_* columns")
    batch.add_argument("--overwrite", action="store_true")
    batch.add_argument("--print-urls", action="store_true", help="Print built URLs after report")
    batch.add_argument("--format", choices=("text", "md", "json", "html"), default="text")
    batch.add_argument("--out", help="PRO: write report to file")
    batch.set_defaults(func=cmd_batch)

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
