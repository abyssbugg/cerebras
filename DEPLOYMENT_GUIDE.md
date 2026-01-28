# Cerebras Anthropic Gateway - Render Deployment Guide

## Quick Start: Deploy to Render

### Step 1: Push to GitHub

First, create a new repository and push your code:

```bash
cd /Users/shigeo/Desktop/cerebras

# Initialize git if not already done
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: Cerebras Anthropic Gateway"

# Create a repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/cerebras-anthropic-gateway.git
git branch -M main
git push -u origin main
```

### Step 2: Create Render Web Service

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Configure the service:

   | Setting | Value |
   |---------|-------|
   | **Name** | `cerebras-anthropic-gateway` |
   | **Runtime** | Python 3 |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
   | **Instance Type** | Free (or Starter for better performance) |

### Step 3: Set Environment Variables

In Render dashboard, go to **"Environment"** tab and add:

| Variable | Value |
|----------|-------|
| `CEREBRAS_API_KEY` | `csk-meyjyxcnrmpmy8kdm63v6h64mkk28nntmmjprjd4n5te55fe` |
| `CEREBRAS_BASE_URL` | `https://api.cerebras.ai/v1` |
| `CEREBRAS_MODEL` | `zai-glm-4.7` |
| `GATEWAY_API_KEYS` | `your-custom-api-key-here` |
| `ENVIRONMENT` | `production` |
| `RATE_LIMIT_ENABLED` | `false` |
| `CACHE_ENABLED` | `false` |

**IMPORTANT**: Create your own `GATEWAY_API_KEYS` - this is what you'll use in Claude Code.

### Step 4: Deploy

Click **"Create Web Service"** and wait for deployment (usually 2-5 minutes).

Your gateway will be available at:
```
https://cerebras-anthropic-gateway.onrender.com
```

---

## Step 5: Configure Claude Code

Once deployed, add these to your Claude Code settings (or shell profile):

### For Claude Code

Add to your `~/.claude.json` or environment:

```json
{
    "ANTHROPIC_BASE_URL": "https://cerebras-anthropic-gateway.onrender.com",
    "ANTHROPIC_AUTH_TOKEN": "your-custom-api-key-here",
    "API_TIMEOUT_MS": "300000",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "ANTHROPIC_MODEL": "claude-sonnet-4",
    "ANTHROPIC_SMALL_FAST_MODEL": "claude-sonnet-4",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-sonnet-4",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-sonnet-4"
}
```

Or in your shell profile (`~/.bashrc` or `~/.zshrc`):

```bash
export ANTHROPIC_BASE_URL="https://cerebras-anthropic-gateway.onrender.com"
export ANTHROPIC_API_KEY="your-custom-api-key-here"
```

### For Droid CLI (Factory AI)

Add to your config:

```json
{
    "custom_models": [
        {
            "model_display_name": "Cerebras zai-glm-4.7",
            "model": "claude-sonnet-4",
            "base_url": "https://cerebras-anthropic-gateway.onrender.com",
            "api_key": "your-custom-api-key-here",
            "provider": "anthropic",
            "max_tokens": 64000
        }
    ]
}
```

---

## Testing Your Deployment

### 1. Health Check

```bash
curl https://cerebras-anthropic-gateway.onrender.com/health
```

Expected output:
```json
{"status": "healthy", ...}
```

### 2. Test Message (Non-Streaming)

```bash
curl -X POST https://cerebras-anthropic-gateway.onrender.com/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-custom-api-key-here" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-sonnet-4",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello! Say hi briefly."}]
  }'
```

### 3. Test Streaming

```bash
curl -X POST https://cerebras-anthropic-gateway.onrender.com/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-custom-api-key-here" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-sonnet-4",
    "max_tokens": 100,
    "stream": true,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

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

## Troubleshooting

### "Service is sleeping"
Normal for free tier. Wait 30 seconds for first request.

### "CEREBRAS_API_KEY is required"
Set the environment variable in Render dashboard.

### "Rate limit exceeded"
The in-memory rate limit may trigger. Set `RATE_LIMIT_ENABLED=false` if needed.

### "Connection timeout"
Increase `API_TIMEOUT_MS` in Claude Code settings.

---

## Architecture Overview

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
        (Same as MiniMax/GLM)
```

---

## Your Final URLs

After deployment, your endpoints will be:

| Endpoint | URL |
|----------|-----|
| Base URL | `https://cerebras-anthropic-gateway.onrender.com` |
| Messages | `https://cerebras-anthropic-gateway.onrender.com/v1/messages` |
| Token Count | `https://cerebras-anthropic-gateway.onrender.com/v1/messages/count_tokens` |
| Health | `https://cerebras-anthropic-gateway.onrender.com/health` |

---

## Success Criteria

You're done when:
- ✅ Health check returns `{"status": "healthy"}`
- ✅ Test message returns a response
- ✅ Claude Code works with your gateway URL
- ✅ Gateway stays up even when your PC is off
