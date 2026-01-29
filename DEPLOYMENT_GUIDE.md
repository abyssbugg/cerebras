# Cerebras Anthropic Gateway - Render Deployment Guide

## Overview

This gateway allows you to use Claude Code, Cursor, and Droid CLI with Cerebras AI by providing an Anthropic-compatible API endpoint. Just like GLM and MiniMax, users simply point their tools to your gateway URL and use their Cerebras API key directly.

## Authentication Modes

### Passthrough Mode (Recommended - Like GLM/MiniMax)

Users provide their own Cerebras API key directly. This is the simplest setup and what GLM/MiniMax use.

**Server Configuration:**
- `GATEWAY_API_KEYS` = empty (no value)
- `CEREBRAS_API_KEY` = empty (not needed)

**Client Configuration:**
- Users set their Cerebras API key as `ANTHROPIC_AUTH_TOKEN`
- The gateway forwards it to Cerebras

### Gateway Keys Mode (Alternative)

Server admin issues custom API keys to users. Server uses its own Cerebras key.

**Server Configuration:**
- `GATEWAY_API_KEYS` = comma-separated list of keys you issue
- `CEREBRAS_API_KEY` = your server's Cerebras key

**Client Configuration:**
- Users set the gateway key you issued as `ANTHROPIC_AUTH_TOKEN`

---

## Deploy to Render (Passthrough Mode)

### Step 1: Push to GitHub

Make sure your code is pushed to GitHub (already done if following the project).

### Step 2: Create Render Web Service

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository (`cerebras`)
4. Configure the service:

   | Setting | Value |
   |---------|-------|
   | **Name** | `cerebras` |
   | **Runtime** | Python 3 |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
   | **Instance Type** | Free (or Starter for better performance) |

### Step 3: Set Environment Variables (Passthrough Mode)

In Render dashboard, go to **"Environment"** tab and add:

| Variable | Value |
|----------|-------|
| `CEREBRAS_BASE_URL` | `https://api.cerebras.ai/v1` |
| `CEREBRAS_MODEL` | `zai-glm-4.7` |
| `ENVIRONMENT` | `production` |
| `RATE_LIMIT_ENABLED` | `false` |
| `CACHE_ENABLED` | `false` |

**DO NOT set `GATEWAY_API_KEYS` or `CEREBRAS_API_KEY`** - this enables passthrough mode.

### Step 4: Deploy

Click **"Create Web Service"** and wait for deployment (usually 2-5 minutes).

Your gateway will be available at:
```
https://cerebras.onrender.com
```

---

## Configure Your Clients

### Claude Code Configuration

Add these to your Claude Code settings file or environment variables:

```json
{
    "ANTHROPIC_BASE_URL": "https://cerebras.onrender.com/anthropic",
    "ANTHROPIC_AUTH_TOKEN": "YOUR_CEREBRAS_API_KEY",
    "API_TIMEOUT_MS": "3000000",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "ANTHROPIC_MODEL": "zai-glm-4.7",
    "ANTHROPIC_SMALL_FAST_MODEL": "zai-glm-4.7",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "zai-glm-4.7",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "zai-glm-4.7",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "zai-glm-4.7"
}
```

Or as environment variables:

```bash
export ANTHROPIC_BASE_URL="https://cerebras.onrender.com/anthropic"
export ANTHROPIC_API_KEY="YOUR_CEREBRAS_API_KEY"
```

**Replace `YOUR_CEREBRAS_API_KEY` with your actual Cerebras API key (e.g., `csk-...`)**

### Droid CLI (Factory AI) Configuration

Add to your Droid CLI config:

```json
{
    "custom_models": [
        {
            "model_display_name": "Cerebras Coding Plan",
            "model": "zai-glm-4.7",
            "base_url": "https://cerebras.onrender.com/anthropic",
            "api_key": "YOUR_CEREBRAS_API_KEY",
            "provider": "anthropic",
            "max_tokens": 64000
        },
        {
            "model_display_name": "GLM-4.7 [Cerebras Coding Plan]",
            "model": "zai-glm-4.7",
            "base_url": "https://cerebras.onrender.com/anthropic",
            "api_key": "YOUR_CEREBRAS_API_KEY",
            "provider": "generic-chat-completion-api",
            "max_tokens": 131072
        }
    ]
}
```

