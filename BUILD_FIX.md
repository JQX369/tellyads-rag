# Vercel Build Command Fix

## The Issue
Your Build Command is: `cd frontend && npm run build`
But your Root Directory is already: `frontend`

This causes Vercel to look for `frontend/frontend` which doesn't exist.

## The Fix

In Vercel Settings → Build and Development Settings:

1. **Build Command**: Change from `cd frontend && npm run build` to just: `npm run build`
2. Click **Save**

Since Root Directory is already set to `frontend`, Vercel will automatically:
- Change into the `frontend/` directory
- Run `npm install` 
- Run `npm run build`
- Look for output in `.next/`

## After Fixing

1. Go to **Deployments** tab
2. Click **"Redeploy"** on the latest deployment
3. Or push a new commit to trigger auto-deployment

The deployment should work now!

