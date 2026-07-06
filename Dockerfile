# ---------------------------------------------------------------------------
# Spotify Skip Tracker — Railway-only deployment
#
# Multi-stage build:
#   Stage 1 (frontend-build): builds the React app with Node.js
#   Stage 2 (runtime):        Python + Flask/Gunicorn, serves both the API
#                             and the built frontend from frontend/dist
#
# Flask serves frontend/dist automatically (see spotify_skip_tracker/web.py):
#   /        → frontend/dist/index.html (SPA fallback)
#   /assets  → static files
#   /api/*   → Flask API routes
# ---------------------------------------------------------------------------

# ---- Stage 1: build the React frontend -----------------------------------
FROM node:22-alpine AS frontend-build

WORKDIR /build

# Install dependencies first (better layer caching)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Build the production bundle → /build/dist
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python runtime ----------------------------------------------
FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend source
COPY . .

# Copy the built frontend into the location web.py expects:
#   <repo root>/frontend/dist
COPY --from=frontend-build /build/dist ./frontend/dist

# Railway injects PORT at runtime; default to 5000 for local docker runs.
# Shell form is required for ${PORT} expansion.
CMD gunicorn server:app --bind 0.0.0.0:${PORT:-5000} --timeout 120 --workers 1
