"""AffOps core — UTM, disclosure, CSV validation (stdlib only)."""
from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

__version__ = "0.1.0"

# Free tier batch limit (PRO = unlimited)
FREE_BATCH_LIMIT = 10

# Built-in disclosure phrases (FTC-ish / common affiliate language)
DEFAULT_DISCLOSURE_PHRASES = [
    r"affiliate\s+link",
    r"affiliate\s+disclosure",
    r"as\s+an\s+amazon\s+associate",
    r"i\s+(may\s+)?earn\s+(a\s+)?commission",
    r"we\s+(may\s+)?earn\s+(a\s+)?commission",
    r"compensated\s+affiliate",
    r"paid\s+partnership",
    r"#ad\b",
    r"#affiliate\b",
    r"disclosure\s*:",
]

REQUIRED_CSV_COLUMNS = {"url", "name"}
OPTIONAL_CSV_COLUMNS = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "network", "notes"}

BRAND_PRESETS_FREE = {
    "generic": {"utm_source": "blog", "utm_medium": "affiliate"},
    "newsletter": {"utm_source": "newsletter", "utm_medium": "email"},
}

BRAND_PRESETS_PRO = {
    **BRAND_PRESETS_FREE,
    "amazon": {"utm_source": "amazon", "utm_medium": "affiliate", "utm_campaign": "product"},
    "shareasale": {"utm_source": "shareasale", "utm_medium": "affiliate"},
    "impact": {"utm_source": "impact", "utm_medium": "affiliate"},
    "cj": {"utm_source": "cj", "utm_medium": "affiliate"},
    "partnerize": {"utm_source": "partnerize", "utm_medium": "affiliate"},
}


@dataclass
class Finding:
    level: str  # ok | warn | error
    message: str
    context: str = ""


@dataclass
class Report:
    title: str
    findings: List[Finding] = field(default_factory=list)

    def add(self, level: str, message: str, context: str = "") -> None:
        self.findings.append(Finding(level, message, context))

    @property
    def ok(self) -> bool:
        return not any(f.level == "error" for f in self.findings)

    def to_text(self) -> str:
        lines = [f"## {self.title}", ""]
        if not self.findings:
            lines.append("No findings.")
            return "\n".join(lines)
        for f in self.findings:
            prefix = {"ok": "[OK]", "warn": "[WARN]", "error": "[ERROR]"}.get(f.level, "[?]")
            ctx = f" — {f.context}" if f.context else ""
            lines.append(f"{prefix} {f.message}{ctx}")
        return "\n".join(lines)

    def to_markdown(self) -> str:
        lines = [f"# {self.title}", "", "| Level | Message | Context |", "|-------|---------|--------|"]
        for f in self.findings:
            ctx = f.context.replace("|", "\\|")
            msg = f.message.replace("|", "\\|")
            lines.append(f"| {f.level} | {msg} | {ctx} |")
        if not self.findings:
            lines.append("| ok | No findings | |")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(
            {
                "title": self.title,
                "ok": self.ok,
                "findings": [
                    {"level": f.level, "message": f.message, "context": f.context}
                    for f in self.findings
                ],
            },
            indent=2,
        )


def has_pro(license_key: Optional[str]) -> bool:
    """PRO unlock: AFFOPS_LICENSE or --license starting with 'pro_' (placeholder until Stripe)."""
    key = (license_key or os.environ.get("AFFOPS_LICENSE") or "").strip()
    if not key:
        return False
    # Placeholder validator — real Stripe-backed keys later
    return key.lower().startswith("pro_") and len(key) >= 8


def build_utm_url(
    url: str,
    source: Optional[str] = None,
    medium: Optional[str] = None,
    campaign: Optional[str] = None,
    content: Optional[str] = None,
    term: Optional[str] = None,
    overwrite: bool = False,
) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL (need scheme + host): {url!r}")

    qs = parse_qs(parsed.query, keep_blank_values=True)
    updates = {
        "utm_source": source,
        "utm_medium": medium,
        "utm_campaign": campaign,
        "utm_content": content,
        "utm_term": term,
    }
    for key, value in updates.items():
        if value is None or value == "":
            continue
        if key in qs and not overwrite:
            continue
        qs[key] = [value]

    flat = []
    for k, vals in qs.items():
        for v in vals:
            flat.append((k, v))
    new_query = urlencode(flat, doseq=False)
    return urlunparse(parsed._replace(query=new_query))


