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
        """Convert audio using ElevenLabs and stream playback immediately."""
        try:
            import time
            start_time = time.time()
            print(f"{colorama.Fore.CYAN}Sending to API...{colorama.Style.RESET_ALL}", end=" ", flush=True)
            
            # Use PCM format for instant decoding (no MP3 decode overhead)
            # The convert method already returns a streaming generator
            audio_stream = self.client.speech_to_speech.convert(
                voice_id=self.voice_id,
                audio=audio,
                model_id=self.model_id,
                output_format="pcm_22050",  # Raw PCM - no decode needed
                # NOTE: remove_background_noise=True adds 5+ seconds of latency!
                remove_background_noise=False,
                optimize_streaming_latency=4,  # Max latency optimization (deprecated but may help)
            )
            
            # Collect and resample chunks, then stream with minimal delay
            first_chunk_time = None
            chunk_count = 0
            all_samples = []
            all_audio_bytes = []
            
            for chunk in audio_stream:
                if chunk:
                    if first_chunk_time is None:
                        first_chunk_time = time.time()
                        latency = (first_chunk_time - start_time) * 1000
                        print(f"{colorama.Fore.GREEN}First chunk in {latency:.0f}ms{colorama.Style.RESET_ALL}", end=" ", flush=True)
                    
                    # Immediately convert and resample each chunk
                    samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
                    resampled = self._resample(samples, self.api_sample_rate, self.output_sample_rate)
                    all_samples.append(resampled)
                    all_audio_bytes.append(chunk)
                    chunk_count += 1
                    
                    # Start playback after first few chunks to avoid underrun
                    if chunk_count == 3 and len(all_samples) > 0:
                        # Combine what we have so far and start playing
                        initial_audio = np.concatenate(all_samples)
                        print(f"(streaming...)", end=" ", flush=True)
                        sd.play(initial_audio, samplerate=self.output_sample_rate, device=self.output_device)
                        all_samples = []  # Clear, we'll append remaining
            
            # If we started early, queue remaining audio
            if chunk_count > 3 and len(all_samples) > 0:
                remaining = np.concatenate(all_samples)
                # Wait for initial playback, then play rest
                sd.wait()
                if len(remaining) > 0:
                    sd.play(remaining, samplerate=self.output_sample_rate, device=self.output_device)
                    sd.wait()
            elif len(all_samples) > 0:
                # Short audio - play all at once
                all_audio = np.concatenate(all_samples)
                print(f"(playing...)", end=" ", flush=True)
                sd.play(all_audio, samplerate=self.output_sample_rate, device=self.output_device)
                sd.wait()
            else:
                sd.wait()  # Wait for any ongoing playback
            
            total_time = (time.time() - start_time) * 1000
            print(f"{colorama.Fore.GREEN}Done! ({chunk_count} chunks, {total_time:.0f}ms){colorama.Style.RESET_ALL}")
            
            # Save for debugging (optional, in background)
            if all_audio_bytes:
                self._save_debug_audio(b''.join(all_audio_bytes))
            
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
