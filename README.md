# 🎙️ Learncast

> Turn any class transcript into a spoken audio recap — in minutes.

## What it does

Learncast takes a class transcript, PDF, or article URL and transforms it into a 
personalised podcast-style audio recap using a 3-step AI pipeline.

## How it works

1. **Extract** — pulls every concept from the transcript
2. **Describe** — explains each concept using Feynman-layered breakdowns
3. **Write & Speak** — generates a natural podcast script and converts it to audio

## Features

- 📄 Upload PDF, .txt, or paste transcript directly
- 🌐 Paste any article URL
- 🎤 Choose Female or Male voice
- 😄 Toggle lively mode for jokes and energy
- ✅ Key points, quiz questions, and full script included
- ⏱️ Audio capped at 15 minutes

## Setup

1. Clone the repo
2. Install dependencies:
   pip install -r requirements.txt
3. Add your OpenAI API key to a .env file:
   OPENAI_API_KEY=your_key_here
4. Run:
   python src/main.py
5. Open http://localhost:7860

## Tech stack

- Python
- Gradio — UI
- OpenAI GPT-4o mini — script generation
- OpenAI TTS — audio generation
- PyPDF2 — PDF parsing

## Built by

Ironhack AI Bootcamp — Week 1 Project