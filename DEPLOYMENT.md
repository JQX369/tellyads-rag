# GitHub Repository Setup Instructions

## Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `tellyads-rag` (or your preferred name)
3. Description: "Public semantic search platform for TV commercials"
4. Choose **Public** or **Private**
5. **DO NOT** initialize with README, .gitignore, or license (we already have these)
6. Click **"Create repository"**

## Step 2: Push to GitHub

After creating the repo, GitHub will show you commands. Use these:

```bash
# Add the remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/tellyads-rag.git

# Rename branch to main (if needed)
git branch -M main

# Push to GitHub
git push -u origin main
```

## Step 3: Deploy to Vercel

### Option A: Via Vercel Dashboard (Recommended)

1. Go to https://vercel.com/new
2. **Import Git Repository**: Select your `tellyads-rag` repo
3. **Configure Project**:
   - **Framework Preset**: Next.js
   - **Root Directory**: `frontend`
   - **Build Command**: `cd frontend && npm run build` (or leave default)
   - **Output Directory**: `.next` (or leave default)
4. **Environment Variables**:
   - `NEXT_PUBLIC_API_URL` = `https://your-backend-url.com` (set this after deploying backend)
   - `NEXT_PUBLIC_BASE_URL` = `https://your-vercel-app.vercel.app`
5. Click **Deploy**

### Option B: Via Vercel CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# Deploy (from project root)
cd frontend
vercel

# Follow prompts:
# - Set root directory: frontend
# - Override settings? No
```

## Step 4: Deploy Backend

The backend needs to be deployed separately. Options:

### Railway (Easiest)
1. Go to https://railway.app
2. New Project → Deploy from GitHub
3. Select your repo
4. Add service → Python
5. Set start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
6. Add environment variables from your `.env` file
7. Deploy

### Render
1. Go to https://render.com
2. New → Web Service
3. Connect GitHub repo
4. Settings:
   - **Build Command**: `pip install -r tvads_rag/requirements.txt`
   - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables
6. Deploy

### Fly.io
```bash
# Install flyctl
# Then:
fly launch
# Follow prompts, set start command as above
```

## Step 5: Update Frontend Environment Variable

After backend is deployed:
1. Go to Vercel Dashboard → Your Project → Settings → Environment Variables
2. Update `NEXT_PUBLIC_API_URL` to your backend URL
3. Redeploy

## 🎉 Done!

Your site should now be live at `https://your-app.vercel.app`





