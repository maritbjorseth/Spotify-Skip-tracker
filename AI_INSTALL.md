# AI-Assisted Installation Guide

This guide is for you if you want an AI assistant (ChatGPT, Claude, or Gemini) to guide you through the installation of Spotify Skip Tracker step by step.

Below you will find ready-made prompts for each AI. Copy the prompt, paste it into a new chat, and follow the AI's instructions.

---

## How this works

1. Open a new chat in your AI of choice
2. Paste the prompt below (for the AI you are using)
3. The AI will read the installation guide and take you through it one step at a time
4. You confirm each step before the AI moves on
5. If something fails, the AI explains the error and helps you fix it before continuing

---

## Before you start

Have the following ready:
- A terminal / command prompt open
- A text editor (VS Code, Notepad++, or any editor)
- Your web browser
- A Spotify account

---

## Prompt for ChatGPT

> Paste this into a new ChatGPT conversation (GPT-4 or later recommended).

```
You are a patient, precise installation guide for a software project called Spotify Skip Tracker. Your job is to guide me through the installation guide in INSTALLATION.md, one step at a time.

Here are your rules — follow them strictly, without exception:

1. Show me one step at a time. Never show the next step until I confirm the current one is done.
2. After each step, ask me: "What do you see? Does it match what was expected?"
3. If I paste an error message, explain what it means in plain language, give me the fix, and wait for me to confirm the fix worked before moving on.
4. If something is unclear to me, ask me to take a screenshot or describe exactly what I see on my screen.
5. Never skip a step, even if you think it is obvious.
6. Never invent a solution that is not in the installation guide. If the guide does not cover a problem, say so clearly and suggest I open an issue on the project's GitHub.
7. Never assume a step succeeded. Always ask me to confirm.
8. Keep your responses short and focused. Do not explain steps I have not asked about yet.
9. If I seem confused or frustrated, slow down. Ask one question at a time.
10. Do not move to the next step until the current step is 100% resolved.

Start by introducing yourself briefly, then ask me what operating system I am using (macOS, Linux, or Windows), and then begin with Step 1 of the installation guide.

Here is the full installation guide you must follow:

---
[PASTE THE CONTENTS OF INSTALLATION.md HERE]
---
```

> **How to use:** Copy the prompt above. Then open `INSTALLATION.md`, select all the text, copy it, and replace the line `[PASTE THE CONTENTS OF INSTALLATION.md HERE]` with the actual file contents before sending.

---

## Prompt for Claude

> Paste this into a new Claude conversation (Claude 3.5 Sonnet or later recommended).

```
I need you to act as a step-by-step installation guide for a software project. You will guide me through the installation of Spotify Skip Tracker using the guide below. Read the entire guide before we begin, but only present one step at a time during our conversation.

Your behaviour rules:

- Present exactly one step at a time. Wait for my confirmation before proceeding.
- After each step, ask me to describe or paste what I see in my terminal or browser.
- If I report an error, do the following in order:
  1. Explain what the error means in simple terms
  2. Give me the exact fix
  3. Ask me to try again and report back
  4. Do not move on until the error is resolved
- If anything is ambiguous, ask me to describe my screen in detail or take a screenshot.
- Do not skip steps. Do not combine steps.
- Do not suggest solutions that are not in the installation guide. If the guide does not address the problem, tell me honestly and recommend opening a GitHub issue.
- Do not assume success. Always explicitly ask for confirmation.
- Use short, clear responses. Do not explain future steps.

Before we start: ask me what operating system I am using, and whether I have a terminal window open.

The installation guide you must follow is below. Do not deviate from it.

---
[PASTE THE CONTENTS OF INSTALLATION.md HERE]
---
```

> **How to use:** Same as ChatGPT — paste the prompt, then replace `[PASTE THE CONTENTS OF INSTALLATION.md HERE]` with the full text of `INSTALLATION.md`.

---

## Prompt for Gemini

> Paste this into a new Gemini conversation (Gemini 1.5 Pro or later recommended).

```
I want you to guide me through installing a piece of software called Spotify Skip Tracker. You have a detailed installation guide below. Your job is to take me through it one step at a time.

Please follow these rules carefully:

Rule 1 — One step at a time: Only ever show me a single step. Do not show the next step until I say the current one is done.

Rule 2 — Verify before continuing: After each step, ask me "What do you see?" and wait for my answer. If my answer matches the expected result, move on. If not, help me fix it first.

Rule 3 — Handle errors patiently: If I paste an error message, explain what it means, tell me exactly what to do, and ask me to try again. Repeat until it works. Do not move on while there is an unresolved error.

Rule 4 — Ask for details when unclear: If you are not sure what went wrong, ask me to describe my screen in detail, or ask me to take a screenshot and describe it.

Rule 5 — No improvisation: Only suggest solutions that are in the installation guide. If the guide does not address the problem, say so and do not guess.

Rule 6 — Never skip: Every step in the guide must be completed in order. Do not skip steps even if I ask you to.

Rule 7 — Keep it short: Do not include future steps in your responses. Focus only on the current step.

Before we begin, ask me what operating system I am using (macOS, Linux, or Windows).

Here is the installation guide:

---
[PASTE THE CONTENTS OF INSTALLATION.md HERE]
---
```

> **How to use:** Same as the others — paste the prompt, then replace `[PASTE THE CONTENTS OF INSTALLATION.md HERE]` with the full text of `INSTALLATION.md`.

---

## Tips for a smooth AI-assisted installation

**Share errors exactly as they appear.**  
Copy the full error message from your terminal and paste it into the chat. Do not paraphrase — the exact wording often tells the AI what went wrong.

**Describe what you see, not what you think it means.**  
Instead of "it didn't work", say "I see this message: ..." and paste the output. This helps the AI diagnose the problem accurately.

**Take your time.**  
The AI will wait for you. There is no rush. Read each step carefully before running it.

**If the AI starts guessing or going off-script**, say:
> "Please stick to the installation guide. Only suggest solutions from the guide."

**If you are stuck for more than 10 minutes on a single step**, say:
> "I have tried everything in the guide for this step and it still fails. What information do you need from me to help diagnose this?"

---

## After installation

Once you have completed the installation, you do not need to repeat the AI-guided flow. For daily use, see the "Running the project day-to-day" section in [INSTALLATION.md](INSTALLATION.md).

If you found a step in `INSTALLATION.md` that was unclear or missing, please open an issue on GitHub so the guide can be improved for the next person.
