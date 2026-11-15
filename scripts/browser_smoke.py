#!/usr/bin/env python3
"""Browser smoke test + screenshots of the running app (needs API on :8000 and Vite on :5173).

Usage: python scripts/browser_smoke.py [--url http://127.0.0.1:5173] [--out docs/screenshots]
Fails (exit 1) on console errors, failed API calls or missing core UI states.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def chromium_path() -> str | None:
    cands = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome")))
    return cands[-1] if cands else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:5173")
    ap.add_argument("--out", default="docs/screenshots")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    failed: list[str] = []
    results: dict[str, object] = {}
    with sync_playwright() as p:
        kw = {}
        try:
            browser = p.chromium.launch()
        except Exception:
            kw["executable_path"] = chromium_path()
            browser = p.chromium.launch(**kw)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("response", lambda r: failed.append(f"{r.status} {r.url}") if "/api/" in r.url and r.status >= 400 else None)
        page.goto(a.url)
        page.wait_for_selector(".status-row .status", timeout=30000)
        page.wait_for_timeout(1500)
        results["guardian_status"] = page.locator(".status-row .status").first.inner_text()
        page.screenshot(path=str(out / "01_plan_overview.png"), full_page=False)

        # Slope + geology layers
        page.get_by_label("Slope (derived from DTM)", exact=False).first.check()
        page.wait_for_timeout(800)
        page.locator(".map-wrap").screenshot(path=str(out / "02_slope_layer.png"))
        page.get_by_label("Slope (derived from DTM)", exact=False).first.uncheck()
        page.get_by_label("Geologic units (USGS SIM 3464)", exact=False).first.check()
        page.wait_for_timeout(800)
        page.locator(".map-wrap").screenshot(path=str(out / "03_geology_layer.png"))
        page.get_by_label("Geologic units (USGS SIM 3464)", exact=False).first.uncheck()

        # Route comparison panel
        page.locator("section[aria-labelledby='routes-h']").screenshot(path=str(out / "04_route_comparison.png"))

        # Contingency
        page.get_by_role("button", name="Inject blocked zone and replan").click()
        page.wait_for_selector(".status-change", timeout=30000)
        page.wait_for_timeout(1000)
        results["contingency"] = page.locator(".status-change").inner_text()
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)
        page.screenshot(path=str(out / "05_contingency_replan.png"), full_page=False)
        page.locator("section[aria-labelledby='contingency-h']").screenshot(path=str(out / "06_contingency_panel.png"))

        # Evidence tabs
        page.get_by_role("tab", name="Rover photos").click()
        page.wait_for_timeout(1500)
        page.locator("section[aria-labelledby='evidence-h']").screenshot(path=str(out / "07_rover_photos.png"))
        page.get_by_role("tab", name="Atmosphere (history)").click()
        page.wait_for_timeout(500)
        page.locator("section[aria-labelledby='evidence-h']").screenshot(path=str(out / "08_meda_history.png"))
        page.get_by_role("tab", name="Sources & alignment").click()
        page.wait_for_timeout(500)
        page.locator("section[aria-labelledby='evidence-h']").screenshot(path=str(out / "09_sources_alignment.png"))

        # Mobile layout
        m = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        m.on("pageerror", lambda e: errors.append(str(e)))
        m.goto(a.url)
        m.wait_for_selector(".status-row .status", timeout=30000)
        m.wait_for_timeout(1200)
        overflow = m.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        results["mobile_horizontal_overflow_px"] = overflow
        m.screenshot(path=str(out / "10_mobile.png"))
        browser.close()
    results["console_errors"] = errors
    results["failed_api_calls"] = failed
    print(json.dumps(results, indent=2))
    status_ok = any(s in str(results.get("guardian_status", "")) for s in ("FEASIBLE", "INFEASIBLE", "UNKNOWN"))
    ok = status_ok and not errors and not failed and "Status change" in str(results.get("contingency", "")) and results["mobile_horizontal_overflow_px"] == 0
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