def check_disclosure(text: str, phrases: Optional[Sequence[str]] = None) -> Report:
    report = Report("Disclosure check")
    body = text or ""
    if not body.strip():
        report.add("error", "Empty content — nothing to check")
        return report

    patterns = phrases or DEFAULT_DISCLOSURE_PHRASES
    matched = []
    for pat in patterns:
        if re.search(pat, body, flags=re.IGNORECASE):
            matched.append(pat)

    affiliatey = re.findall(
        r"https?://[^\s)\"']+(?:tag=|ascsubtag=|ref=|aff(?:iliate)?id=|clickid=)[^\s)\"']*",
        body,
        flags=re.IGNORECASE,
    )

    if matched:
        report.add("ok", f"Found {len(matched)} disclosure pattern(s)", ", ".join(matched[:5]))
    else:
        level = "error" if affiliatey else "warn"
        msg = (
            "No disclosure phrases found near affiliate-style links"
            if affiliatey
            else "No disclosure phrases found (add one if you use affiliate links)"
        )
        report.add(level, msg)

    if affiliatey:
        report.add("warn", f"Detected {len(affiliatey)} possible affiliate URL(s)", affiliatey[0][:80])
    else:
        report.add("ok", "No obvious affiliate tracking params in URLs")

    if matched and len(body) > 200:
        first_hit = min(
            (m.start() for pat in matched for m in [re.search(pat, body, re.I)] if m),
            default=None,
        )
        if first_hit is not None and first_hit > len(body) * 0.6:
            report.add("warn", "Disclosure appears late in the content — prefer near the top")

    return report


def validate_affiliate_csv(path: Path, pro: bool = False) -> Report:
    report = Report(f"CSV validator: {path.name}")
    if not path.exists():
        report.add("error", f"File not found: {path}")
        return report

    try:
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames:
                report.add("error", "CSV has no header row")
                return report
            fields = {f.strip().lower() for f in reader.fieldnames}
            missing = REQUIRED_CSV_COLUMNS - fields
            if missing:
                report.add("error", f"Missing required columns: {', '.join(sorted(missing))}")
            else:
                report.add("ok", "Required columns present (url, name)")

            extra_known = fields & OPTIONAL_CSV_COLUMNS
            if extra_known:
                report.add("ok", f"Optional columns: {', '.join(sorted(extra_known))}")

            rows = list(reader)
            if not rows:
                report.add("error", "CSV has no data rows")
                return report

            if not pro and len(rows) > FREE_BATCH_LIMIT:
                report.add(
                    "warn",
                    f"Free tier validates first {FREE_BATCH_LIMIT} of {len(rows)} rows "
                    f"(PRO unlocks unlimited — see PRO.md)",
                )
                rows = rows[:FREE_BATCH_LIMIT]

            for i, row in enumerate(rows, start=2):
                norm = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
                url = norm.get("url", "")
                name = norm.get("name", "")
                if not name:
                    report.add("error", f"Row {i}: empty name")
                if not url:
                    report.add("error", f"Row {i}: empty url")
                    continue
                try:
                    parsed = urlparse(url)
                    if parsed.scheme not in ("http", "https") or not parsed.netloc:
                        report.add("error", f"Row {i}: invalid url", url[:100])
                    else:
                        qs = parse_qs(parsed.query)
                        has_utm = any(k.startswith("utm_") for k in qs)
                        if not has_utm and not any(norm.get(c) for c in ("utm_source", "utm_medium", "utm_campaign")):
                            msg = f"Row {i}: no UTM params"
                            if pro:
                                report.add("warn", msg + " — PRO would suggest defaults", name)
                            else:
                                report.add("warn", msg, name)
                except Exception as exc:  # noqa: BLE001
                    report.add("error", f"Row {i}: {exc}")

    except UnicodeDecodeError:
        report.add("error", "File is not valid UTF-8")
    except csv.Error as exc:
        report.add("error", f"CSV parse error: {exc}")

    return report


def batch_utm_from_csv(path: Path, pro: bool, overwrite: bool = False) -> Tuple[Report, List[str]]:
    report = Report(f"Batch UTM: {path.name}")
    urls: List[str] = []
    if not path.exists():
        report.add("error", f"File not found: {path}")
        return report, urls

    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            report.add("error", "CSV has no header")
            return report, urls
        rows = list(reader)

    if not pro and len(rows) > FREE_BATCH_LIMIT:
        report.add(
            "error",
            f"Free tier limited to {FREE_BATCH_LIMIT} rows ({len(rows)} provided). "
            "Sponsor PRO ($15/mo) or trim the CSV — see PRO.md",
        )
        return report, urls

    for i, row in enumerate(rows, start=2):
        norm = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        url = norm.get("url", "")
        if not url:
            report.add("error", f"Row {i}: missing url")
            continue
        try:
            built = build_utm_url(
                url,
                source=norm.get("utm_source") or None,
                medium=norm.get("utm_medium") or None,
                campaign=norm.get("utm_campaign") or None,
                content=norm.get("utm_content") or None,
                term=norm.get("utm_term") or None,
                overwrite=overwrite,
            )
            urls.append(built)
            report.add("ok", f"Row {i}: built", built[:120])
        except ValueError as exc:
            report.add("error", f"Row {i}: {exc}")

    return report, urls
