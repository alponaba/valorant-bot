from pathlib import Path

root = Path(__file__).resolve().parent
checks = {
    "base template": root / "templates/base.html",
    "home template": root / "templates/index.html",
    "commands template": root / "templates/commands.html",
    "privacy template": root / "templates/privacy.html",
    "status template": root / "templates/status.html",
    "site css": root / "static/css/site.css",
    "site js": root / "static/js/site.js",
    "OG image": root / "static/img/og-vtracker.png",
    "favicon": root / "static/img/vtracker-mark.svg",
}
missing = [name for name, path in checks.items() if not path.exists()]
base = checks["base template"].read_text(encoding="utf-8") if checks["base template"].exists() else ""
required = ["canonical", "og:title", "og:image", "application/ld+json", "google-site-verification"]
missing_meta = [token for token in required if token not in base]
if missing or missing_meta:
    print("SEO PREFLIGHT FAILED")
    if missing: print("Missing files:", ", ".join(missing))
    if missing_meta: print("Missing metadata:", ", ".join(missing_meta))
    raise SystemExit(1)
print("SEO PREFLIGHT OK")
print(f"Checked {len(checks)} website assets and {len(required)} metadata hooks.")
