"""Input layer for data ingestion."""

from src.input.truth_social import TruthSocialScraper, TruthPost, MockTruthSocialScraper
from src.input.news_aggregator import NewsAggregator, NewsItem, filter_trump_related
from src.input.entity_extractor import EntityExtractor, extract_entities, ExtractionResult

__all__ = [
    "TruthSocialScraper",
    "TruthPost", 
    "MockTruthSocialScraper",
    "NewsAggregator",
    "NewsItem",
    "filter_trump_related",
    "EntityExtractor",
    "extract_entities",
    "ExtractionResult",
]
