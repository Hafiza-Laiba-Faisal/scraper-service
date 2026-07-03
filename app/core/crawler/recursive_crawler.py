"""
Recursive web crawler with full pipeline integration.
Supports concurrent crawling, queue statistics, and timing breakdown.
"""
from __future__ import annotations
import time
import threading
import hashlib
import uuid
import logging
from typing import Callable, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor

from core.fetcher.httpx_fetcher import HttpxFetcher
from core.parser.bs4_parser import BS4Parser
from core.extractor.metadata_extractor import DefaultMetadataExtractor
from core.extractor.links_extractor import DefaultLinksExtractor
from core.extractor.pdf_extractor import PDFExtractor
from core.extractor.asset_extractor import AssetExtractor
from core.content.readability_extractor import ReadabilityExtractor
from core.content.detector import ContentDetector, ContentType
from core.crawler.sitemap_parser import SitemapParser
from .scheduler import URLScheduler

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    """Result of crawling a single page."""
    url: str
    status_code: int = 0
    content_type: ContentType = ContentType.UNKNOWN
    title: str = ""
    description: str = ""
    metadata: dict = field(default_factory=dict)
    links: list[str] = field(default_factory=list)
    depth: int = 0
    elapsed_ms: float = 0
    error: Optional[str] = None
    crawled_at: datetime = field(default_factory=datetime.utcnow)
    timing: dict = field(default_factory=dict)
    readability: dict = field(default_factory=dict)
    assets: dict = field(default_factory=dict)


@dataclass
class CrawlStats:
    """Overall crawl statistics."""
    total_pages: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    html_pages: int = 0
    pdf_files: int = 0
    images: int = 0
    other_files: int = 0
    total_time_sec: float = 0
    pages_per_second: float = 0
    # Queue stats
    queued_urls: int = 0
    visited_urls: int = 0
    duplicates_skipped: int = 0
    external_skipped: int = 0
    robots_skipped: int = 0
    max_depth_reached: int = 0


