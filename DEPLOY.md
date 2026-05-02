# Deploy Vera bot — get a public URL in ~2 minutes

## Option A: Render (recommended, free tier, no card needed)

1. Push this folder to a GitHub repo (public or private)
2. Go to https://render.com → New → Web Service
3. Connect your repo → Render auto-detects `render.yaml`
4. Click **Deploy** — your URL: `https://vera-bot.onrender.com`

Or use the Render CLI:
```bash
npm install -g @render-run/cli
render deploy
```

## Option B: Railway (free $5 credit, fastest cold start)

```bash
npm install -g @railway/cli
railway login
railway init
railway up
railway domain   # prints your public URL
```

## Option C: Fly.io (free allowance)

```bash
brew install flyctl    # or curl -L https://fly.io/install.sh | sh
fly auth login
fly launch             # detects Dockerfile, picks region
fly deploy
fly status             # shows your URL: https://vera-bot.fly.dev
```

## Option D: Docker anywhere (GCP Cloud Run, AWS App Runner, etc.)

```bash
docker build -t vera-bot .
docker run -p 8000:8000 vera-bot
# Then push to your container registry and deploy
```

## Verify your deployment

```bash
export BOT=https://your-url-here

curl $BOT/v1/healthz
curl $BOT/v1/metadata

curl -X POST $BOT/v1/context \
  -H 'Content-Type: application/json' \
  -d '{"scope":"merchant","context_id":"m_001","version":1,"payload":{"identity":{"id":"m_001","name":"Dr. Meera Dental Clinic","locality":"Koramangala","category":"dentist"},"performance":{"rating":4.7,"total_reviews":142},"offers":[{"label":"Dental Check Up","price":299,"discount_pct":40}]}}'

curl -X POST $BOT/v1/tick \
  -H 'Content-Type: application/json' \
  -d '{"merchant_id":"m_001","trigger":{"type":"spike","meta":{"search_count":190,"query":"Dental Check Up"}},"category":"dentist"}'
```

## Submit

Submit `https://your-url-here` to magicpin. The judge harness calls the endpoints directly.
