#!/usr/bin/env python3
"""Browser smoke test + screenshots of the running app.

Usage: python scripts/browser_smoke.py [--url http://127.0.0.1:5173] [--out docs/screenshots]
Works against the dev server (API on :8000) or a static build. Exits 1 on console errors,
failed API calls, missing core states, horizontal overflow on mobile, or a keyboard-only failure.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


def chromium_path() -> str | None:
    cands = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome")))
    return cands[-1] if cands else None


def watch(page: Page, errors: list[str], failed: list[str]) -> None:
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("response", lambda r: failed.append(f"{r.status} {r.url}") if "/api/" in r.url and r.status >= 400 else None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:5173")
    ap.add_argument("--out", default="docs/screenshots")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    failed: list[str] = []
    res: dict[str, object] = {}
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            browser = p.chromium.launch(executable_path=chromium_path())
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        watch(page, errors, failed)
        page.goto(a.url)
        page.wait_for_selector(".guide[open]", timeout=30000)
        page.screenshot(path=str(out / "00_guide.png"))
        page.get_by_role("button", name="Start planning").click()
        page.wait_for_selector(".rail-n.done", timeout=120000)  # routes computed
        page.wait_for_timeout(800)
        page.screenshot(path=str(out / "01_plan_overview.png"))

        page.get_by_role("button", name="See routes").click()
        page.get_by_role("radio", name="Slope", exact=True).click()
        page.wait_for_timeout(700)
        page.screenshot(path=str(out / "02_slope_layer.png"))
        page.get_by_role("radio", name="Geology", exact=True).click()
        page.wait_for_timeout(700)
        page.locator(".map-wrap").screenshot(path=str(out / "03_geology_layer.png"))
        page.get_by_role("radio", name="Photo", exact=True).click()
        page.screenshot(path=str(out / "04_route_comparison.png"))

        page.get_by_role("button", name="Next: Feasibility").click()
        page.wait_for_selector(".verdict")
        res["feasibility"] = page.locator(".verdict .status").first.inner_text()
        page.screenshot(path=str(out / "05_feasibility.png"))

        page.get_by_role("button", name="Next: Contingency").click()
        page.get_by_role("button", name="Run scenario").click()
        page.wait_for_selector(".result .change", timeout=60000)
        page.wait_for_timeout(500)
        res["contingency_detour"] = page.locator(".result .change").inner_text().replace("\n", " ")
        page.screenshot(path=str(out / "06_contingency_replan.png"))

        # honest failure: zone placed on the habitat
        page.get_by_role("button", name="Place the zone on the map instead").click()
        hab = page.locator(".pin-hab").bounding_box()
        assert hab, "habitat marker not found"
        page.mouse.click(hab["x"] + hab["width"] / 2, hab["y"] + hab["height"] / 2)
        page.get_by_label("Blocked zone radius", exact=True).fill("200")
        page.get_by_role("button", name="Run scenario").click()
        page.wait_for_function("document.querySelector('.result .change')?.innerText.includes('Infeasible')", timeout=60000)
        page.wait_for_timeout(500)
        res["contingency_enclosed"] = page.locator(".result .change").inner_text().replace("\n", " ")
        res["enclosed_reasons"] = page.locator(".result .reasons").inner_text().replace("\n", " ")
        page.screenshot(path=str(out / "07_no_feasible_return.png"))

        page.get_by_role("button", name="Next: Evidence").click()
        page.get_by_role("tab", name="Rover photos").click()
        page.wait_for_timeout(1200)
        page.screenshot(path=str(out / "08_rover_photos.png"))
        page.get_by_role("tab", name="Weather history").click()
        page.wait_for_timeout(400)
        page.screenshot(path=str(out / "09_weather_history.png"))
        page.get_by_role("tab", name="Data sources").click()
        page.wait_for_timeout(400)
        page.screenshot(path=str(out / "10_data_sources.png"))

        # keyboard-only pass on a fresh page: dismiss guide with Enter, reach "See routes" with Tab, activate with Enter
        kb = browser.new_page(viewport={"width": 1440, "height": 900})
        watch(kb, errors, failed)
        kb.goto(a.url)
        kb.wait_for_selector(".guide[open]")
        kb.keyboard.press("Enter")  # focus starts on "Start planning"
        kb.wait_for_selector(".rail-n.done", timeout=120000)
        reached = False
        for _ in range(40):  # Tab to the "Skip to step actions" link, then Enter moves focus to the primary action
            kb.keyboard.press("Tab")
            if kb.evaluate("document.activeElement?.textContent?.includes('Skip to step actions')"):
                kb.keyboard.press("Enter")
                break
        reached = bool(kb.evaluate("document.activeElement?.textContent?.includes('See routes')"))
        if reached:
            kb.keyboard.press("Enter")
            kb.wait_for_selector(".route-card", timeout=10000)
        res["keyboard_only_reaches_routes"] = reached

        # second planning area, opened via a shareable ?area= link
        rim = browser.new_page(viewport={"width": 1440, "height": 900})
        watch(rim, errors, failed)
        rim.goto(a.url.rstrip("/") + "/?area=jezero-crater-rim-v1")
        rim.wait_for_selector(".guide[open]")
        rim.get_by_role("button", name="Start planning").click()
        rim.wait_for_selector(".rail-n.done", timeout=120000)
        rim.wait_for_timeout(2500)
        res["rim_area_active"] = rim.locator(".area-switch button.on").inner_text()
        res["rim_feasibility"] = rim.locator(".rail-s").nth(2).inner_text()
        rim.screenshot(path=str(out / "12_crater_rim.png"))

        m = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        watch(m, errors, failed)
        m.goto(a.url)
        m.wait_for_selector(".guide[open]")
        m.get_by_role("button", name="Start planning").click()
        m.wait_for_selector(".rail-n.done", timeout=120000)
        m.wait_for_timeout(800)
        res["mobile_horizontal_overflow_px"] = m.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        m.screenshot(path=str(out / "11_mobile.png"))
        browser.close()
    res["console_errors"] = errors
    res["failed_api_calls"] = failed
    print(json.dumps(res, indent=2))
    ok = (
        res.get("feasibility", "") != ""
        and "Infeasible" in str(res.get("contingency_enclosed"))
        and "NO_ROUTE" in str(res.get("enclosed_reasons"))
        and res["keyboard_only_reaches_routes"] is True
        and res.get("rim_area_active") == "Crater rim" and "margin" in str(res.get("rim_feasibility"))
        and res["mobile_horizontal_overflow_px"] == 0
        and not errors
        and not failed
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
