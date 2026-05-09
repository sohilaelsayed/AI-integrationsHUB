# AI Integration Hub - Setup Guide

## Quick Start

This is a FastAPI-based microservice for AI-powered charity donor-need matching.

### Prerequisites
- Python 3.8+
- Git
- OpenRouter API account (for AI)
- Redis Cloud account (for caching)

### Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd AI-integrationsHUB
   ```

2. **Set up environment variables**
   ```bash
   # Copy the template
   cp .env.example .env

   # Edit .env with your credentials:
   # - OPENROUTER_API_KEY: Get from https://openrouter.ai/
   # - REDIS_URL: Your Redis Cloud connection string
   # - REDIS_PREFIX: Keep as "charityNeedsSmart" (optional)
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the service**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Test the API**
   - Open http://127.0.0.1:8000/docs (Swagger UI)
   - Try the `/match` endpoint

### Required Accounts

- **OpenRouter API**: Sign up at https://openrouter.ai/ (free tier available)
- **Redis Cloud**: Sign up at https://redis.com/ (free tier available)

### Project Structure

```
AI-integrationsHUB/
├── app/
│   ├── main.py              # FastAPI app entry
│   ├── core/
│   │   └── config.py        # Environment config
│   ├── models/
│   │   └── schemas.py       # Pydantic models
│   ├── routes/
│   │   └── match_route.py   # API endpoints
│   └── services/
│       └── ai_service.py    # AI & caching logic
├── requirements.txt         # Python dependencies
├── .env.example            # Environment template
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

### API Usage

**Endpoint:** `POST /api/match`

**Example Request:**
```json
{
  "donor": {
    "donorOrganizationId": "123e4567-e89b-12d3-a456-426614174000",
    "donorOrganizationName": "EgyFood Corp",
    "donorOrganizationDescription": "Food distribution company",
    "city": "Cairo",
    "governorate": "Cairo"
  },
  "charityNeeds": [
    {
      "charityNeedId": "a3f8c912-4d5e-4b3a-9c1f-2e8d7a6b5c4d",
      "charityName": "Hope Foundation",
      "productName": "Rice Bags",
      "category": 0,
      "quantity": 200,
      "unit": 0,
      "priority": 0,
      "status": 1,
      "createdAt": "2024-01-01T00:00:00Z"
    }
  ]
}
```

**Response:**
```json
{
  "matchedCharityNeeds": [...],
  "status": {"successful": true, "message": "..."},
  "source": "ai"
}
```

### Features

- AI-powered donor-need matching
- Redis caching (1-hour TTL)
- Graceful fallback when services are down
- Comprehensive data validation
- Swagger documentation

### Security Notes

- Never commit `.env` file (it's in `.gitignore`)
- Use `.env.example` as template for credentials
- Keep API keys secure and rotate regularly

### Troubleshooting

**Service won't start:**
- Check Python version (3.8+)
- Verify all dependencies installed
- Ensure `.env` is properly configured

**Redis connection fails:**
- Service continues working (caching disabled)
- Check Redis URL format
- Verify Redis Cloud credentials

**AI requests fail:**
- Check OpenRouter API key
- Verify internet connection
- Service falls back to basic matching


### License

[Add your license here]