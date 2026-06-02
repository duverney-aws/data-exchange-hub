#!/usr/bin/env python3
"""Deploy frontend dist to AWS Amplify."""
import os
import subprocess
import json
import urllib.request
import zipfile

APP_ID = "d28qy16znlocxk"
BRANCH = "main"

# Pack dist/ with root-level paths (Amplify requires index.html at root, not dist/index.html)
print("Packing dist.zip...")
with zipfile.ZipFile("dist.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk("dist"):
        for f in files:
            abs_path = os.path.join(root, f)
            z.write(abs_path, os.path.relpath(abs_path, "dist"))

# Step 1: Create deployment
print("Creating Amplify deployment...")
result = subprocess.run(
    ["aws", "amplify", "create-deployment", "--app-id", APP_ID, "--branch-name", BRANCH, "--output", "json"],
    capture_output=True, text=True
)
if result.returncode != 0:
    print(f"  Error creating deployment: {result.stderr}")
    exit(1)
data = json.loads(result.stdout)
job_id = data["jobId"]
url = data["zipUploadUrl"]
print(f"  Job ID: {job_id}")

# Step 2: Upload zip
print("Uploading dist.zip...")
with open("dist.zip", "rb") as f:
    req = urllib.request.Request(url, data=f.read(), method="PUT")
    resp = urllib.request.urlopen(req)
    print(f"  Upload status: {resp.status}")

# Step 3: Start deployment
print("Starting deployment...")
result2 = subprocess.run(
    ["aws", "amplify", "start-deployment", "--app-id", APP_ID, "--branch-name", BRANCH, "--job-id", job_id, "--output", "json"],
    capture_output=True, text=True
)
if result2.returncode == 0:
    summary = json.loads(result2.stdout)
    status = summary.get("jobSummary", {}).get("status", "unknown")
    print(f"  Deployment status: {status}")
    print(f"\n  Portal URL: https://main.{APP_ID}.amplifyapp.com")
else:
    print(f"  Error: {result2.stderr}")
