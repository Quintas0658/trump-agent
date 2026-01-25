"""Entity extractor - Extracts entities from text for search query generation."""

from dataclasses import dataclass
from typing import Optional
import re


@dataclass 
class ExtractedEntity:
    """An extracted entity with metadata."""
    name: str
    entity_type: str  # "person", "country", "organization", "topic"
    confidence: float


@dataclass
class ExtractionResult:
    """Result of entity extraction."""
    entities: list[ExtractedEntity]
    keywords: list[str]
    suggested_queries: list[str]


class EntityExtractor:
    """Extracts entities from text for search query generation.
    
    Uses a combination of pattern matching and keyword detection.
    For production, this should be enhanced with LLM-based extraction.
    """
    
    # Known political figures (expanded over time)
    KNOWN_PERSONS = {
        "trump": "Donald Trump",
        "biden": "Joe Biden",
        "vance": "JD Vance",
        "kamala": "Kamala Harris",
        "elon": "Elon Musk",
        "musk": "Elon Musk",
        "delcy": "Delcy Rodríguez",
        "maduro": "Nicolás Maduro",
        "putin": "Vladimir Putin",
        "xi": "Xi Jinping",
        "zelensky": "Volodymyr Zelensky",
        "netanyahu": "Benjamin Netanyahu",
        "powell": "Jerome Powell",
        "bossie": "Dave Bossie",
        "cohen": "Michael Cohen",
    }
    
    # Countries and regions
    COUNTRIES = {
        "venezuela", "iran", "china", "russia", "ukraine", "israel",
        "mexico", "canada", "europe", "eu", "nato", "greenland",
        "denmark", "minnesota", "nevada", "california", "texas",
        "gaza", "palestine", "taiwan",
    }
    
    # Policy topics
    TOPICS = {
        "tariff", "trade", "immigration", "border", "military",
        "sanctions", "executive order", "fed", "interest rate",
        "oil", "energy", "climate", "abortion", "election",
        "crypto", "bitcoin", "truth social", "media",
    }
    
    # Action words (for Judgment 0)
    ACTION_WORDS = {
        "signed", "ordered", "deployed", "fired", "arrested",
        "appointed", "banned", "sanctioned", "invaded", "struck",
        "raided", "pardoned", "vetoed", "declared",
    }
    
    def extract(self, text: str) -> ExtractionResult:
        """Extract entities and generate search queries from text."""
        text_lower = text.lower()
        
        entities = []
        keywords = []
        
        # Extract known persons
        for key, full_name in self.KNOWN_PERSONS.items():
            if key in text_lower:
                entities.append(ExtractedEntity(
                    name=full_name,
                    entity_type="person",
                    confidence=0.9
                ))
        
        # Extract countries
        for country in self.COUNTRIES:
            if country in text_lower:
                entities.append(ExtractedEntity(
                    name=country.title(),
                    entity_type="country",
                    confidence=0.85
                ))
                keywords.append(country)
        
        # Extract topics
        for topic in self.TOPICS:
            if topic in text_lower:
                entities.append(ExtractedEntity(
                    name=topic,
                    entity_type="topic",
                    confidence=0.8
                ))
                keywords.append(topic)
        
        # Extract action words
        for action in self.ACTION_WORDS:
            if action in text_lower:
                keywords.append(action)
        
        # Extract capitalized words (potential proper nouns)
        proper_nouns = self._extract_proper_nouns(text)
        for noun in proper_nouns:
            if noun.lower() not in self.KNOWN_PERSONS:
                entities.append(ExtractedEntity(
                    name=noun,
                    entity_type="unknown",
                    confidence=0.5
                ))
        
        # Generate search queries
        queries = self._generate_queries(entities, keywords, text)
        
        return ExtractionResult(
            entities=entities,
            keywords=keywords,
            suggested_queries=queries,
        )
    
    def _extract_proper_nouns(self, text: str) -> list[str]:
        """Extract capitalized words that might be proper nouns."""
        # Pattern: Capitalized words not at sentence start
        words = text.split()
        proper_nouns = []
        
        for i, word in enumerate(words):
            # Clean punctuation
            clean_word = re.sub(r'[^\w]', '', word)
            
            if not clean_word:
                continue
            
            # Check if capitalized (and not the first word of a sentence)
            if clean_word[0].isupper() and len(clean_word) > 1:
                # Skip common words
                skip_words = {"The", "A", "An", "This", "That", "Just", "Great", "Good", "Bad"}
                if clean_word not in skip_words:
                    proper_nouns.append(clean_word)
        
        return list(set(proper_nouns))
    
    def _generate_queries(
        self, 
        entities: list[ExtractedEntity], 
        keywords: list[str],
        original_text: str
    ) -> list[str]:
        """Generate search queries from extracted entities."""
        queries = []
        
        # Query 1: Direct context (first 50 chars of text)
        if len(original_text) > 20:
            queries.append(f"Trump {original_text[:50]}")
        
        # Query 2-N: Entity-specific queries
        persons = [e for e in entities if e.entity_type == "person"]
        countries = [e for e in entities if e.entity_type == "country"]
        
        for person in persons[:2]:
            if person.name.lower() not in ["donald trump"]:
                queries.append(f"{person.name} news January 2026")
        
        for country in countries[:2]:
            queries.append(f"Trump {country.name} policy 2026")
        
        # Query N+1: Topic-based
        topics = [e for e in entities if e.entity_type == "topic"]
        for topic in topics[:1]:
            queries.append(f"Trump {topic.name} latest")
        
        # Ensure we have at least 2 queries
        if len(queries) < 2:
            queries.append("Trump latest news today")
        
        # Limit to 5 queries max
        return queries[:5]
    
    def detect_actions(self, text: str) -> list[str]:
        """Detect action words in text (for Judgment 0)."""
        text_lower = text.lower()
        found_actions = []
        
        for action in self.ACTION_WORDS:
            if action in text_lower:
                found_actions.append(action)
        
        return found_actions


# LLM-enhanced entity extractor
class LLMEntityExtractor:
    """Entity extractor that uses LLM for better accuracy.
    
    Falls back to rule-based extraction if LLM fails.
    """
    
    def __init__(self, llm_client=None):
        self.llm = llm_client
        self.fallback = EntityExtractor()
    
    def extract(self, text: str) -> ExtractionResult:
        """Extract entities using LLM with fallback."""
        if not self.llm:
            return self.fallback.extract(text)
        
        try:
            return self._llm_extract(text)
        except Exception as e:
            print(f"LLM extraction failed, using fallback: {e}")
            return self.fallback.extract(text)
    
    def _llm_extract(self, text: str) -> ExtractionResult:
        """Use LLM for entity extraction."""
        prompt = f"""Extract entities from this text for search query generation.

TEXT: "{text}"

Return:
1. ENTITIES: List of (name, type) where type is one of: person, country, organization, topic
2. KEYWORDS: Important keywords for search
3. QUERIES: 3-5 search queries to get context about this text

Format your response as:
ENTITIES:
- Name | Type
...

KEYWORDS: word1, word2, ...

QUERIES:
- query 1
- query 2
...
"""
        # This would call the LLM
        # For now, fallback to rule-based
        return self.fallback.extract(text)


# Convenience function
def extract_entities(text: str) -> ExtractionResult:
    """Extract entities from text using the default extractor."""
    return EntityExtractor().extract(text)
