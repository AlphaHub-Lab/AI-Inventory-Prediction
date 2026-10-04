import pathlib
import re
import sys

issues = []
root = pathlib.Path("app")

for f in root.rglob("*.py"):
    try:
        src = f.read_text(encoding="utf-8", errors="ignore")
        lines = src.splitlines()
    except Exception:
        continue

    for i, line in enumerate(lines, 1):
        lo = line.lower().strip()

        # Hardcoded secrets
        if re.search(r'(secret_key|password|api_key)\s*=\s*["\']', lo) and not lo.startswith("#"):
            issues.append(f"[HARDCODED SECRET?] {f}:{i} -> {line.strip()[:100]}")

        # CORS wildcard
        if "allow_origins" in lo and '["*"]' in line:
            issues.append(f"[CORS WILDCARD] {f}:{i} -> {line.strip()}")

        # Rate limit missing (placeholder - flag any route without rate limit)
        if "@router.post" in lo and "rate_limit" not in src.lower()[:500]:
            issues.append(f"[NO RATE LIMIT on POST?] {f}:{i} -> {line.strip()}")

        # Raw SQL with f-string
        if "text(" in lo and "f'" in line or "text(" in lo and 'f"' in line:
            issues.append(f"[SQLI RISK - f-string in text()] {f}:{i} -> {line.strip()[:100]}")

        # Debug mode / print secrets
        if "print(" in lo and any(k in lo for k in ["token", "password", "secret"]):
            issues.append(f"[DEBUG LEAK?] {f}:{i} -> {line.strip()[:100]}")

    # Check for missing auth dependency
    has_depends = "depends" in src.lower()
    has_router = "@router." in src
    if has_router and not has_depends:
        issues.append(f"[UNPROTECTED ROUTER - no Depends found] {f}")

print("=" * 60)
print("STATIC SECURITY SCAN RESULTS")
print("=" * 60)
if not issues:
    print("No obvious issues found.")
else:
    for iss in issues:
        print(iss)
print(f"\nTotal: {len(issues)} potential issues flagged")
