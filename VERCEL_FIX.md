# Vercel Configuration Fix

## The Issue
Vercel needs to know that your Next.js app is in the `frontend/` subdirectory, not the root.

## Solution: Update Project Settings in Vercel Dashboard

1. Go to your Vercel project: https://vercel.com/jacyorath/tellyads-rag/settings
2. Navigate to **Settings** → **General**
3. Scroll down to **Root Directory**
4. Click **Edit**
5. Set Root Directory to: `frontend`
6. Click **Save**

## Alternative: Use Vercel CLI

If you have Vercel CLI installed:

```bash
cd frontend
vercel link
# Select your existing project: tellyads-rag
vercel --prod
```

## After Configuration

Once the root directory is set, Vercel will automatically:
- Detect Next.js in the `frontend/` folder
- Run `npm install` and `npm run build` in that directory
- Deploy successfully

The push I just made should trigger a new deployment once the root directory is configured correctly.





