from io import BytesIO
import os
import numpy as np
import sounddevice as sd
from elevenlabs.client import ElevenLabs
import colorama


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
    def __init__(self, api_key, voice_id, output_device=None):
        self.client = ElevenLabs(api_key=api_key)
        self.voice_id = voice_id
        self.output_device = output_device
        self.sample_rate = 44100  # ElevenLabs default output sample rate
        
        if output_device is not None:
            print(f"{colorama.Fore.GREEN}Audio output routed to: {sd.query_devices(output_device)['name']}{colorama.Style.RESET_ALL}")
        else:
            print(f"{colorama.Fore.YELLOW}Warning: VB-Cable not found, using default output{colorama.Style.RESET_ALL}")

    @classmethod
    def from_env(cls):
        # Auto-detect VB-Cable
        device_id, device_name = find_vb_cable_device()
        if device_id is not None:
            print(f"{colorama.Fore.CYAN}Found VB-Cable: {device_name} (Device ID: {device_id}){colorama.Style.RESET_ALL}")
        
        return cls(
            os.getenv("API_KEY", None),
            os.getenv("VOICE_ID", None),
            output_device=device_id
        )

    def convert_audio(self, audio: BytesIO):
        """Convert audio using ElevenLabs and play to VB-Cable."""
        try:
            print(f"{colorama.Fore.CYAN}Sending audio to ElevenLabs API...{colorama.Style.RESET_ALL}")
            
            # Using .convert() based on the latest SDK documentation
            audio_stream = self.client.speech_to_speech.convert(
                voice_id=self.voice_id,
                audio=audio,
                model_id="eleven_multilingual_sts_v2",
                output_format="mp3_44100_128",
                remove_background_noise=True,
            )
            
            print(f"{colorama.Fore.CYAN}Receiving audio stream from API...{colorama.Style.RESET_ALL}")
            
            # Collect all audio chunks from the stream
            audio_chunks = []
            for chunk in audio_stream:
                if chunk:
                    audio_chunks.append(chunk)
            
            print(f"{colorama.Fore.CYAN}Received {len(audio_chunks)} chunks, total {sum(len(c) for c in audio_chunks)} bytes{colorama.Style.RESET_ALL}")
            
            if not audio_chunks:
                print(f"{colorama.Fore.RED}No audio received from ElevenLabs{colorama.Style.RESET_ALL}")
                return
            
            # Combine chunks
            audio_bytes = b''.join(audio_chunks)
            
            # Save MP3 to recordings folder for debugging
            import time
            recordings_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "recordings")
            os.makedirs(recordings_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            mp3_path = os.path.join(recordings_dir, f"transformed_{timestamp}.mp3")
            with open(mp3_path, "wb") as f:
                f.write(audio_bytes)
            print(f"{colorama.Fore.CYAN}Saved MP3 to: {mp3_path}{colorama.Style.RESET_ALL}")
            
            # Decode MP3
            from pydub import AudioSegment
            print(f"{colorama.Fore.CYAN}Decoding MP3 audio...{colorama.Style.RESET_ALL}")
            audio_segment = AudioSegment.from_mp3(BytesIO(audio_bytes))
            
            # Convert to numpy array
            samples = np.array(audio_segment.get_array_of_samples())
            if audio_segment.channels == 2:
                samples = samples.reshape((-1, 2))
            
            # Normalize to float32
            samples = samples.astype(np.float32) / 32768.0
            
            print(f"{colorama.Fore.GREEN}Playing transformed audio to VB-Cable ({audio_segment.duration_seconds:.1f}s)...{colorama.Style.RESET_ALL}")
            
            # Play to VB-Cable
            sd.play(samples, samplerate=audio_segment.frame_rate, device=self.output_device)
            sd.wait()
            
            print(f"{colorama.Fore.GREEN}Done! Audio sent to VB-Cable.{colorama.Style.RESET_ALL}")
            
        except ImportError:
            print(f"{colorama.Fore.RED}pydub not installed. Run: pip install pydub{colorama.Style.RESET_ALL}")
        except Exception as e:
            print(f"{colorama.Fore.RED}Error: {type(e).__name__}: {e}{colorama.Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
