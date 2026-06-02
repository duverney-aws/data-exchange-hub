# Amplify Application Debugging Guide

## Application Overview

**What it is:** A React + TypeScript self-service portal for CMOs to onboard and manage data exchange contracts with Merck.

**Tech Stack:**
- **Frontend:** React 18 + TypeScript + Vite
- **UI Library:** AWS Cloudscape Design System
- **Routing:** React Router v6
- **Deployment:** AWS Amplify
- **Backend:** AWS API Gateway + Lambda (CDK deployed)

**Current Deployment:**
- **App ID:** `d28qy16znlocxk`
- **Branch:** `main`
- **URL:** `https://main.d28qy16znlocxk.amplifyapp.com`

---

## Understanding How It Works

### Architecture Flow

```
User Browser
    ↓
AWS Amplify (Static Hosting)
    ↓
React App (Cloudscape UI)
    ↓
API Calls (/api/*)
    ↓
API Gateway (from CDK deployment)
    ↓
Lambda Functions
    ↓
DynamoDB / S3 / Glue Schema Registry
```

### Key Components

1. **Frontend Pages:**
   - Dashboard - Overview of contracts and pipelines
   - CMO Registration - New CMO onboarding
   - Data Contracts - List and manage contracts
   - Schema Management - Upload and register schemas
   - Integration Patterns - Select Pattern 1/2/3
   - Pipelines - Monitor pipeline status
   - NL Query - Natural language queries (Bedrock)

2. **API Service (`src/services/api.ts`):**
   - All API calls go to `/api/*` endpoints
   - Expects API Gateway to be configured
   - No authentication currently (placeholder in amplify-config.ts)

3. **Configuration (`src/amplify-config.ts`):**
   - **CRITICAL:** Contains placeholder values that need to be updated

---

## Common Issues & Solutions

### Issue 1: "Failed to fetch" or CORS Errors

**Symptoms:**
- API calls fail with network errors
- Console shows CORS policy errors
- 404 errors on `/api/*` endpoints

**Root Cause:**
The frontend is making API calls to `/api/*` but Amplify doesn't know where the backend API is.

**Solution:**

You need to configure API Gateway endpoint in one of two ways:

#### Option A: Update amplify-config.ts (Recommended)

1. Get your API Gateway endpoint from CDK deployment:
```bash
cd cdk
aws cloudformation describe-stacks --stack-name PharmaDataExchangeApiStack --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' --output text
```

2. Update `frontend/src/amplify-config.ts`:
```typescript
const amplifyConfig = {
  Auth: {
    Cognito: {
      userPoolId: 'PLACEHOLDER_USER_POOL_ID', // Leave for now
      userPoolClientId: 'PLACEHOLDER_CLIENT_ID', // Leave for now
    },
  },
  API: {
    REST: {
      PharmaAPI: {
        endpoint: 'https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/prod', // UPDATE THIS
        region: 'us-east-1',
      },
    },
  },
};
```

3. Update `frontend/src/services/api.ts` to use Amplify API:
```typescript
import { get, post, put } from 'aws-amplify/api';

export async function registerCMO(data: CMORegistrationRequest): Promise<CMORegistrationResponse> {
  const response = await post({
    apiName: 'PharmaAPI',
    path: '/cmo/register',
    options: {
      body: data
    }
  }).response;
  
  return await response.body.json();
}
```

#### Option B: Use Amplify Rewrites (Quick Fix)

Add to `amplify.yml` in your Amplify app:

```yaml
version: 1
frontend:
  phases:
    build:
      commands:
        - npm ci
        - npm run build
  artifacts:
    baseDirectory: dist
    files:
      - '**/*'
  cache:
    paths:
      - node_modules/**/*
customHeaders:
  - pattern: '**/*'
    headers:
      - key: 'Strict-Transport-Security'
        value: 'max-age=31536000; includeSubDomains'
      - key: 'X-Frame-Options'
        value: 'SAMEORIGIN'
      - key: 'X-Content-Type-Options'
        value: 'nosniff'
# ADD THIS SECTION
rewrites:
  - source: '/api/<*>'
    target: 'https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/prod/<*>'
    status: '200'
```

---

### Issue 2: Blank Page / White Screen

**Symptoms:**
- Page loads but shows nothing
- Console shows React errors
- "Cannot read property of undefined" errors

