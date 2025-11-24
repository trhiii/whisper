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
import subprocess

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
# 1. Try NVIDIA GPU (CUDA) - works on Windows, Linux, and some Macs
device = "cpu"  # Default fallback
if torch.cuda.is_available():
    device = "cuda"
    safe_print(f"Using NVIDIA GPU ({torch.cuda.get_device_name(0)})")
# 2. Try Apple Silicon GPU (MPS) - macOS only
elif SYSTEM == "Darwin":
    try:
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = "mps"
            safe_print("Using Apple Silicon GPU (MPS)")
        else:
            safe_print("Warning: GPU not found. Using CPU (slower).")
    except (AttributeError, Exception):
        safe_print("Warning: GPU not found. Using CPU (slower).")
# 3. Fallback to CPU
else:
    safe_print("Warning: GPU not found. Using CPU (slower).")

safe_print(f"Platform: {SYSTEM}")

# List available audio input devices
safe_print("\nAvailable audio input devices:")
try:
    devices = sd.query_devices()
    input_devices = [(i, d) for i, d in enumerate(devices) if d['max_input_channels'] > 0]
    for idx, dev_info in input_devices:
        default_marker = " (DEFAULT)" if dev_info['name'] == sd.query_devices(kind='input')['name'] else ""
        safe_print(f"   [{idx}] {dev_info['name']}{default_marker}")
except Exception as e:
    safe_print(f"   Could not list devices: {e}")

safe_print(f"\nLoading {MODEL_SIZE} model on {device}...")
# Time model loading
startup_start = time.perf_counter()
model = whisper.load_model(MODEL_SIZE, device=device)
startup_time = time.perf_counter() - startup_start
safe_print(f"Model loaded in {startup_time:.2f}s. Hold {HOTKEY_NAME} to dictate.")
if SYSTEM == "Darwin":
    safe_print("Note: On macOS, ensure Terminal/Python has Accessibility permissions")
    safe_print("      (System Settings > Privacy & Security > Accessibility)")



q = queue.Queue()
kb_controller = Controller()

def get_frontmost_app_macos():
    """Get the name of the frontmost application on macOS"""
    if SYSTEM != "Darwin":
        return None
    try:
        script = '''
        tell application "System Events"
            set frontApp to name of first application process whose frontmost is true
            return frontApp
        end tell
        '''
        result = subprocess.run(['osascript', '-e', script], 
                              capture_output=True, text=True, timeout=2, check=False)
        if result.returncode == 0 and result.stdout:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception):
        return None

def activate_app_macos(app_name):
    """Activate a specific application on macOS"""
    if SYSTEM != "Darwin" or not app_name:
        return
    try:
        # Escape quotes in app name to prevent AppleScript injection
        escaped_name = app_name.replace('"', '\\"')
        script = f'''
        tell application "{escaped_name}"
            activate
        end tell
        '''
        subprocess.run(['osascript', '-e', script], 
                      capture_output=True, timeout=2, check=False)
        time.sleep(0.2)  # Give the app time to activate
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception):
        pass

def get_frontmost_window_windows():
    """Get the handle of the frontmost window on Windows"""
    if SYSTEM != "Windows":
        return None
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        return hwnd if hwnd else None
    except ImportError:
        # pywin32 not installed - this is OK, we'll use fallback
        return None
    except Exception:
        return None

def activate_window_windows(hwnd):
    """Activate a specific window on Windows"""
    if SYSTEM != "Windows" or not hwnd:
        return
    try:
        import win32gui
        import win32con
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)  # Give the window time to activate
    except ImportError:
        # pywin32 not installed - this is OK
        pass
    except Exception:
        pass

def callback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if status:
        print(status)
    q.put(indata.copy())

def on_press(key):
    if key == HOTKEY:
        # Start recording
        global recording, previous_window
        if not recording:
            recording = True
            # Store the currently focused window before recording (Windows only)
            # macOS uses simple direct typing, no window switching needed
            if SYSTEM == "Windows":
                previous_window = get_frontmost_window_windows()
            
            # Clear the queue for a fresh recording
            while not q.empty():
                try:
                    q.get_nowait()
                except:
                    break
            safe_print("Recording...")
            global stream
            try:
                # Explicitly use default input device with float32 dtype
                stream = sd.InputStream(
                    callback=callback, 
                    channels=1, 
                    samplerate=16000,
                    dtype='float32'
                )
                stream.start()
            except Exception as e:
                safe_print(f"Error starting audio stream: {e}")
                recording = False

