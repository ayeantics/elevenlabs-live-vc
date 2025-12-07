import numpy as np
import sounddevice as sd
import threading
import time
import colorama
from collections import deque

from src.settings.audio import AudioSettings


class AudioRecorder:
    def __init__(self, settings: AudioSettings):
        self.settings = settings
        self.is_recording = False
        self.audio_data = []
        self.stream = None
        
        # VAD settings
        self.vad_enabled = settings.mode == 1  # mode 1 = automatic
        self.silence_threshold = 0.015  # RMS threshold for voice detection (lowered for sensitivity)
        self.silence_duration = 1.2  # Seconds of silence before stopping
        self.min_recording_duration = 0.3  # Minimum recording length in seconds
        self.pre_buffer_duration = 0.5  # Seconds of audio to keep before voice detected
        
        # VAD state
        self.last_voice_time = 0
        self.recording_start_time = 0
        self.vad_callback = None  # Callback when VAD stops recording
        self._vad_thread = None
        self._stop_vad = False
        self.voice_detected = False  # Track if we've detected voice in this session
        
        # Pre-buffer for capturing audio before voice is detected
        # Calculate buffer size: pre_buffer_duration * sample_rate / chunk_size
        # Default chunk size is about 1024 samples at 48kHz
        self.pre_buffer_chunks = int(self.pre_buffer_duration * settings.sample_rate / 1024) + 5
        self.pre_buffer = deque(maxlen=self.pre_buffer_chunks)

    @classmethod
    def from_env(cls):
        return cls(AudioSettings.from_env())

    def set_vad_callback(self, callback):
        """Set callback function to be called when VAD detects end of speech."""
        self.vad_callback = callback

    def get_audio_data(self) -> np.ndarray:
        return self.audio_data

    def _calculate_rms(self, audio_chunk):
        """Calculate RMS (volume level) of audio chunk."""
        return np.sqrt(np.mean(audio_chunk ** 2))

    def callback(self, indata, frames, time_info, status):
        audio_copy = indata.copy()
        
        if self.vad_enabled:
            rms = self._calculate_rms(audio_copy)
            
            if not self.voice_detected:
                # Keep filling pre-buffer until voice is detected
                self.pre_buffer.append(audio_copy)
                
                if rms > self.silence_threshold:
                    # Voice detected! Start actual recording with pre-buffer
                    self.voice_detected = True
                    self.is_recording = True
                    self.recording_start_time = time.time()
                    self.last_voice_time = time.time()
                    
                    # Add pre-buffer to audio data
                    self.audio_data = list(self.pre_buffer)
                    print(f"\n{colorama.Fore.GREEN}[VAD] Voice detected, recording...{colorama.Style.RESET_ALL}")
            else:
                # We're actively recording
                if self.is_recording:
                    self.audio_data.append(audio_copy)
                    
                    if rms > self.silence_threshold:
                        self.last_voice_time = time.time()
        else:
            # Manual mode - just record if is_recording is True
            if self.is_recording:
                self.audio_data.append(audio_copy)

    def _vad_monitor(self):
        """Background thread to monitor for silence and stop recording."""
        while not self._stop_vad:
            time.sleep(0.1)
            
            if self._stop_vad:
                break
            
            if not self.voice_detected:
                continue
                
            if not self.is_recording:
                continue
                
            current_time = time.time()
            recording_duration = current_time - self.recording_start_time
            silence_time = current_time - self.last_voice_time
            
            # Stop if we've had enough silence after minimum recording duration
            if recording_duration > self.min_recording_duration and silence_time > self.silence_duration:
                print(f"\n{colorama.Fore.YELLOW}[VAD] Silence detected, processing...{colorama.Style.RESET_ALL}")
                self.stop()
                if self.vad_callback:
                    self.vad_callback()
                break

    def start(self):
        """Start recording (manual mode)."""
        if not self.is_recording:
            self.is_recording = True
            self.audio_data = []
            self.recording_start_time = time.time()
            self.last_voice_time = time.time()
            self._stop_vad = False
            self.voice_detected = True  # In manual mode, we're always "voice detected"

            self.stream = sd.InputStream(
                callback=self.callback,
                channels=self.settings.channels,
                samplerate=self.settings.sample_rate,
                dtype='float32'
            )
            self.stream.start()
            
            # Start VAD monitoring thread if in automatic mode
            if self.vad_enabled:
                self._vad_thread = threading.Thread(target=self._vad_monitor, daemon=True)
                self._vad_thread.start()

    def stop(self):
        if self.stream is not None:
            self._stop_vad = True
            self.stream.stop()
            self.stream.close()
            self.stream = None
            self.is_recording = False
            self.voice_detected = False

    def start_continuous(self):
        """Start continuous listening for VAD mode."""
        if self.vad_enabled:
            self.audio_data = []
            self.pre_buffer.clear()
            self.voice_detected = False
            self.is_recording = False
            self._stop_vad = False
            
            print(f"{colorama.Fore.GREEN}[VAD] Listening for voice...{colorama.Style.RESET_ALL}")
            
            self.stream = sd.InputStream(
                callback=self.callback,
                channels=self.settings.channels,
                samplerate=self.settings.sample_rate,
                dtype='float32'
            )
            self.stream.start()
            
            # Start VAD monitoring thread
            self._vad_thread = threading.Thread(target=self._vad_monitor, daemon=True)
            self._vad_thread.start()
