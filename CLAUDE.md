# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a voice dictation tool that uses OpenAI Whisper for speech-to-text transcription. It's a single-file Python application (`dictate.py`) that listens for a hotkey, records audio while the key is held, transcribes the audio using Whisper, and types the transcribed text.

## Environment Setup

The project uses a Python virtual environment located at `.venv/`.

Activate the virtual environment:
```bash
source .venv/bin/activate
```

Install dependencies (if needed):
```bash
pip install openai-whisper sounddevice scipy pynput pyperclip
```

## Running the Application

```bash
source .venv/bin/activate
python dictate.py
```

The application will:
1. Load the Whisper model (configured as "base" by default)
2. Listen for the F8 key (configurable via `HOTKEY` constant)
3. Record audio while F8 is held down
4. Transcribe the audio when F8 is released
5. Type the transcribed text into the active application

## Architecture

The application uses an event-driven architecture with the following key components:

- **Audio Recording**: Uses `sounddevice` with a callback-based streaming approach. Audio chunks are pushed to a queue as they're captured.
- **Hotkey Listening**: Uses `pynput.keyboard.Listener` to detect key press/release events globally across the OS.
- **Speech-to-Text**: Audio is saved to a temporary WAV file and transcribed using the Whisper model. The model is loaded once at startup and reused for all transcriptions.
- **Text Output**: Uses `pynput.keyboard.Controller` to simulate keyboard input and type the transcribed text.

### Key Global State

- `recording`: Boolean flag indicating whether audio is currently being recorded
- `stream`: The active audio input stream (created/destroyed on each recording session)
- `q`: Queue holding audio chunks during recording
- `model`: The loaded Whisper model (persists for the lifetime of the application)

## Configuration

Constants in `dictate.py`:
- `HOTKEY`: Key to hold for dictation (default: `keyboard.Key.f8`)
- `MODEL_SIZE`: Whisper model size (options: 'tiny', 'base', 'small', 'medium', 'large')

Audio settings (hardcoded in the implementation):
- Sample rate: 16000 Hz
- Channels: 1 (mono)

## Platform Notes

This code is macOS-specific due to the `pynput` dependency requiring PyObjC frameworks. The audio recording and Whisper transcription components are cross-platform, but keyboard input simulation may behave differently on other operating systems.