def on_release(key):
    global recording, stream, previous_window
    if key == HOTKEY and recording:
        # Start total processing timer
        total_start = time.perf_counter()
        
        safe_print("Processing...")
        recording = False
        try:
            stream.stop()
            stream.close()
        except Exception as e:
            safe_print(f"Warning: Error stopping stream: {e}")

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
        # Normalize audio to float32 range [-1.0, 1.0]
        audio_data = audio_data.flatten().astype(np.float32)
        
        # Check audio level
        max_amplitude = np.max(np.abs(audio_data))
        audio_duration = len(audio_data) / 16000.0
        safe_print(f"Audio stats: duration={audio_duration:.2f}s, max_amplitude={max_amplitude:.4f}")
        
        if max_amplitude < 0.001:
            safe_print("Warning: Audio level is very low. Check your microphone!")
        elif max_amplitude > 0.95:
            safe_print("Warning: Audio may be clipping!")
        
        # Normalize to prevent clipping (scale to 0.95 max if needed)
        if max_amplitude > 0.95:
            audio_data = audio_data / max_amplitude * 0.95
        
        # Convert to int16 for WAV file (Whisper expects int16 format)
        audio_int16 = (audio_data * 32767).astype(np.int16)

        # Save to temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav.write(tmp.name, 16000, audio_int16)
            tmp_path = tmp.name
        process_time = time.perf_counter() - process_start

        # Time transcription
        transcribe_start = time.perf_counter()
        try:
            result = model.transcribe(tmp_path, fp16=False, language=None) # fp16=False for CPU, language=None for auto-detect
            text = result['text'].strip()
        except Exception as e:
            safe_print(f"Transcription error: {e}")
            text = ""
        transcribe_time = time.perf_counter() - transcribe_start

        # Delete temp file
        try:
            os.remove(tmp_path)
        except:
            pass

        safe_print(f"Raw transcription result: {repr(text)}")
        
        if not text or len(text.strip()) == 0:
            safe_print("Warning: No text transcribed. Check your microphone and try again.")
            return

        if text:
            # Time typing
            typing_start = time.perf_counter()
            
            # Print what we're about to type (for debugging)
            safe_print(f"Typing: {text}")
            
            # Fork: macOS and Windows use different approaches
            # macOS: Simple direct typing (like macos-1.0 that worked)
            # Windows: Try window switching first, then direct typing
            typing_success = False
            
            if SYSTEM == "Darwin":
                # macOS: Use simple direct typing approach from macos-1.0
                # Wait a moment for the app to regain focus after hotkey release
                time.sleep(0.2)
                
                try:
                    # Simple direct typing - this is what worked in macos-1.0
                    kb_controller.type(text + " ")
                    typing_success = True
                    safe_print("Text typed successfully")
                except Exception as e:
                    safe_print(f"Typing failed: {e}")
                    safe_print("Note: On macOS, ensure Terminal/Python has Accessibility permissions")
                    safe_print("      (System Settings > Privacy & Security > Accessibility)")
            
            elif SYSTEM == "Windows":
                # Windows: Try multiple methods to ensure text gets to the right place
                # Method 1: Try to restore focus to previous window
                window_switched = False
                if previous_window:
                    try:
                        import win32gui
                        current_hwnd = win32gui.GetForegroundWindow()
                        # Only switch if it's not already the previous window
                        if current_hwnd != previous_window:
                            safe_print("Restoring focus to previous window...")
                            activate_window_windows(previous_window)
                            time.sleep(0.3)  # Give more time for window to activate
                            window_switched = True
                    except (ImportError, Exception) as e:
                        # pywin32 not available or failed - continue anyway
                        pass
                
                # Method 2: Try clipboard paste first (more reliable on Windows)
                # This preserves the original clipboard content
                try:
                    original_clipboard = pyperclip.paste()
                    # Copy text to clipboard
                    pyperclip.copy(text + " ")
                    # Small delay to ensure clipboard is ready
                    time.sleep(0.1)
                    
                    # If we didn't switch windows, give user a moment to click target app
                    if not window_switched:
                        safe_print("Paste ready. Ensure target application has focus...")
                        time.sleep(0.2)
                    
                    # Paste using Ctrl+V
                    kb_controller.press(keyboard.Key.ctrl)
                    kb_controller.press('v')
                    kb_controller.release('v')
                    kb_controller.release(keyboard.Key.ctrl)
                    # Small delay to ensure paste completes
                    time.sleep(0.1)
                    # Restore original clipboard
                    pyperclip.copy(original_clipboard)
                    typing_success = True
                    safe_print("Text pasted successfully")
                except Exception as e:
                    safe_print(f"Clipboard paste failed: {e}")
                    # Fallback to direct typing
                    try:
                        if not window_switched:
                            safe_print("Trying direct typing...")
                            time.sleep(0.2)
                        kb_controller.type(text + " ")
                        typing_success = True
                        safe_print("Text typed successfully")
                    except Exception as e2:
                        safe_print(f"Direct typing also failed: {e2}")
                        safe_print("Note: Ensure the application has focus and is not blocked by security software")
            
            else:
                # Linux or other - simple direct typing
                time.sleep(0.2)
                try:
                    kb_controller.type(text + " ")
                    typing_success = True
                    safe_print("Text typed successfully")
                except Exception as e:
                    safe_print(f"Typing failed: {e}")
            
            if not typing_success:
                safe_print("Warning: Failed to input text. Check application focus and permissions.")
            
            typing_time = time.perf_counter() - typing_start
            
            # Calculate total time
            total_time = time.perf_counter() - total_start
            
            # Print timing information
            print(f"\nTiming breakdown:")
            print(f"   Audio collection: {collect_time*1000:.1f}ms")
            print(f"   Audio processing: {process_time*1000:.1f}ms")
            print(f"   Transcription:    {transcribe_time:.2f}s")
            print(f"   Typing/pasting:   {typing_time*1000:.1f}ms")
            print(f"   Total time:        {total_time:.2f}s\n")

recording = False
previous_window = None  # Windows only - for window switching

# Listen for hotkeys
with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()