**Debugging Steps:**

1. **Check Browser Console:**
```
Press F12 → Console tab
Look for red error messages
```

2. **Common Causes:**

**a) Missing Environment Variables:**
Check if `amplify-config.ts` has placeholder values.

**b) Routing Issues:**
Amplify needs to handle client-side routing. Add to `amplify.yml`:

```yaml
customHeaders:
  - pattern: '**/*'
    headers:
      - key: 'Cache-Control'
        value: 'no-cache'
# ADD THIS
redirects:
  - source: '</^[^.]+$|\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json)$)([^.]+$)/>'
    target: '/index.html'
    status: '200'
```

**c) Build Errors:**
Check Amplify build logs:
```bash
aws amplify list-jobs --app-id d28qy16znlocxk --branch-name main --max-results 1
```

---

### Issue 3: API Returns 403 Forbidden

**Symptoms:**
- API calls return 403 status
- "Missing Authentication Token" error

**Root Cause:**
API Gateway requires authentication but frontend isn't sending credentials.

**Solution:**

1. **Check if API requires auth:**
```bash
aws apigateway get-rest-apis --query 'items[?name==`PharmaDataExchangeAPI`]'
```

2. **If auth is required, implement Cognito:**

Update `frontend/src/main.tsx`:
```typescript
import { Amplify } from 'aws-amplify';
import amplifyConfig from './amplify-config';

Amplify.configure(amplifyConfig);

// Rest of your code...
```

3. **Add authentication to API calls:**
```typescript
import { fetchAuthSession } from 'aws-amplify/auth';

export async function registerCMO(data: CMORegistrationRequest): Promise<CMORegistrationResponse> {
  const session = await fetchAuthSession();
  const token = session.tokens?.idToken?.toString();
  
  const response = await fetch('/api/cmo/register', {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(data),
  });
  
  // ... rest of code
}
```

---

### Issue 4: Build Fails in Amplify

**Symptoms:**
- Deployment shows "Build failed"
- Red status in Amplify console

**Debugging Steps:**

1. **View Build Logs:**
```bash
aws amplify get-job --app-id d28qy16znlocxk --branch-name main --job-id <JOB-ID>
```

2. **Common Build Errors:**

**a) TypeScript Errors:**
```bash
# Test build locally
cd frontend
npm run build
```

Fix any TypeScript errors before deploying.

**b) Missing Dependencies:**
Check `package.json` has all dependencies:
```json
{
  "dependencies": {
    "@cloudscape-design/components": "^3.0.0",
    "aws-amplify": "^6.0.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0"
  }
}
```

**c) Node Version Mismatch:**
Add to `amplify.yml`:
```yaml
version: 1
frontend:
  phases:
    preBuild:
      commands:
        - nvm install 18
        - nvm use 18
        - node --version
    build:
      commands:
        - npm ci
        - npm run build
```

---

### Issue 5: Deployment Script Fails

**Symptoms:**
- `deploy_amplify.py` script errors
- "Error creating deployment" message

**Debugging Steps:**

1. **Check AWS Credentials:**
```bash
aws sts get-caller-identity
```

2. **Verify App ID:**
```bash
aws amplify get-app --app-id d28qy16znlocxk
```

3. **Check if dist.zip exists:**
```bash
cd frontend
ls -lh dist.zip
```

If missing:
```bash
npm run build
cd dist
zip -r ../dist.zip .
cd ..
```

4. **Manual Deployment:**
```bash
# Create deployment
aws amplify create-deployment --app-id d28qy16znlocxk --branch-name main

# Upload zip (use URL from above command)
curl -X PUT -T dist.zip "UPLOAD_URL_FROM_ABOVE"

# Start deployment (use job ID from create-deployment)
aws amplify start-deployment --app-id d28qy16znlocxk --branch-name main --job-id JOB_ID
```

---

## Debugging Checklist

### Before Deployment

- [ ] Backend API deployed via CDK
- [ ] API Gateway endpoint obtained
- [ ] `amplify-config.ts` updated with real endpoint
- [ ] Local build succeeds (`npm run build`)
- [ ] No TypeScript errors
- [ ] `dist.zip` created

### After Deployment

