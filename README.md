# Trump Policy Analysis Agent

A daily intelligence briefing agent that analyzes Trump's Truth Social posts with structured judgment and falsifiable hypotheses.

## Features

- **Structured Judgment**: 4-step judgment process (0-3) with strict STOP RULEs
- **Real-time Grounding**: Parallel search to fill LLM knowledge gaps
- **Append-Only Memory**: Events, entity states, and hypotheses stored immutably
- **Devil's Advocate**: Built-in red team challenge before output
- **Honest Output**: Competing explanations, falsifiable conditions, explicit uncertainty

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env with your API keys
```

## Usage

```bash
# Analyze a single tweet
python main.py --tweet "Just had a GREAT call with President Delcy..."

# Generate daily brief for a specific date
python main.py --generate-daily-brief --date 2026-01-15
```

## Required API Keys

- Supabase URL + anon key
- Tavily API key (search)
- Apify API key (Truth Social scraper)
- Google AI API key (Gemini)
