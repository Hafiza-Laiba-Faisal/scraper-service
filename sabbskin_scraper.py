"""
Sabbskin.com - Full Image Scraper
Scrapes all product/collection images and saves them with their URLs.
"""
import os, re, json, time, hashlib, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

BASE_URL = "https://www.sabbskin.com"
DOWNLOAD_DIR = "sabbskin_images"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

session = requests.Session()
session.headers.update(HEADERS)

visited_pages = set()
all_image_urls = {}  # url -> {filename, alt, page_source}
downloaded = 0


def get_soup(url):
    try:
        r = session.get(url, timeout=20)
        if r.status_code == 200:
            return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"  ⚠ Failed {url}: {e}")
    return None


def extract_images(soup, page_url):
    """Extract all product/content images from a page."""
    found = []
    if not soup:
        return found

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        srcset = img.get("srcset") or img.get("data-srcset") or ""
        alt = img.get("alt", "").strip()

        # Get best resolution from srcset
        if srcset:
            parts = [p.strip().split(" ")[0] for p in srcset.split(",") if p.strip()]
            if parts:
                src = parts[-1]  # last = highest resolution

        if not src:
            continue

        # Skip flags, icons, svgs, tiny images
        if any(skip in src for skip in ["/flags/", "cdn.shopify.com/static", ".svg", "icon"]):
            continue

        # Normalize URL
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = urljoin(BASE_URL, src)

        # Strip width params and get full size
        src_clean = re.sub(r"[?&]width=\d+", "", src)
        src_clean = re.sub(r"_\d+x\d+(\.[a-z]+)", r"\1", src_clean)

        if src_clean not in all_image_urls:
            all_image_urls[src_clean] = {
                "url": src_clean,
                "alt": alt,
                "source_page": page_url,
                "filename": ""
            }
            found.append(src_clean)

    return found


def get_all_product_urls(soup):
    """Extract product URLs from a page."""
    urls = set()
    if not soup:
        return urls
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/products/" in href:
            full = urljoin(BASE_URL, href)
            urls.add(full.split("?")[0])  # remove query params
    return urls


def get_all_collection_urls(soup):
    """Extract collection URLs from a page."""
    urls = set()
    if not soup:
        return urls
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/collections/" in href and "all" not in href:
            full = urljoin(BASE_URL, href)
            urls.add(full.split("?")[0])
    return urls


def scrape_page(url, page_type="page"):
    if url in visited_pages:
        return
    visited_pages.add(url)
    soup = get_soup(url)
    if not soup:
        return

    imgs = extract_images(soup, url)
    if imgs:
        print(f"  [{page_type}] {url.split(BASE_URL)[-1][:60]} → {len(imgs)} images")

    return soup


def download_image(url, filename):
    global downloaded
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    if os.path.exists(filepath):
        return False
    try:
        r = session.get(url, timeout=30, stream=True)
        if r.status_code == 200:
            with open(filepath, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            downloaded += 1
            return True
    except Exception as e:
        print(f"  ❌ {url}: {e}")
    return False


def get_filename_from_url(url, idx):
    """Extract clean filename from URL."""
    path = urlparse(url).path
    name = path.split("/")[-1].split("?")[0]
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    if not name or "." not in name:
        ext = ".jpg"
        name = f"image_{idx:04d}{ext}"
    else:
        # Prepend index for uniqueness
        name = f"{idx:04d}_{name}"
    return name


def main():
    print("🧴 Sabbskin.com Image Scraper")
    print("=" * 50)

    # Step 1: Homepage
    print("\n📄 Step 1: Scraping homepage...")
    soup_home = scrape_page(BASE_URL, "homepage")

    # Step 2: All collections
    print("\n📂 Step 2: Finding all collections...")
    collection_urls = set()
    if soup_home:
        collection_urls = get_all_collection_urls(soup_home)

    # Also try known collections from homepage links
    known = [
        "/collections/all",
        "/collections/cleanser",
        "/collections/sunscreen",
        "/collections/serum-1",
        "/collections/moisturizers",
        "/collections/eye",
        "/collections/vitamin-c",
        "/collections/niacinamide-1",
        "/collections/retinol",
        "/collections/tenor-mist",
        "/collections/face-mask",
        "/collections/hair",
    ]
    for k in known:
        collection_urls.add(urljoin(BASE_URL, k))

    print(f"  Found {len(collection_urls)} collections")

    product_urls = set()
    for col_url in sorted(collection_urls):
        soup_col = scrape_page(col_url, "collection")
        if soup_col:
            prods = get_all_product_urls(soup_col)
            product_urls.update(prods)
            # Check pagination
            for page_num in range(2, 10):
                paged_url = f"{col_url}?page={page_num}"
                r = session.get(paged_url, timeout=15)
                if r.status_code != 200 or "No products found" in r.text:
                    break
                soup_p = BeautifulSoup(r.text, "html.parser")
                new_prods = get_all_product_urls(soup_p)
                if not new_prods:
                    break
                extract_images(soup_p, paged_url)
                product_urls.update(new_prods)

    print(f"\n🛍 Step 3: Scraping {len(product_urls)} product pages...")
    for prod_url in sorted(product_urls):
        scrape_page(prod_url, "product")
        time.sleep(0.3)

    # Step 4: Download all images
    print(f"\n⬇ Step 4: Downloading {len(all_image_urls)} unique images...")
    results = []
    for idx, (url, meta) in enumerate(all_image_urls.items()):
        filename = get_filename_from_url(url, idx + 1)
        all_image_urls[url]["filename"] = filename
        success = download_image(url, filename)
        size = os.path.getsize(os.path.join(DOWNLOAD_DIR, filename)) if os.path.exists(os.path.join(DOWNLOAD_DIR, filename)) else 0
        results.append({
            "url": url,
            "filename": filename,
            "alt": meta["alt"],
            "source_page": meta["source_page"],
            "size_kb": round(size / 1024, 1),
        })
        if (idx + 1) % 20 == 0:
            print(f"  Progress: {idx+1}/{len(all_image_urls)} | Downloaded: {downloaded}")

    # Step 5: Save URL list as JSON
    json_path = os.path.join(DOWNLOAD_DIR, "image_urls.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n📋 URLs saved to {json_path}")

    # Step 6: Save as CSV
    csv_path = os.path.join(DOWNLOAD_DIR, "image_urls.csv")
    with open(csv_path, "w") as f:
        f.write("filename,url,alt,source_page,size_kb\n")
        for r in results:
            f.write(f'"{r["filename"]}","{r["url"]}","{r["alt"]}","{r["source_page"]}",{r["size_kb"]}\n')
    print(f"📋 CSV saved to {csv_path}")

    print(f"\n✅ Done! {downloaded} images downloaded to ./{DOWNLOAD_DIR}/")
    print(f"   Total unique image URLs found: {len(all_image_urls)}")


if __name__ == "__main__":
    main()