### Cursor IDE Configuration

In Cursor settings:

```json
{
    "anthropic.baseUrl": "https://cerebras.onrender.com/anthropic",
    "anthropic.apiKey": "YOUR_CEREBRAS_API_KEY"
}
```

---

## Testing Your Deployment

### 1. Health Check

```bash
curl https://cerebras.onrender.com/health
```

Expected output:
```json
{"status": "healthy", ...}
```

### 2. Test Message (Non-Streaming)

```bash
curl -X POST https://cerebras.onrender.com/anthropic/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_CEREBRAS_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "zai-glm-4.7",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello! Say hi briefly."}]
  }'
```

### 3. Test Streaming

```bash
curl -X POST https://cerebras.onrender.com/anthropic/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_CEREBRAS_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "zai-glm-4.7",
    "max_tokens": 100,
    "stream": true,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---

## Available Endpoints

| Endpoint | URL |
|----------|-----|
| Health | `https://cerebras.onrender.com/health` |
| Messages (standard) | `https://cerebras.onrender.com/v1/messages` |
| Messages (anthropic) | `https://cerebras.onrender.com/anthropic/v1/messages` |
| Token Count | `https://cerebras.onrender.com/v1/messages/count_tokens` |

**Note:** Both `/v1/messages` and `/anthropic/v1/messages` work identically. The `/anthropic` prefix is for GLM/MiniMax compatibility.

---

## Render Free Tier Limitations

- **Sleep after 15 minutes of inactivity** - First request after sleep takes ~30s to spin up
- **Limited bandwidth** - 100GB/month
- **No Redis** - Caching and rate limiting use in-memory fallback

### Upgrade Options

For always-on service without cold starts:
- **Starter ($7/month)** - No sleep, better performance
- **Standard ($25/month)** - More resources, priority support

---

## Performance Tuning

### Uvicorn Workers

For high-traffic deployments, increase the number of uvicorn workers:

```bash
# Instead of the default single worker:
uvicorn app.main:app --host 0.0.0.0 --port $PORT

# Use multiple workers (recommended: 2-4 per CPU core):
uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 4
```

**Render Configuration:**
Update the Start Command in Render dashboard:
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 4
```

**Docker Configuration:**
Update the CMD in Dockerfile:
```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]
```

**Guidelines:**
- **Development:** 1 worker (default)
- **Production (small):** 2-4 workers
- **Production (high traffic):** 4-8 workers (requires paid tier)

---

## Troubleshooting

### "Service is sleeping"
Normal for free tier. Wait 30 seconds for first request.

### "Invalid Cerebras API key"
Verify your Cerebras API key is correct. Go to [Cerebras Dashboard](https://cloud.cerebras.ai/) to check.

### "Connection timeout"
Increase `API_TIMEOUT_MS` in Claude Code settings (try `3000000` = 50 minutes).

### "No API key provided"
Make sure you're passing the API key in the `x-api-key` header or `Authorization: Bearer` header.

### "Rate limit exceeded"
If using free tier, you may hit Cerebras rate limits. Check your Cerebras plan limits.

---

## Architecture

```
┌─────────────────┐          ┌──────────────────────┐          ┌─────────────────┐
│   Claude Code   │ ──────▶  │ Render Web Service   │ ──────▶  │   Cerebras AI   │
│   Cursor IDE    │          │ (Your Gateway)       │          │   (zai-glm-4.7) │
│   Droid CLI     │          │                      │          │                 │
└─────────────────┘          └──────────────────────┘          └─────────────────┘
      ▲                              │
      │                              │
      └──────────────────────────────┘
        Anthropic-compatible API
        (Same as GLM/MiniMax)

User's Cerebras API Key ─────────────────────────────────────▶ Passed through
```

---

## Success Criteria

You're done when:
- ✅ Health check returns `{"status": "healthy"}`
- ✅ Test message returns a response
- ✅ Claude Code works with your gateway URL
- ✅ Gateway stays up even when your PC is off
- ✅ Users can use their own Cerebras API keys
