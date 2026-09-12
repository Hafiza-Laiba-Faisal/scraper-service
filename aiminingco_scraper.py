"""
Scraper Service ka use karke https://www.aiminingco.com/for/stable-diffusion
aur uske saare links ko scrape karna
"""
import sys, os, json, asyncio, httpx
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from core.fetcher.escalating_fetcher import EscalatingFetcher
from core.parser.bs4_parser import BS4Parser
from core.extractor.metadata_extractor import DefaultMetadataExtractor
from core.extractor.links_extractor import DefaultLinksExtractor
from core.fetcher import client as global_client


class SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return str(obj)
        except:
            return None


async def scrape_page(fetcher, parser, meta_ext, links_ext, url):
    result = await fetcher.get(url, timeout=30)
    if not result.ok:
        return {"url": url, "error": f"HTTP {result.status_code}"}
    html = result.text
    final_url = result.final_url or url
    tree = parser.parse(html)
    metadata = meta_ext.extract(tree, final_url)
    links_data = links_ext.extract(tree, final_url)
    return {
        "url": final_url,
        "status": result.status_code,
        "title": metadata.get("title", ""),
        "description": metadata.get("description", ""),
        "html_length": len(html),
        "links_count": links_data["count"],
        "links": links_data["links"],
    }


async def main():
    print("=" * 60)
    print("SCRAPER SERVICE - AIMININGCO.COM")
    print("=" * 60)

    # Init async client
    limits = httpx.Limits(max_connections=200, max_keepalive_connections=50)
    global_client.async_client = httpx.AsyncClient(http2=False, limits=limits, follow_redirects=True, timeout=30)

    fetcher = EscalatingFetcher()
    parser = BS4Parser()
    meta_ext = DefaultMetadataExtractor()
    links_ext = DefaultLinksExtractor()

    # Step 1: Scrape main page
    print("\n[1/2] Scraping main page...")
    main_data = await scrape_page(fetcher, parser, meta_ext, links_ext,
                                   "https://www.aiminingco.com/for/stable-diffusion")
    print(f"  Title: {main_data['title']}")
    print(f"  Links found: {main_data['links_count']}")

    # Step 2: Filter links
    gpu_links = []
    provider_links = []
    other_links = []
    for link in main_data["links"]:
        href = link.get("url", "")
        if not href or href.startswith("#"):
            continue
        if "/gpu/" in href and "/for/stable-diffusion" in href:
            gpu_links.append(href)
        elif "/provider/" in href and "/for/stable-diffusion" in href:
            provider_links.append(href)
        elif href.startswith("http") and "aiminingco.com" in href:
            other_links.append(href)

    gpu_links = list(dict.fromkeys(gpu_links))
    provider_links = list(dict.fromkeys(provider_links))
    other_links = list(dict.fromkeys(other_links))

    print(f"  GPU links: {len(gpu_links)}")
    print(f"  Provider links: {len(provider_links)}")
    print(f"  Other links: {len(other_links)}")

    # Step 3: Scrape all GPU pages
    print(f"\n[2/2] Scraping {len(gpu_links)} GPU pages...")
    gpu_results = []
    for i, url in enumerate(gpu_links):
        print(f"  [{i+1}/{len(gpu_links)}] Scraping...")
        data = await scrape_page(fetcher, parser, meta_ext, links_ext, url)
        gpu_results.append(data)
        await asyncio.sleep(0.3)

    # Save everything
    output_dir = os.path.join(os.path.dirname(__file__), "aiminingco_data_v2")
    os.makedirs(output_dir, exist_ok=True)

    # Save main page JSON
    with open(os.path.join(output_dir, "main_page.json"), "w", encoding="utf-8") as f:
        json.dump(main_data, f, indent=2, ensure_ascii=False, cls=SafeEncoder)

    # Save GPU pages JSON
    with open(os.path.join(output_dir, "gpu_pages.json"), "w", encoding="utf-8") as f:
        json.dump(gpu_results, f, indent=2, ensure_ascii=False, cls=SafeEncoder)

    # Save summary
    with open(os.path.join(output_dir, "summary.txt"), "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("AIMININGCO.COM - STABLE DIFFUSION SCRAPE REPORT\n")
        f.write(f"Scraped using Scraper Service\n")
        f.write("=" * 70 + "\n\n")

        f.write(f"MAIN PAGE: {main_data['url']}\n")
        f.write(f"Title: {main_data['title']}\n")
        f.write(f"Description: {main_data['description'][:300]}\n\n")

        f.write(f"GPU PAGES SCRAPED: {len(gpu_links)}\n")
        f.write("-" * 70 + "\n")
        for data in gpu_results:
            title = data.get("title", "N/A")[:100]
            f.write(f"  GPU: {title}\n")
            if "error" in data:
                f.write(f"  ERROR: {data['error']}\n")
            else:
                f.write(f"  HTML: {data['html_length']:,} bytes | Links: {data.get('links_count', 0)}\n")
            f.write("\n")

        f.write(f"\nPROVIDER LINKS ({len(provider_links)}):\n")
        for url in provider_links:
            f.write(f"  - {url}\n")

        f.write(f"\nOTHER AIMINGCO LINKS ({len(other_links)}):\n")
        for url in other_links:
            f.write(f"  - {url}\n")

        f.write(f"\n\nALL RAW LINKS FROM MAIN PAGE ({main_data['links_count']}):\n")
        f.write("-" * 70 + "\n")
        for link in main_data["links"]:
            f.write(f"  {link.get('url',''):80s} | {link.get('text','')[:60]}\n")

    print(f"\n✓ Data saved to: {output_dir}/")
    print(f"  - main_page.json")
    print(f"  - gpu_pages.json")
    print(f"  - summary.txt")

    if global_client.async_client:
        await global_client.async_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
