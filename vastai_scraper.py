"""
Use Playwright (via Scraper Service) to render Vast.ai and extract content
"""
import sys, os, json, asyncio
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from playwright.async_api import async_playwright

BROWSER_PATH = os.path.expanduser("~/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome")

async def main():
    print("Launching Playwright browser...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=BROWSER_PATH,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        
        url = "https://cloud.vast.ai/"
        print(f"Navigating to: {url}")
        # Use domcontentloaded instead of networkidle to avoid timeout
        await page.goto(url, wait_until="domcontentloaded", timeout=120000)
        # Give it extra time for JS to render
        await page.wait_for_timeout(8000)
        
        title = await page.title()
        print(f"\nTitle: {title}")
        
        # Get full page text
        text = await page.inner_text("body")
        print(f"\nBODY TEXT (first 3000 chars):\n{text[:3000]}")
        
        # Get all visible links
        links = await page.evaluate("""
            () => Array.from(document.querySelectorAll('a')).map(a => ({
                href: a.href,
                text: a.innerText.trim().slice(0, 100),
                visible: a.offsetParent !== null
            }))
        """)
        print(f"\n=== LINKS ({len(links)}) ===")
        for l in links[:30]:
            if l['text'] or l['href']:
                print(f"  {l['href'][:90]}  [{l['text'][:60]}]")
        
        # Get page HTML
        html = await page.content()
        print(f"\nHTML length: {len(html)}")
        
        # Save
        output_dir = os.path.join(os.path.dirname(__file__), "aiminingco_data_v2")
        with open(os.path.join(output_dir, "vastai_content.txt"), "w", encoding="utf-8") as f:
            f.write(f"TITLE: {title}\n\n")
            f.write(f"=== BODY TEXT ===\n{text}\n\n")
            f.write(f"=== ALL LINKS ===\n")
            for l in links:
                if l['text'] or l['href']:
                    f.write(f"{l['href']} | {l['text']}\n")
        
        print(f"\n✓ Saved to: {output_dir}/vastai_content.txt")
        await browser.close()

asyncio.run(main())
