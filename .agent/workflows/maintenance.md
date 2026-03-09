---
description: How to maintain and monitor the Smart Parking application
---

# Smart Parking System — Maintenance Guide

// turbo-all

## Health Check
1. Visit `https://your-vercel-domain/api/health` to verify the app is online
2. Visit `https://your-vercel-domain/api/debug/db` to verify database connectivity

## Restarting the App Locally
```bash
cd d:\Documents\projects\samples\JEEVAN
python app.py
```
Then open http://127.0.0.1:5000

## Deploying Updates
```bash
cd d:\Documents\projects\samples\JEEVAN
git add .
git commit -m "Your commit message"
git push origin main
```
Vercel will auto-deploy from the `main` branch.

## If Google Sheets Stops Working
1. Go to https://console.cloud.google.com
2. Navigate to IAM & Admin > Service Accounts
3. Create a new key for your service account (JSON format)
4. Copy the entire JSON content
5. Go to Vercel Dashboard > Settings > Environment Variables
6. Set `GSHEET_CREDENTIALS_JSON` to the full JSON content
7. Redeploy

## Admin Credentials
- **Username:** admin
- **Password:** admin123
- **Login URL:** /login (unified login page)

## Common Issues
| Issue | Solution |
|-------|----------|
| "Loading..." spinner stuck | Clear browser cache (Ctrl+Shift+R) |
| Google Sheets 429 error | Wait 1 min (rate limit), app auto-caches |
| Session expired | Re-login; sessions last 12 hours |
| Email not sending | Check SMTP credentials in .env |
