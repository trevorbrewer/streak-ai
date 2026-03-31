# Setup Guide

## Prerequisites

- Python 3.11 or higher
- A GitHub account
- An Anthropic API key (get one at console.anthropic.com)
- Optional: SendGrid account for email delivery

## Installation

1. Clone the repo
   git clone https://github.com/YOUR_USERNAME/streak-ai.git
   cd streak-ai

2. Create and activate virtual environment
   python3 -m venv venv
   source venv/bin/activate

3. Install dependencies
   pip install -r requirements.txt

4. Configure environment variables
   cp .env.example .env
   # Edit .env with your actual API keys

5. Verify setup
   python3 src/config.py

## API Keys

| Key | Where to get it | Required? |
|-----|----------------|-----------|
| ANTHROPIC_API_KEY | console.anthropic.com | Yes |
| SENDGRID_API_KEY | sendgrid.com | For email |
| OPENWEATHER_API_KEY | openweathermap.org/api | Optional |

## Running the pipeline

   python3 streak_ai.py --run-now

## Running tests

   python3 -m pytest tests/ -v