# AffOps

[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%9D%A4-pink?logo=github)](https://github.com/sponsors/dmarzejon)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![PRO $15/mo](https://img.shields.io/badge/PRO-%2415%2Fmo-blue)](./PRO.md)

**UTM link builder + affiliate disclosure checker + spreadsheet validator** for content / affiliate operators.

Free core is MIT forever. Unlock batch / custom rules / report export with [PRO ($15/mo)](./PRO.md) via [GitHub Sponsors](https://github.com/sponsors/dmarzejon).

## Why

Shipping affiliate posts without consistent UTMs or a clear disclosure is how campaigns go dark — and how FTC headaches start. AffOps is a tiny local CLI (and single-file web UI) that:

1. **Builds** clean `utm_*` URLs (with free brand presets)
2. **Scans** draft copy for disclosure phrases near affiliate-style links
3. **Validates** your affiliate link CSV before it hits the CMS

No account. No phone-home. Runs offline.

## Quick start (CLI)

```bash
# requires Python 3.9+ (stdlib only — no pip install)
python3 affops.py utm "https://example.com/deal" \
  --source blog --medium affiliate --campaign spring

python3 affops.py disclosure --file examples/post.md

python3 affops.py validate examples/links.csv

python3 affops.py batch examples/links.csv --print-urls
```

### Examples

| Command | What it does |
|---------|----------------|
| `utm` | Append / merge UTM params on one URL |
| `disclosure` | Regex-scan text for FTC-ish disclosure language |
| `validate` | Check CSV has `url`,`name` + sensible UTMs |
| `batch` | Build many UTM URLs from CSV (free: 10 rows) |

## Web UI (no install)

Open [`web/index.html`](./web/index.html) in any browser — single-file HTML+JS, same free features (UTM builder + disclosure check). Great for quick paste jobs.

## Free vs PRO

| | Free (MIT) | [PRO $15/mo](./PRO.md) |
|--|------------|-------------------------|
| Single UTM build | ✅ | ✅ |
| Disclosure scan (built-in pack) | ✅ | ✅ |
| CSV validate | ✅ (first 10 rows) | Unlimited |
| Batch UTM | 10 rows | Unlimited |
| Custom disclosure rule packs | — | ✅ |
| Report export (MD/HTML/JSON) | stdout | ✅ files |
| Brand presets | 2 | Full library |

Sponsor tiers ($5 / $15 / $49): [sponsors-tiers.md](./sponsors-tiers.md)

```bash
export AFFOPS_LICENSE=pro_yourkey   # placeholder until Stripe
python3 affops.py batch big.csv --format md --out report.md
```

## Sponsors

[![Sponsor dmarzejon](https://img.shields.io/badge/GitHub%20Sponsors-dmarzejon-ea4aaa?logo=githubsponsors)](https://github.com/sponsors/dmarzejon)

Funding config: [`.github/FUNDING.yml`](./.github/FUNDING.yml)

## License

[MIT](./LICENSE) © 2026 Diego Marzejon

Free core stays open. PRO is additive licensing on top — see [PRO.md](./PRO.md). Stripe checkout for non-GitHub licenses is on the roadmap.