- [ ] Amplify build succeeded (check console)
- [ ] App URL loads (`https://main.d28qy16znlocxk.amplifyapp.com`)
- [ ] No console errors (F12)
- [ ] API calls work (check Network tab)
- [ ] Routing works (navigate between pages)

---

## Testing the Application

### 1. Test Frontend Locally

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`

### 2. Test API Connectivity

```bash
# Test CMO registration endpoint
curl -X POST https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/prod/cmo/register \
  -H "Content-Type: application/json" \
  -d '{
    "organizationName": "Test CMO",
    "contactEmail": "test@example.com",
    "contactPhone": "+1-555-0100",
    "address": "123 Test St",
    "gxpCertified": true
  }'
```

### 3. Test Amplify Deployment

```bash
# Check deployment status
aws amplify list-jobs --app-id d28qy16znlocxk --branch-name main --max-results 1

# Get app details
aws amplify get-app --app-id d28qy16znlocxk
```

---

## Quick Fixes

### Fix 1: Update API Endpoint

```bash
cd frontend/src
# Edit amplify-config.ts
# Replace PLACEHOLDER_API_ENDPOINT with your API Gateway URL
```

### Fix 2: Rebuild and Redeploy

```bash
cd frontend
npm run build
cd dist
zip -r ../dist.zip .
cd ..
python deploy_amplify.py
```

### Fix 3: Add CORS to API Gateway

If API exists but CORS blocks requests:

```bash
# Add CORS headers to API Gateway
aws apigateway update-integration-response \
  --rest-api-id YOUR-API-ID \
  --resource-id YOUR-RESOURCE-ID \
  --http-method POST \
  --status-code 200 \
  --patch-operations op=add,path=/responseParameters/method.response.header.Access-Control-Allow-Origin,value="'*'"
```

---

## Getting Help

### View Amplify Logs

```bash
# List recent jobs
aws amplify list-jobs --app-id d28qy16znlocxk --branch-name main

# Get specific job details
aws amplify get-job --app-id d28qy16znlocxk --branch-name main --job-id <JOB-ID>
```

### View CloudWatch Logs

```bash
# API Gateway logs
aws logs tail /aws/apigateway/PharmaDataExchangeAPI --follow

# Lambda logs
aws logs tail /aws/lambda/PharmaDataExchange-CMORegistration --follow
```

### Check API Gateway

```bash
# List APIs
aws apigateway get-rest-apis

# Get API details
aws apigateway get-rest-api --rest-api-id YOUR-API-ID

# Test endpoint
aws apigateway test-invoke-method \
  --rest-api-id YOUR-API-ID \
  --resource-id YOUR-RESOURCE-ID \
  --http-method POST \
  --body '{"organizationName":"Test"}'
```

---

## What to Tell Me for Debugging

When asking for help, provide:

1. **Error Message:** Exact error from console or logs
2. **What You're Trying:** Which page/feature
3. **Browser Console:** Screenshot of F12 → Console tab
4. **Network Tab:** Screenshot of F12 → Network tab showing failed request
5. **Amplify Build Log:** Output from `aws amplify get-job`
6. **API Endpoint:** Your API Gateway URL
7. **App URL:** Your Amplify app URL

---

## Next Steps

1. **Get API Gateway Endpoint:**
```bash
cd cdk
aws cloudformation describe-stacks --stack-name PharmaDataExchangeApiStack
```

2. **Update amplify-config.ts** with real endpoint

3. **Rebuild and Deploy:**
```bash
cd frontend
npm run build
cd dist && zip -r ../dist.zip . && cd ..
python deploy_amplify.py
```

4. **Test the app** at `https://main.d28qy16znlocxk.amplifyapp.com`

---

## Summary

**The app works like this:**
1. React app hosted on Amplify (static files)
2. User interacts with Cloudscape UI components
3. API calls go to `/api/*` endpoints
4. Amplify needs to know where backend API is (via config or rewrites)
5. Backend API (API Gateway + Lambda) handles requests
6. Data stored in DynamoDB/S3

**Most common issue:** Frontend doesn't know where backend API is. Fix by updating `amplify-config.ts` with your API Gateway endpoint.

**I can help debug:**
- Build failures
- API connectivity issues
- CORS errors
- Routing problems
- TypeScript errors
- Deployment issues

Just share the error message and I'll guide you through the fix!
