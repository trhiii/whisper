import whisper
import sounddevice as sd
import numpy as np
from pynput import keyboard
from pynput.keyboard import Controller
import queue
import tempfile
import scipy.io.wavfile as wav
import os
import torch  # <--- Add this import at the very top

# ... existing imports ...

# Configuration
HOTKEY = keyboard.Key.cmd_r  # Right Command key (like macOS dictation)
MODEL_SIZE = "turbo" 

# INTELLIGENT DEVICE DETECTION
# 1. Try NVIDIA GPU (CUDA)
if torch.cuda.is_available():
    device = "cuda"
    print(f"✅ Using NVIDIA GPU ({torch.cuda.get_device_name(0)})")
# 2. Try Apple Silicon GPU (MPS)
elif torch.backends.mps.is_available():
    device = "mps"
    print("✅ Using Apple Silicon GPU (MPS)")
# 3. Fallback to CPU
else:
    device = "cpu"
    print("⚠️ GPU not found. Using CPU (slower).")

print(f"Loading {MODEL_SIZE} model on {device}...")
# Pass the 'device' parameter here
model = whisper.load_model(MODEL_SIZE, device=device) 
print(f"Model loaded. Hold {HOTKEY} to dictate.")



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
        print("Processing...")
        recording = False
        stream.stop()
        stream.close()

        # Collect audio data
        data = []
        while not q.empty():
            data.append(q.get())

        if not data:
            return

        # Flatten and save to temporary file
        audio_data = np.concatenate(data, axis=0)
        # Normalize audio
        audio_data = audio_data.flatten().astype(np.float32)

        # Whisper handles raw numpy arrays effectively now, but saving to file is robust
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav.write(tmp.name, 16000, audio_data)
            tmp_path = tmp.name

        # Transcribe
        result = model.transcribe(tmp_path, fp16=False) # fp16=False for CPU
        text = result['text'].strip()

        # Delete temp file
        os.remove(tmp_path)

        if text:
            print(f"Typing: {text}")
            kb_controller.type(text + " ")

recording = False

# Listen for hotkeys
with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()