class RecursiveCrawler:
    """
    Production-grade recursive web crawler.
    """

    def __init__(
        self,
        seed_url: str,
        max_depth: int = 3,
        max_pages: int = 100,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
        respect_robots: bool = True,
        timeout: int = 30,
        follow_external: bool = False,
        workers: int = 1,
        on_page: Optional[Callable[[CrawlResult], None]] = None,
        on_progress: Optional[Callable[[CrawlStats], None]] = None,
    ):
        self.seed_url = seed_url
        self.timeout = timeout
        self.workers = max(1, workers)
        self.on_page = on_page
        self.on_progress = on_progress

        # Auto-set allowed_domains to seed domain when follow_external=False
        if not follow_external and allowed_domains is None:
            seed_domain = urlparse(seed_url).netloc.lower()
            allowed_domains = [seed_domain]

        # Components
        self.scheduler = URLScheduler(
            max_depth=max_depth,
            max_pages=max_pages,
            allowed_domains=allowed_domains,
            blocked_domains=blocked_domains,
            respect_robots=respect_robots,
        )
        self.fetcher = HttpxFetcher()
        self.parser = BS4Parser()
        self.meta_extractor = DefaultMetadataExtractor()
        self.links_extractor = DefaultLinksExtractor()
        self.content_detector = ContentDetector()
        self.asset_extractor = AssetExtractor()

        # Results & deduplication state
        self.results: list[CrawlResult] = []
        self.stats = CrawlStats()
        self._lock = threading.RLock()
        self._seen_hashes = set()
        self._last_request_time = {}
        self._domain_lock = threading.Lock()
        self._start_time: float = 0

    def crawl(self) -> list[CrawlResult]:
        """
        Execute crawl from seed URL with concurrent workers.
        """
        self._start_time = time.time()

        # Auto-detect or parse Sitemap if seed is sitemap
        is_sitemap = self.seed_url.endswith(".xml") or self.seed_url.endswith(".xml.gz") or "sitemap" in self.seed_url.lower()
        
        sitemap_urls = []
        if is_sitemap:
            sitemap_parser = SitemapParser(timeout=self.timeout)
            sitemap_urls = sitemap_parser.parse(self.seed_url)
        elif self.scheduler.respect_robots:
            # Auto-detect sitemaps from robots.txt
            parsed_seed = urlparse(self.seed_url)
            base_url = f"{parsed_seed.scheme}://{parsed_seed.netloc}"
            sitemaps = self.scheduler.robots.get_sitemaps(base_url)
            if sitemaps:
                sitemap_parser = SitemapParser(timeout=self.timeout)
                for sm in sitemaps:
                    sitemap_urls.extend(sitemap_parser.parse(sm))

        # Add seed(s) to scheduler
        if sitemap_urls:
            for u in sitemap_urls:
                self.scheduler.add_seed(u)
            if not is_sitemap:
                self.scheduler.add_seed(self.seed_url)
        else:
            if not self.scheduler.add_seed(self.seed_url):
                return []

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {}

            while not self.scheduler.is_complete() or futures:
                # Submit new work up to worker limit
                while len(futures) < self.workers:
                    next_item = self.scheduler.get_next_url()
                    if not next_item:
                        break
                    url, depth = next_item
                    future = executor.submit(self._crawl_page, url, depth)
                    futures[future] = url

                if not futures:
                    break

                # Collect completed futures
                done_futures = [f for f in list(futures) if f.done()]

                if not done_futures:
                    time.sleep(0.05)
                    continue

                for future in done_futures:
                    futures.pop(future)
                    try:
                        result = future.result()
                        with self._lock:
                            self.results.append(result)
                            self._update_stats(result)
                        if self.on_page:
                            self.on_page(result)
                        if self.on_progress:
                            self.on_progress(self.stats)
                    except Exception as e:
                        logger.error(f"Worker exception: {e}")

        # Final stats
        self.stats.total_time_sec = time.time() - self._start_time
        if self.stats.total_time_sec > 0:
            self.stats.pages_per_second = self.stats.total_pages / self.stats.total_time_sec

        # Merge queue stats
        q_stats = self.scheduler.get_stats()
        self.stats.queued_urls = q_stats.get("total_seen", 0)
        self.stats.visited_urls = q_stats.get("completed", 0)
        self.stats.duplicates_skipped = q_stats.get("duplicates_skipped", 0)
        self.stats.external_skipped = q_stats.get("external_skipped", 0)
        self.stats.robots_skipped = q_stats.get("robots_skipped", 0)
        self.stats.max_depth_reached = q_stats.get("max_depth_reached", 0)

        return self.results

    def _crawl_page(self, url: str, depth: int) -> CrawlResult:
        """Crawl a single page with timing breakdown, crawl-delay, deduplication, and extraction."""
        result = CrawlResult(url=url, depth=depth)
        timing = {}

        # Respect robots.txt Crawl-Delay
        if self.scheduler.respect_robots:
            domain = urlparse(url).netloc.lower()
            delay = self.scheduler.robots.get_crawl_delay(url, self.scheduler.user_agent)
            if delay:
                with self._domain_lock:
                    last_time = self._last_request_time.get(domain, 0.0)
                    now = time.monotonic()
                    elapsed = now - last_time
                    if elapsed < delay:
                        sleep_time = delay - elapsed
                        time.sleep(sleep_time)
                    self._last_request_time[domain] = time.monotonic()

        try:
            # Fetch
            t0 = time.time()
            fetch_result = self.fetcher.get(url, timeout=self.timeout)
            timing["fetch_ms"] = round((time.time() - t0) * 1000, 2)

            result.status_code = fetch_result.status_code
            result.elapsed_ms = fetch_result.elapsed_ms

            if not fetch_result.ok:
                result.error = f"HTTP {fetch_result.status_code}"
                self.scheduler.mark_failed(url, result.error)
                result.timing = timing
                return result

            # Detect content type
            result.content_type = self.content_detector.detect(
                url,
                fetch_result.headers
            )

            # Content Hashing & Deduplication
            content_bytes = fetch_result.content or b""
            content_hash = hashlib.sha256(content_bytes).hexdigest()
            
            with self._lock:
                if content_hash in self._seen_hashes:
                    self.scheduler.queue.skip_duplicate()
                    self.scheduler.mark_completed(url)
                    result.error = "Duplicate content skipped"
                    result.timing = timing
                    return result
                self._seen_hashes.add(content_hash)

            # Handle PDF Pipeline
            if result.content_type == ContentType.PDF:
                downloads_dir = Path("downloads")
                downloads_dir.mkdir(exist_ok=True)
                pdf_filename = f"{uuid.uuid4()}.pdf"
                pdf_path = downloads_dir / pdf_filename
                pdf_path.write_bytes(content_bytes)

                pdf_extractor = PDFExtractor(use_ocr=True)
                try:
                    pdf_data = pdf_extractor.extract_text(pdf_path)
                except Exception as e:
                    pdf_data = {"text": "", "pages": 0, "method": "direct", "metadata": {}, "error": str(e)}

                result.title = pdf_data.get("metadata", {}).get("title") or pdf_filename
                result.description = pdf_data.get("metadata", {}).get("subject", "")
                result.metadata = {
                    "pdf_path": str(pdf_path),
                    "pages": pdf_data.get("pages", 0),
                    "method": pdf_data.get("method", "direct"),
                    "pdf_metadata": pdf_data.get("metadata", {}),
                    "text": pdf_data.get("text", "")
                }

            # Handle HTML pages
            elif self.content_detector.should_parse_html(result.content_type):
                html = fetch_result.text

                # Parse
                t1 = time.time()
                tree = self.parser.parse(html)
                timing["parse_ms"] = round((time.time() - t1) * 1000, 2)

                # Extract
                t2 = time.time()
                metadata = self.meta_extractor.extract(tree, url)
                result.title = metadata.get("og_title") or metadata.get("title", "")
                result.description = metadata.get("og_description") or metadata.get("description", "")
                result.metadata = metadata

                links_data = self.links_extractor.extract(tree, url)
                discovered_urls = [link["url"] for link in links_data["links"]]
                result.links = discovered_urls
                timing["extract_ms"] = round((time.time() - t2) * 1000, 2)

                # Readability Extraction
                readability_extractor = ReadabilityExtractor(base_url=url)
                result.readability = readability_extractor.extract(html)

                # Media and File Discovery
                self.asset_extractor.base_url = url
                result.assets = self.asset_extractor.extract(tree)

                # Add discovered URLs to queue
                self.scheduler.add_discovered_urls(
                    discovered_urls,
                    parent_url=url,
                    current_depth=depth
                )

            self.scheduler.mark_completed(url)

        except Exception as e:
            result.error = str(e)
            self.scheduler.mark_failed(url, result.error)

        result.timing = timing
        return result

    def _update_stats(self, result: CrawlResult):
        """Update crawl statistics."""
        self.stats.total_pages += 1

        if result.error:
            if "Duplicate content skipped" in result.error:
                self.stats.skipped += 1
            else:
                self.stats.failed += 1
        else:
            self.stats.successful += 1

        # Content type stats
        if result.content_type == ContentType.HTML:
            self.stats.html_pages += 1
        elif result.content_type == ContentType.PDF:
            self.stats.pdf_files += 1
        elif result.content_type == ContentType.IMAGE:
            self.stats.images += 1
        else:
            self.stats.other_files += 1

    def get_stats(self) -> CrawlStats:
        """Get current crawl statistics."""
        with self._lock:
            return self.stats

