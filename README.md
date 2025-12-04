# TellyAds RAG - Public Semantic Search Platform

A modern web application for searching and exploring TV commercials using semantic AI.

## 🚀 Features

- **Semantic Search**: Find ads by concept, emotion, or content (e.g., "car ads with road trips", "nostalgic 90s commercials")
- **RAG-Powered Analysis**: AI-extracted insights including impact scores, emotional arcs, creative DNA
- **Video Playback**: Direct CloudFront integration for ad viewing
- **SEO Optimized**: Full metadata, sitemap, structured data for search engine discoverability
- **Modern UI**: Built with Next.js 14, TypeScript, Tailwind CSS

## 📁 Project Structure

```
├── backend/           # FastAPI REST API
│   ├── main.py       # API endpoints
│   └── csv_parser.py # CloudFront URL mapping
├── frontend/          # Next.js application
│   ├── app/          # App Router pages
│   ├── components/   # React components
│   └── lib/          # Utilities & types
└── tvads_rag/        # RAG ingestion pipeline (unchanged)
```

## 🛠️ Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (via Supabase)
- `.env` file with database credentials

### Backend

```bash
# Install dependencies
pip install -r tvads_rag/requirements.txt

# Run API server
python -m uvicorn backend.main:app --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000`

## 🌐 Deployment

### Vercel (Frontend)

1. Connect your GitHub repo to Vercel
2. Set build command: `cd frontend && npm run build`
3. Set output directory: `frontend/.next`
4. Add environment variable: `NEXT_PUBLIC_API_URL=https://your-backend-url.com`

### Backend

Deploy FastAPI to any Python hosting (Railway, Render, Fly.io, etc.):

```bash
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

## 📝 Environment Variables

### Backend (.env)
- `SUPABASE_DB_URL` - PostgreSQL connection string
- `OPENAI_API_KEY` - For embeddings/search
- `COHERE_API_KEY` - For reranking (optional)

### Frontend (.env.local)
- `NEXT_PUBLIC_API_URL` - Backend API URL
- `NEXT_PUBLIC_BASE_URL` - Frontend URL (for SEO)

## 🔒 Safety

**Your ingestion pipeline (`tvads_rag/`, `index_ads.py`) remains completely untouched.** The API only reads from the database - no writes, no schema changes.

## 📄 License

[Your License Here]





