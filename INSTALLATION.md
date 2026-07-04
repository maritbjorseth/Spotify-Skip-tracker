# Spotify Skip Tracker — Full Installation Guide

This guide takes you from zero to a running dashboard. Every step is explained individually, including what you should see when it works and what to do if it fails.

**Time to complete:** approximately 30–45 minutes  
**Difficulty:** beginner-friendly — no prior experience with Railway, Neon, Vercel, or Spotify APIs required

> If you want an AI to guide you through this installation step by step, see [AI_INSTALL.md](AI_INSTALL.md).

---

## Table of Contents

1. [Check your prerequisites](#1-check-your-prerequisites)
2. [Create a Spotify Developer App](#2-create-a-spotify-developer-app)
3. [Create a Neon database](#3-create-a-neon-database)
4. [Clone the repository](#4-clone-the-repository)
5. [Create a Python virtual environment](#5-create-a-python-virtual-environment)
6. [Install Python dependencies](#6-install-python-dependencies)
7. [Create your environment file](#7-create-your-environment-file)
8. [Fill in the environment variables](#8-fill-in-the-environment-variables)
9. [Authenticate with Spotify](#9-authenticate-with-spotify)
10. [Start the backend](#10-start-the-backend)
11. [Install frontend dependencies](#11-install-frontend-dependencies)
12. [Start the frontend](#12-start-the-frontend)
13. [Log in and verify](#13-log-in-and-verify)
14. [Deploy to production (optional)](#14-deploy-to-production-optional)

---

## 1. Check your prerequisites

You need three tools installed before you begin: Python, Node.js, and git. Check each one separately.

### 1a. Check Python

Open a terminal and run:

```bash
python3 --version
```

**What you should see:**
```
Python 3.12.x
```
Any version of 3.12 or higher is fine (3.13, 3.14, etc.).

> If you see a lower version number (e.g. 3.10 or 3.11), you need to upgrade Python before continuing.  
> Download the latest version from https://www.python.org/downloads/


<img width="321" height="89" alt="image" src="https://github.com/user-attachments/assets/7851a785-aba9-41c5-9860-043a2975a07e" />


---

### 1b. Check Node.js

```bash
node --version
```

**What you should see:**
```
v20.x.x
```
Any version of v20 or higher is fine.

> If you see a lower version, download Node.js from https://nodejs.org/ (choose the LTS version).

---

### 1c. Check git

```bash
git --version
```

**What you should see:**
```
git version 2.x.x
```

> If git is not installed, download it from https://git-scm.com/downloads

---

## 2. Create a Spotify Developer App

The tracker reads from the Spotify Web API. You need to register an app to get your API credentials.

### Step 2a — Open the Spotify Developer Dashboard

Go to https://developer.spotify.com/dashboard and log in with your Spotify account.

<img width="1470" height="615" alt="image" src="https://github.com/user-attachments/assets/6a180c2c-d55f-4a7d-b178-3520e30043eb" />


---

### Step 2b — Create a new app

1. Click **Create app** (top right)
2. Fill in the form:
   - **App name:** `Spotify Skip Tracker` (or any name you prefer)
   - **App description:** `Personal skip tracking tool`
   - **Website:** leave blank
   - **Redirect URIs:** add the following two URIs, one at a time, by clicking **Add**:
     - `http://127.0.0.1:8888/callback`
     - `http://127.0.0.1:5000/api/auth/callback`
   - **Which API/SDKs are you planning to use?** Select **Web API**
3. Check the terms of service box
4. Click **Save**

> **Why two redirect URIs?**  
> The `setup` command (step 9) uses a temporary server on port **8888** for the one-time authentication flow. The web-based login at `/api/auth/login` uses the Flask server on port **5000**. Both URIs must be registered or Spotify will reject the request.

<img width="1470" height="835" alt="Dashbord" src="https://github.com/user-attachments/assets/e751964b-adf2-44e0-9073-4b70501783e9" />


**What you should see:** You are redirected to your app's settings page.

---

### Step 2c — Copy your credentials

On your app's settings page, click **Settings** in the top right.

You will see two values you need to copy:
- **Client ID** — a 32-character string (e.g. `414bee9f9066468fbb2655af4f8a918a`)
- **Client Secret** — click **View client secret** to reveal it

Copy both values and keep them somewhere accessible. You will need them in step 8 and step 9.

<img width="1470" height="747" alt="image" src="https://github.com/user-attachments/assets/98e05bcd-b5f3-40f0-81f7-d4aed860863e" />


---

## 3. Create a Neon database

The tracker stores all play history in a PostgreSQL database. We use Neon, which has a free tier that requires no credit card.

### Step 3a — Sign up for Neon

Go to https://neon.tech and click **Sign up**. You can sign up with your GitHub account.

---

### Step 3b — Create a project

1. After signing up, click **New project**
2. Give it a name, e.g. `spotify-skip-tracker`
3. Choose a region close to you (e.g. `AWS / eu-west-1` for Europe)
4. Click **Create project**

<img width="1470" height="830" alt="image" src="https://github.com/user-attachments/assets/8434e567-4bdb-4576-9ddf-f4ca942d63cd" />


**What you should see:** Neon creates the project and shows you a connection string.

---

### Step 3c — Copy the connection string

On the project page, you will see a **Connection string** panel. It looks like:

```
postgresql://neondb_owner:password@ep-something.aws.neon.tech/neondb?sslmode=require
```

Copy this entire string. You will paste it into `.env.local` in step 8.

> If you close this page, you can find the connection string again under **Dashboard → Connection Details**.

📷 **Skjermbilde:** Neon connection string panel

---

## 4. Clone the repository

Navigate to the folder where you want to store the project, then run:

```bash
git clone https://github.com/your-username/spotify-skip-tracker.git
```

> Replace `your-username` with the actual GitHub username or organisation that hosts this repository.

Then move into the project folder:

```bash
cd spotify-skip-tracker
```

**What you should see:**
```
Cloning into 'spotify-skip-tracker'...
remote: Counting objects: ...
```

Followed by a standard shell prompt inside the `spotify-skip-tracker` folder.

**If this fails:**
- `Repository not found` — double-check the URL. The repository may be private; you may need to be granted access.
- `git: command not found` — git is not installed. See step 1c.

---

## 5. Create a Python virtual environment

A virtual environment keeps this project's Python dependencies separate from the rest of your system. **This step is required on modern macOS and Linux** — Python will refuse to install packages globally.

Run this command inside the project folder:

```bash
python3 -m venv venv
```

**What you should see:** No output. A new folder called `venv/` appears in the project directory.

**If this fails:**
- `No module named venv` — your Python installation is incomplete. Re-install Python from https://www.python.org/downloads/

---

## 6. Activate the virtual environment

You must activate the virtual environment every time you open a new terminal session to work on this project.

**macOS / Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```
venv\Scripts\activate
```

**What you should see:** Your terminal prompt changes to show `(venv)` at the beginning:
```
(venv) your-computer:spotify-skip-tracker you$
```

📷 **Skjermbilde:** Terminal prompt showing `(venv)` prefix

> If you close your terminal and come back later, you must run this command again before running any `python3` or `pip` commands.

---

## 6. Install Python dependencies

With the virtual environment active, install the required Python packages:

```bash
pip install -r requirements.txt
```

**What you should see:** A list of packages being downloaded and installed, ending with:
```
Successfully installed Flask-3.x ... psycopg2-binary-2.x ... requests-2.x ...
```

This may take 30–60 seconds.

**If this fails:**
- `pip: command not found` — the virtual environment is not active. Run `source venv/bin/activate` first (macOS/Linux) or `venv\Scripts\activate` (Windows).
- `error: externally-managed-environment` — you are trying to install without a virtual environment. Go back to step 5.
- Any package fails to build — make sure you have Python 3.12 or higher (`python3 --version`).

---

## 7. Create your environment file

The project uses a file called `.env.local` to store secret credentials. A template is included in the repository.

Run:

```bash
cp .env.local.example .env.local
```

**What you should see:** No output. A new file called `.env.local` appears in the project root.

Verify it exists:

```bash
ls .env.local
```

**What you should see:**
```
.env.local
```

> `.env.local` is listed in `.gitignore` and will never be committed to git. Your credentials stay on your machine only.

**If this fails:**
- `No such file or directory: .env.local.example` — you are not in the project root folder. Run `cd spotify-skip-tracker` and try again.

---

## 8. Fill in the environment variables

Open `.env.local` in a text editor. You need to replace the placeholder values with your real credentials.

Fill in the following variables one at a time:

---

### `SPOTIFY_CLIENT_ID`

Paste the **Client ID** you copied from the Spotify Developer Dashboard in step 2c.

```
SPOTIFY_CLIENT_ID=414bee9f9066468fbb2655af4f8a918a
```

---

### `SPOTIFY_CLIENT_SECRET`

Paste the **Client Secret** from step 2c.

```
SPOTIFY_CLIENT_SECRET=7fd31f3517b340b593de13d842943af9
```

---

### `DATABASE_URL`

Paste the full connection string you copied from Neon in step 3c.

```
DATABASE_URL=postgresql://neondb_owner:password@ep-something.aws.neon.tech/neondb?sslmode=require
```

> Keep the entire string on one line. Do not wrap it.

---

### `TOKEN_ENCRYPTION_KEY`

This key encrypts your Spotify refresh token before it is stored in the database. Generate it by running this command in your terminal (with the virtual environment active):

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**What you should see:** A string like:
```
n3Ru5DgOdw8em6pVgqF2JLIdCPRs35xkuEBfveAnMjU=
```

Paste that value into `.env.local`:

```
TOKEN_ENCRYPTION_KEY=n3Ru5DgOdw8em6pVgqF2JLIdCPRs35xkuEBfveAnMjU=
```

> Save this key. If you lose it, tokens stored in the database cannot be decrypted and all users will need to re-authenticate.

---

### `SECRET_KEY`

This key signs Flask session cookies. Replace the placeholder with any long random string:

```
SECRET_KEY=my-long-random-secret-abc123
```

Alternatively, generate one with:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

### `REDIRECT_URI_WEB`

Leave this as-is for local development:

```
REDIRECT_URI_WEB=http://127.0.0.1:5000/api/auth/callback
```

---

### `FRONTEND_URL`

Leave this as-is for local development:

```
FRONTEND_URL=http://localhost:5173
```

---

**After filling in all values, save the file.**

📷 **Skjermbilde:** `.env.local` open in a text editor with real values filled in (blur or redact the secrets)

---

## 9. Authenticate with Spotify

This step runs a one-time browser-based login that gives the tracker permission to read your Spotify playback history.

Run the following command, replacing the placeholders with your actual credentials from step 2c:

```bash
python3 -m spotify_skip_tracker setup \
  --client-id YOUR_CLIENT_ID \
  --client-secret YOUR_CLIENT_SECRET
```

**Example:**
```bash
python3 -m spotify_skip_tracker setup \
  --client-id 414bee9f9066468fbb2655af4f8a918a \
  --client-secret 7fd31f3517b340b593de13d842943af9
```

**What you should see:**
1. A browser window opens and shows the Spotify permissions screen
2. Click **Agree** to grant access
3. The browser redirects to `http://127.0.0.1:8888/callback` (this is your local machine — it is normal for it to show a brief blank page or "connection refused" after the redirect)
4. In the terminal, you should see:
   ```
   Innlogging lagret i /Users/you/.spotify_skip_tracker/credentials.json.
   Du kan nå kjøre: python -m spotify_skip_tracker run
   ```

Your credentials are now saved in `~/.spotify_skip_tracker/credentials.json` on your machine.

📷 **Skjermbilde:** Spotify permission screen in the browser

**If this fails:**
- `INVALID_CLIENT` — your Client ID or Client Secret is wrong. Double-check them in the Spotify Developer Dashboard.
- `INVALID_REDIRECT_URI` — `http://127.0.0.1:8888/callback` is not registered in your Spotify app. Go back to step 2b and add it.
- Browser does not open — copy the URL printed in the terminal and open it manually.
- `Tidsavbrudd` (timeout) — you took more than 2 minutes to approve in the browser. Run the command again.

---

## 10. Start the backend

Make sure `DATABASE_URL` is filled in `.env.local` before this step.

```bash
python3 -m spotify_skip_tracker run
```

**What you should see:** Log output similar to:

```
INFO  Starting tracker for user: your_spotify_username
INFO  Database schema OK
INFO  Flask app running on http://0.0.0.0:5000
```

The terminal stays running. **Do not close it.** Open a second terminal window for the next steps.

📷 **Skjermbilde:** Terminal showing Flask startup output

**If this fails:**
- `could not connect to server` or `connection refused` — `DATABASE_URL` is missing or wrong. Check `.env.local` and verify the Neon connection string is correct.
- `ModuleNotFoundError` — the virtual environment is not active. Open a new terminal, navigate to the project folder, run `source venv/bin/activate`, then try again.
- `No credentials found` — step 9 did not complete successfully. Re-run the `setup` command.

---

## 11. Install frontend dependencies

Open a **second terminal window**. Navigate to the project folder, then into the `frontend` subfolder:

```bash
cd spotify-skip-tracker/frontend
```

Install the Node.js packages:

```bash
npm install
```

**What you should see:** npm downloads packages and prints a summary ending with something like:
```
added 154 packages in 30s
```

This may take 30–60 seconds.

**If this fails:**
- `npm: command not found` — Node.js is not installed or not on your PATH. See step 1b.
- `ERESOLVE` or dependency conflicts — try `npm install --legacy-peer-deps`.

---

## 12. Start the frontend

Still in the `frontend` folder, run:

```bash
npm run dev
```

**What you should see:**

```
  VITE v8.x ready in 500ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

The terminal stays running. **Do not close it.**

📷 **Skjermbilde:** Vite dev server startup output in the terminal

**If this fails:**
- `sh: vite: command not found` — `npm install` did not complete. Run it again.
- Port 5173 already in use — another process is using the port. Stop the other process, or run `npm run dev -- --port 5174` to use a different port.

---

## 13. Log in and verify

Open your browser and go to:

```
http://localhost:5173
```

**What you should see:** The Spotify Skip Tracker login screen.

📷 **Skjermbilde:** Login screen in the browser

Click **Log in with Spotify**. You will be redirected to Spotify's login page. After approving, you are redirected back to the dashboard.

**What you should see on the dashboard:**
- A "Now Playing" widget (shows nothing if Spotify is not currently playing)
- Statistic cards (will show zeros if no plays are recorded yet)
- Charts (will be empty until the tracker has collected some data)

📷 **Skjermbilde:** Dashboard after first login

> The tracker starts collecting data immediately. Play some music on Spotify, wait a minute or two, then refresh the page to see your first entries.

**If the login fails:**
- `redirect_uri_mismatch` — `http://127.0.0.1:5000/api/auth/callback` is not registered in your Spotify app. Go back to step 2b and add it.
- Blank page or 502 error — the backend is not running. Check the first terminal window (step 10) for errors.
- CORS error in the browser console — `FRONTEND_URL` in `.env.local` does not match `http://localhost:5173`. Correct it and restart the backend.

---

## Summary: Running the project day-to-day

After installation, here is what you need to do each time you want to use the tracker:

**Terminal 1 — backend:**
```bash
cd spotify-skip-tracker
source venv/bin/activate    # macOS/Linux
python3 -m spotify_skip_tracker run
```

**Terminal 2 — frontend:**
```bash
cd spotify-skip-tracker/frontend
npm run dev
```

Then open http://localhost:5173.

---

## 14. Deploy to production (optional)

For the tracker to run continuously — even when your laptop is off — you need to deploy to Railway (backend) and Vercel (frontend). This section walks through both.

### 14a. Deploy the backend to Railway

**What you need:**
- A [Railway](https://railway.app) account (free tier available)
- Your repository pushed to GitHub

**Steps:**

1. Go to https://railway.app and log in
2. Click **New Project → Deploy from GitHub repo**
3. Select your repository
4. Railway detects `railway.toml` automatically and sets the start command

📷 **Skjermbilde:** Railway "New Project" screen with GitHub repo selected

5. Go to **Variables** and add the following:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Your Neon connection string |
| `SPOTIFY_CLIENT_ID` | From Spotify Developer Dashboard |
| `SPOTIFY_CLIENT_SECRET` | From Spotify Developer Dashboard |
| `TOKEN_ENCRYPTION_KEY` | Your generated Fernet key |
| `SECRET_KEY` | A stable random string |
| `REDIRECT_URI_WEB` | `https://<your-railway-domain>/api/auth/callback` |
| `FRONTEND_URL` | Your Vercel URL (set this after step 14b) |

6. Click **Deploy**. Railway builds and starts the container.

7. Go to **Settings → Networking → Generate Domain** to get your Railway URL (e.g. `your-app.up.railway.app`).

8. In your Spotify Developer App settings, add the new redirect URI:
   `https://your-app.up.railway.app/api/auth/callback`

📷 **Skjermbilde:** Railway Variables panel with all env vars set

---

### 14b. Deploy the frontend to Vercel

**What you need:**
- A [Vercel](https://vercel.com) account (free tier available)

**Steps:**

1. Go to https://vercel.com and log in
2. Click **Add New → Project**
3. Import your GitHub repository
4. Vercel detects `vercel.json` automatically. No build configuration changes needed.
5. Go to **Environment Variables** and add:

| Variable | Value |
|---|---|
| *(none required)* | The frontend resolves the API URL automatically |

6. Click **Deploy**

7. After deployment, copy your Vercel URL (e.g. `https://spotify-skip-tracker.vercel.app`)

8. Go back to Railway and update the `FRONTEND_URL` variable to your Vercel URL

9. Redeploy Railway (click **Redeploy** or push a commit)

📷 **Skjermbilde:** Vercel deployment screen

---

### 14c. First login after deployment

Navigate to `https://your-app.up.railway.app/api/auth/login` in your browser. Log in with Spotify. This stores your token in the Neon database and starts the background tracker thread.

After that, all future visits should go to your Vercel frontend URL.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `pip: command not found` | venv not active | Run `source venv/bin/activate` |
| `ModuleNotFoundError` | venv not active | Run `source venv/bin/activate` |
| `could not connect to server` | Wrong DATABASE_URL | Re-check Neon connection string |
| `INVALID_REDIRECT_URI` | URI not in Spotify app | Add URI in Spotify Developer Dashboard |
| `redirect_uri_mismatch` | URI not in Spotify app | Add `http://127.0.0.1:5000/api/auth/callback` |
| Dashboard blank / 502 | Backend not running | Check terminal 1 for errors |
| CORS error in browser | FRONTEND_URL mismatch | Match FRONTEND_URL to the URL in your browser |
| Charts empty | No data collected yet | Play music and wait a few minutes |
