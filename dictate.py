import whisper
import sounddevice as sd
import numpy as np
from pynput import keyboard
from pynput.keyboard import Controller
import queue
import tempfile
import scipy.io.wavfile as wav
import os
import torch
import platform
import sys
import time
import pyperclip

# Fix Windows console encoding for emoji support
def safe_print(*args, **kwargs):
    """Print function that handles encoding errors on Windows"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Fallback to ASCII-safe output
        message = ' '.join(str(arg) for arg in args)
        ascii_message = message.encode('ascii', 'replace').decode('ascii')
        print(ascii_message, **kwargs)

if platform.system() == "Windows":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass  # pythonw.exe doesn't have a console, ignore encoding errors

# Configuration - Platform-specific hotkeys
SYSTEM = platform.system()
if SYSTEM == "Windows":
    HOTKEY = keyboard.Key.f9  # F9 key on Windows
    HOTKEY_NAME = "F9"
elif SYSTEM == "Darwin":  # macOS
    HOTKEY = keyboard.Key.cmd_r  # Right Command key on macOS
    HOTKEY_NAME = "Right Command"
else:  # Linux or other
    HOTKEY = keyboard.Key.alt_r  # Right Alt key as fallback
    HOTKEY_NAME = "Right Alt"

MODEL_SIZE = "turbo"  # Fastest model with high accuracy 

# INTELLIGENT DEVICE DETECTION
# 1. Try NVIDIA GPU (CUDA)
if torch.cuda.is_available():
    device = "cuda"
    safe_print(f"✅ Using NVIDIA GPU ({torch.cuda.get_device_name(0)})")
# 2. Try Apple Silicon GPU (MPS)
elif torch.backends.mps.is_available():
    device = "mps"
    safe_print("✅ Using Apple Silicon GPU (MPS)")
# 3. Fallback to CPU
else:
    device = "cpu"
    safe_print("⚠️ GPU not found. Using CPU (slower).")

safe_print(f"Platform: {SYSTEM}")
safe_print(f"Loading {MODEL_SIZE} model on {device}...")
# Time model loading
startup_start = time.perf_counter()
model = whisper.load_model(MODEL_SIZE, device=device)
startup_time = time.perf_counter() - startup_start
safe_print(f"Model loaded in {startup_time:.2f}s. Hold {HOTKEY_NAME} to dictate.")



q = queue.Queue()
kb_controller = Controller()

def callback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if status:
        print(status)
    q.put(indata.copy())

def on_press(key):
    if key == HOTKEY:
        # Start recording
        global recording
        if not recording:
            recording = True
            print("Recording...")
            global stream
            stream = sd.InputStream(callback=callback, channels=1, samplerate=16000)
            stream.start()

def on_release(key):
    global recording, stream
    if key == HOTKEY and recording:
        # Start total processing timer
        total_start = time.perf_counter()
        
        print("Processing...")
        recording = False
        stream.stop()
        stream.close()

        # Time audio collection
        collect_start = time.perf_counter()
        data = []
        while not q.empty():
            data.append(q.get())
        collect_time = time.perf_counter() - collect_start

        if not data:
            return

        # Time audio processing
        process_start = time.perf_counter()
        # Flatten and save to temporary file
        audio_data = np.concatenate(data, axis=0)
        # Normalize audio
        audio_data = audio_data.flatten().astype(np.float32)

        # Save to temporary WAV file (ffmpeg will handle format conversion)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav.write(tmp.name, 16000, audio_data)
            tmp_path = tmp.name
        process_time = time.perf_counter() - process_start

        # Time transcription
        transcribe_start = time.perf_counter()
        result = model.transcribe(tmp_path, fp16=False) # fp16=False for CPU
        text = result['text'].strip()
        transcribe_time = time.perf_counter() - transcribe_start

        # Delete temp file
        os.remove(tmp_path)

        if text:
            # Time typing/pasting
            typing_start = time.perf_counter()
            # Add a small delay to ensure the application has focus
            time.sleep(0.1)
            
            # Print what we're about to type (for debugging)
            print(f"Transcribed: {repr(text)}")  # Using repr to see exact characters
            print(f"Text length: {len(text)} characters")
            
            # Use clipboard paste method (cross-platform)
            # This preserves the original clipboard content
            original_clipboard = pyperclip.paste()
            try:
                # Copy text to clipboard
                pyperclip.copy(text + " ")
                # Paste using platform-appropriate modifier key
                if SYSTEM == "Darwin":  # macOS
                    kb_controller.press(keyboard.Key.cmd)
                    kb_controller.press('v')
                    kb_controller.release('v')
                    kb_controller.release(keyboard.Key.cmd)
                else:  # Windows/Linux
                    kb_controller.press(keyboard.Key.ctrl)
                    kb_controller.press('v')
                    kb_controller.release('v')
                    kb_controller.release(keyboard.Key.ctrl)
                # Small delay to ensure paste completes
                time.sleep(0.05)
                # Restore original clipboard
                pyperclip.copy(original_clipboard)
            except Exception as e:
                print(f"Error pasting text: {e}")
                # Fallback to direct typing
                try:
                    kb_controller.type(text + " ")
                except Exception as e2:
                    print(f"Error typing text: {e2}")
                    print(f"Text that failed: {repr(text)}")
            typing_time = time.perf_counter() - typing_start
            
            # Calculate total time
            total_time = time.perf_counter() - total_start
            
            # Print timing information
            print(f"\n⏱️  Timing breakdown:")
            print(f"   Audio collection: {collect_time*1000:.1f}ms")
            print(f"   Audio processing: {process_time*1000:.1f}ms")
            print(f"   Transcription:    {transcribe_time:.2f}s")
            print(f"   Typing/pasting:   {typing_time*1000:.1f}ms")
            print(f"   Total time:        {total_time:.2f}s\n")

recording = False

# Listen for hotkeys
with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()