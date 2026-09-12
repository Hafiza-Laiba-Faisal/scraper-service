"""
Extract actual text content from scraped GPU pages - fixed for Next.js rendering
"""
import sys, os, json, asyncio, re
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from core.fetcher.escalating_fetcher import EscalatingFetcher
from core.parser.bs4_parser import BS4Parser
from core.fetcher import client as global_client
import httpx


def extract_gpu_data(soup, url):
    text = soup.get_text(separator=' ', strip=True)
    
    data = {"url": url, "raw_text_snippet": text[:500]}
    
    # Fit score - e.g. "Fit Score 65 /100" or "Fit Score 100 /100"
    m = re.search(r'Fit Score\s*(\d+)\s*/\s*100', text)
    data['fit_score'] = m.group(1) + '/100' if m else ''
    
    # Fit level
    m = re.search(r'(Excellent fit|Good fit|Adequate fit)', text)
    data['fit_level'] = m.group(1) if m else ''
    
    # Hourly rate - e.g. "$ 0.11" or "$0.11"
    m = re.search(r'Hourly Rate\s*\$?\s*([\d.]+)', text)
    data['price_per_hr'] = '$' + m.group(1) + '/hr' if m else ''
    
    # VRAM - e.g. "40 / 8 GB"
    m = re.search(r'VRAM vs Required\s*(\d+)\s*/\s*(\d+)\s*GB', text)
    if m:
        data['vram'] = m.group(1) + ' GB'
        data['vram_min'] = m.group(2) + ' GB'
        data['vram_multiplier'] = f"{int(m.group(1))/int(m.group(2)):.1f}x"
    else:
        data['vram'] = ''
    
    # FP16 TFLOPS
    m = re.search(r'(\d+)\s*FP16.*?TFLOPS', text)
    data['fp16_tflops'] = m.group(1) if m else ''
    
    # GPU class
    m = re.search(r'(Consumer|Datacenter|Workstation)\s+class', text)
    data['gpu_class'] = m.group(1) if m else ''
    
    # Cheapest price
    m = re.search(r'Cheapest\s*\$?\s*([\d.]+)/hr', text)
    data['cheapest'] = '$' + m.group(1) + '/hr' if m else ''
    
    # Typical/median price
    m = re.search(r'(?:Typical|median)\s*\$?\s*([\d.]+)/hr', text)
    data['typical'] = '$' + m.group(1) + '/hr' if m else ''
    
    # Marketplaces count  
    m = re.search(r'Marketplaces?\s*(\d+)', text)
    data['marketplaces'] = m.group(1) if m else ''
    
    # Provider pricing - find patterns like "RunPod 100/100 $0.44/hr 3 listings"
    providers = []
    for m in re.finditer(r'([A-Za-z][A-Za-z\s.]+?)\s*(\d+)/100\s*\$?\s*([\d.]+)/hr\s*(\d+)\s+listings?', text):
        name = m.group(1).strip()
        if len(name) > 2:
            providers.append({"provider": name, "price": '$' + m.group(3) + '/hr', "listings": m.group(4)})
    data['providers'] = providers[:10]
    
    # GPU name from title
    m = re.search(r'^(.*?)\s*for\s*Stable Diffusion', text)
    if m:
        data['gpu_name'] = m.group(1).strip()
    
    return data


async def main():
    print("Extracting STRUCTURED GPU DATA...\n")
    
    limits = httpx.Limits(max_connections=200, max_keepalive_connections=50)
    global_client.async_client = httpx.AsyncClient(http2=False, limits=limits, follow_redirects=True, timeout=30)
    
    fetcher = EscalatingFetcher()
    parser = BS4Parser()
    
    gpu_slugs = [
        "a100-pcie-40gb", "a100-pcie-80gb", "a100-sxm-40gb", "a100-sxm-80gb",
        "a40", "b200-sxm", "b300-sxm", "h100-nvl", "h100-pcie", "h100-sxm",
        "h200", "h200-nvl", "l4", "l40", "l40s", "mi300x",
        "rtx-3090", "rtx-4090", "rtx-5090", "rtx-6000-ada",
        "rtx-a5000", "rtx-a6000", "rtx-a4000",
        "rtx-pro-6000-blackwell", "rtx-pro-4000-blackwell",
        "t4", "v100-pcie-16gb", "v100-sxm-16gb", "v100-sxm-32gb", "rtx-3060"
    ]
    
    all_data = []
    for i, slug in enumerate(gpu_slugs):
        url = f"https://www.aiminingco.com/gpu/{slug}/for/stable-diffusion"
        print(f"  [{i+1}/{len(gpu_slugs)}] {slug}...", end=" ", flush=True)
        
        try:
            result = await fetcher.get(url, timeout=30)
            if result.ok:
                tree = parser.parse(result.text)
                data = extract_gpu_data(tree, url)
                all_data.append(data)
                print(f"Fit: {data['fit_score']}  Price: {data['price_per_hr']}  VRAM: {data['vram']}")
            else:
                print(f"HTTP {result.status_code}")
                all_data.append({"gpu_name": slug, "url": url, "error": f"HTTP {result.status_code}"})
        except Exception as e:
            print(f"ERROR: {e}")
            all_data.append({"gpu_name": slug, "url": url, "error": str(e)})
        
        await asyncio.sleep(0.3)
    
    # Save
    output_dir = os.path.join(os.path.dirname(__file__), "aiminingco_data_v2")
    
    class SafeEncoder(json.JSONEncoder):
        def default(self, obj):
            return str(obj)
    
    with open(os.path.join(output_dir, "gpu_structured_data.json"), "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False, cls=SafeEncoder)
    
    # Save readable table
    with open(os.path.join(output_dir, "gpu_comparison_table.txt"), "w", encoding="utf-8") as f:
        header = f"{'GPU Name':<30} {'Fit':<8} {'Level':<16} {'Price/hr':<10} {'VRAM':<10} {'xMin':<6} {'Class':<15} {'Cheapest':<10} {'Mktplcs':<8}\n"
        sep = "-" * 120 + "\n"
        f.write(header)
        f.write(sep)
        
        for d in all_data:
            if 'error' in d:
                f.write(f"{d.get('gpu_name','?'):<30} ERROR: {d['error']}\n")
            else:
                f.write(f"{d.get('gpu_name','?'):<30} {d.get('fit_score',''):<8} {d.get('fit_level',''):<16} "
                        f"{d.get('price_per_hr',''):<10} {d.get('vram',''):<10} {d.get('vram_multiplier',''):<6} "
                        f"{d.get('gpu_class',''):<15} {d.get('cheapest',''):<10} {d.get('marketplaces',''):<8}\n")
        
        # Provider pricing
        f.write(f"\n\n{'='*70}\nDETAILED PROVIDER PRICING\n{'='*70}\n")
        for d in all_data:
            name = d.get('gpu_name', '?')
            provs = d.get('providers', [])
            if provs:
                f.write(f"\n{name} ({d.get('price_per_hr','?')}/hr avg):\n")
                for p in provs:
                    f.write(f"  - {p['provider']:<20} {p['price']:<10} ({p['listings']} listings)\n")
    
    print(f"\n✓ Data saved!")
    print(f"  - gpu_structured_data.json")
    print(f"  - gpu_comparison_table.txt")
    
    if global_client.async_client:
        await global_client.async_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
