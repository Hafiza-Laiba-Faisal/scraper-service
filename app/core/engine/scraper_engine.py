from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from core.engine.quality_scorer import QualityScorer
from core.fetcher.httpx_fetcher import HttpxFetcher
from core.parser.bs4_parser import BS4Parser
from core.extractor.metadata_extractor import DefaultMetadataExtractor
from core.extractor.links_extractor import DefaultLinksExtractor
from core.detectors.login_detector import (
    LoginRequiredDetector,
    CloudflareDetector,
    CaptchaDetector,
    JavaScriptRequiredDetector,
)



@dataclass
class ScrapeResult:
    url: str
    status_code: int = 0
    title: str = ""
    description: str = ""
    html_length: int = 0
    links_count: int = 0
    metadata: dict = field(default_factory=dict)
    links: list = field(default_factory=list)
    content_type: str = ""
    detectors: dict = field(default_factory=dict)
    quality_score: int = 0
    quality_level: str = ""
    adapter_used: str = ""
    error: str | None = None
    elapsed_ms: float = 0
    timing: dict = field(default_factory=dict)
    readability: dict = field(default_factory=dict)
    assets: dict = field(default_factory=dict)


class BaseScraperAdapter(ABC):
    name: str

    @abstractmethod
    def scrape(self, url: str, timeout: int = 30) -> ScrapeResult: ...


class NativeAdapter(BaseScraperAdapter):
    name = "native"

    def __init__(self):
        self.fetcher = HttpxFetcher()
        self.parser = BS4Parser()
        self.metadata_extractor = DefaultMetadataExtractor()
        self.links_extractor = DefaultLinksExtractor()
        self.detectors = [
            LoginRequiredDetector(),
            CloudflareDetector(),
            CaptchaDetector(),
            JavaScriptRequiredDetector(),
        ]

    def scrape(self, url: str, timeout: int = 30) -> ScrapeResult:
        result = ScrapeResult(url=url, adapter_used=self.name)
        timing = {}
        start = time.perf_counter()

        try:
            t0 = time.perf_counter()
            fetch_result = self.fetcher.fetch(url, timeout=timeout)
            timing["fetch_ms"] = round((time.perf_counter() - t0) * 1000, 2)

            result.status_code = fetch_result.status_code
            result.content_type = fetch_result.headers.get("content-type", "")
            html = fetch_result.text
            result.html_length = len(html) if html else 0

            if not fetch_result.ok:
                result.error = f"HTTP {fetch_result.status_code}"
                result.timing = timing
                result.elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
                return result

            t0 = time.perf_counter()
            parsed = self.parser.parse(html)
            timing["parse_ms"] = round((time.perf_counter() - t0) * 1000, 2)

            t0 = time.perf_counter()
            metadata = self.metadata_extractor.extract(parsed, url)
            result.title = metadata.get("og_title") or metadata.get("title", "")
            result.description = metadata.get("og_description") or metadata.get("description", "")
            result.metadata = metadata

            links_data = self.links_extractor.extract(parsed, url)
            result.links = links_data["links"]
            result.links_count = links_data["count"]
            timing["extract_ms"] = round((time.perf_counter() - t0) * 1000, 2)

            # Readability and Asset extraction
            from core.content.readability_extractor import ReadabilityExtractor
            from core.extractor.asset_extractor import AssetExtractor
            
            readability_extractor = ReadabilityExtractor(base_url=url)
            result.readability = readability_extractor.extract(html)
            
            asset_extractor = AssetExtractor(base_url=url)
            result.assets = asset_extractor.extract(parsed)

            detector_results = {}
            for detector in self.detectors:
                detector_results[detector.name] = detector.detect(html, url)
            result.detectors = detector_results

        except Exception as e:
            result.error = str(e)

        result.timing = timing
        result.elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return result


class DeepCrawlAdapter(BaseScraperAdapter):
    name = "deepcrawl"

    @property
    def configured(self) -> bool:
        return bool(os.environ.get("DEEPCRAWL_API_KEY"))

    def scrape(self, url: str, timeout: int = 30) -> ScrapeResult:
        return ScrapeResult(
            url=url,
            adapter_used=self.name,
            error="DeepCrawl adapter not configured. Set DEEPCRAWL_API_KEY.",
        )


class ScraperEngine:
    def __init__(self, fallback_threshold: float = 0.4):
        self.primary = NativeAdapter()
        self.fallback = DeepCrawlAdapter()
        self.scorer = QualityScorer()
        self.fallback_threshold = fallback_threshold

    def scrape(self, url: str, timeout: int = 30) -> ScrapeResult:
        result = self.primary.scrape(url, timeout=timeout)

        score_data = self.scorer.score({
            "title": result.title,
            "html_length": result.html_length,
            "links_count": result.links_count,
            "description": result.description,
            "status_code": result.status_code,
            "detectors": result.detectors,
        })
        result.quality_score = score_data["score"]
        result.quality_level = score_data["quality"]

        normalized = score_data["score"] / 100.0
        if normalized < self.fallback_threshold and self.fallback.configured:
            fallback_result = self.fallback.scrape(url, timeout=timeout)
            fallback_score = self.scorer.score({
                "title": fallback_result.title,
                "html_length": fallback_result.html_length,
                "links_count": fallback_result.links_count,
                "description": fallback_result.description,
                "status_code": fallback_result.status_code,
                "detectors": fallback_result.detectors,
            })
            fallback_result.quality_score = fallback_score["score"]
            fallback_result.quality_level = fallback_score["quality"]

            if fallback_result.quality_score > result.quality_score:
                return fallback_result

        return result
