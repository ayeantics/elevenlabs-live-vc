from io import BytesIO
import os
import numpy as np
import sounddevice as sd
from elevenlabs.client import ElevenLabs
import colorama
import threading
import queue


def find_vb_cable_device():
    """Find VB-Cable Input device for output routing."""
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        device_name = device['name'].lower()
        # VB-Cable Input is what we output TO (it appears as an output device)
        if 'cable input' in device_name and device['max_output_channels'] > 0:
            return i, device['name']
    return None, None


class ElevenLabsClient:
    def __init__(self, api_key, voice_id, output_device=None, model_id=None):
        self.client = ElevenLabs(api_key=api_key)
        self.voice_id = voice_id
        self.output_device = output_device
        self.model_id = model_id or "eleven_english_sts_v2"
        self.api_sample_rate = 22050  # API output rate
        self.output_sample_rate = 48000  # VB-Cable requires 48kHz
        
        if output_device is not None:
            print(f"{colorama.Fore.GREEN}Audio output routed to: {sd.query_devices(output_device)['name']}{colorama.Style.RESET_ALL}")
        else:
            print(f"{colorama.Fore.YELLOW}Warning: VB-Cable not found, using default output{colorama.Style.RESET_ALL}")
        
        print(f"{colorama.Fore.CYAN}Using model: {self.model_id}{colorama.Style.RESET_ALL}")

    @classmethod
    def from_env(cls):
        # Auto-detect VB-Cable
        device_id, device_name = find_vb_cable_device()
        if device_id is not None:
            print(f"{colorama.Fore.CYAN}Found VB-Cable: {device_name} (Device ID: {device_id}){colorama.Style.RESET_ALL}")
        
        return cls(
            os.getenv("API_KEY", None),
            os.getenv("VOICE_ID", None),
            output_device=device_id,
            model_id=os.getenv("MODEL_ID", "eleven_english_sts_v2")
        )

    def _resample(self, samples, orig_rate, target_rate):
        """Fast linear resampling."""
        if orig_rate == target_rate:
            return samples
        ratio = target_rate / orig_rate
        new_length = int(len(samples) * ratio)
        indices = np.linspace(0, len(samples) - 1, new_length)
        return np.interp(indices, np.arange(len(samples)), samples).astype(np.float32)

    def convert_audio(self, audio: BytesIO):
        """Convert audio using ElevenLabs and play to VB-Cable with streaming."""
        try:
            print(f"{colorama.Fore.CYAN}Sending to API...{colorama.Style.RESET_ALL}", end=" ", flush=True)
            
            # Use PCM format for instant decoding (no MP3 decode overhead)
            audio_stream = self.client.speech_to_speech.convert(
                voice_id=self.voice_id,
                audio=audio,
                model_id=self.model_id,
                output_format="pcm_22050",  # Raw PCM - no decode needed
                remove_background_noise=True,
            )
            
            # Collect chunks with progress indicator
            audio_chunks = []
            chunk_count = 0
            for chunk in audio_stream:
                if chunk:
                    audio_chunks.append(chunk)
                    chunk_count += 1
                    if chunk_count % 10 == 0:
                        print(".", end="", flush=True)
            
            print(f" {len(audio_chunks)} chunks", flush=True)
            
            if not audio_chunks:
                print(f"{colorama.Fore.RED}No audio received{colorama.Style.RESET_ALL}")
                return
            
            # Combine chunks - PCM is raw 16-bit signed integers
            audio_bytes = b''.join(audio_chunks)
            
            # Convert PCM bytes to numpy array (16-bit signed, little-endian)
            samples = np.frombuffer(audio_bytes, dtype=np.int16)
            
            # Normalize to float32
            samples = samples.astype(np.float32) / 32768.0
            
            # Resample 22050Hz -> 48000Hz for VB-Cable
            samples = self._resample(samples, self.api_sample_rate, self.output_sample_rate)
            
            duration = len(samples) / self.output_sample_rate
            print(f"{colorama.Fore.GREEN}Playing ({duration:.1f}s)...{colorama.Style.RESET_ALL}", end=" ", flush=True)
            
            # Play to VB-Cable
            sd.play(samples, samplerate=self.output_sample_rate, device=self.output_device)
            sd.wait()
            
            print(f"{colorama.Fore.GREEN}Done!{colorama.Style.RESET_ALL}")
            
            # Save for debugging (optional, in background)
            self._save_debug_audio(audio_bytes)
            
        except Exception as e:
            print(f"{colorama.Fore.RED}Error: {type(e).__name__}: {e}{colorama.Style.RESET_ALL}")
            import traceback
            traceback.print_exc()

    def _save_debug_audio(self, audio_bytes):
        """Save audio to file in background for debugging."""
        def save():
            try:
                import time
                recordings_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "recordings")
                os.makedirs(recordings_dir, exist_ok=True)
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                pcm_path = os.path.join(recordings_dir, f"transformed_{timestamp}.pcm")
                with open(pcm_path, "wb") as f:
                    f.write(audio_bytes)
            except:
                pass
        
        threading.Thread(target=save, daemon=True).start()
