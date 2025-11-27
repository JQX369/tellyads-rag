# Quick Fix for Vercel Deployment

## The Problem
Vercel is looking for `frontend/frontend` instead of `frontend/`

## Solution: Update Root Directory in Vercel Dashboard

**Go to:** https://vercel.com/jacyoraths-projects/tellyads-rag/settings

1. Scroll to **"Root Directory"** section
2. Click **Edit**
3. Change from `frontend` (or whatever it shows) to just: **`frontend`**
4. Make sure it's NOT `frontend/frontend`
5. Click **Save**

## Then Trigger Deployment

After updating the root directory:

1. Go to **Deployments** tab
2. Click **"Redeploy"** on the latest deployment, OR
3. Push a new commit to trigger auto-deployment:
   ```bash
   git commit --allow-empty -m "Trigger Vercel deployment"
   git push origin main
   ```

The deployment should now work correctly!

