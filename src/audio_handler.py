import colorama
import keyboard
import threading
import time
import os
import glob
from src.audio_processor import AudioProcessor
from src.audio_recorder import AudioRecorder
from src.el_client import ElevenLabsClient


class AudioHandler:
    def __init__(self, recorder: AudioRecorder, processor: AudioProcessor, el_client: ElevenLabsClient):
        self.recorder = recorder
        self.processor = processor
        self.el_client = el_client
        self.is_processing = False  # Prevent overlapping processing
        
        # Set up keyboard handler for manual mode
        keyboard.on_press_key("space", self.handle_recording)
        
        # Set up VAD callback for automatic mode
        if self.recorder.vad_enabled:
            self.recorder.set_vad_callback(self.process_vad_recording)
        
        # Start cleanup thread
        self._start_cleanup_thread()

    @classmethod
    def from_env(cls):
        return cls(
            AudioRecorder.from_env(),
            AudioProcessor.from_env(),
            ElevenLabsClient.from_env()
        )

    def _start_cleanup_thread(self):
        """Start background thread to clean up old recordings."""
        def cleanup_loop():
            recordings_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "recordings")
            while True:
                time.sleep(60)  # Check every minute
                try:
                    if os.path.exists(recordings_dir):
                        now = time.time()
                        for filepath in glob.glob(os.path.join(recordings_dir, "transformed_*.mp3")):
                            file_age = now - os.path.getmtime(filepath)
                            if file_age > 600:  # 10 minutes = 600 seconds
                                os.remove(filepath)
                                print(f"{colorama.Fore.YELLOW}[Cleanup] Deleted old recording: {os.path.basename(filepath)}{colorama.Style.RESET_ALL}")
                except Exception as e:
                    pass  # Silently ignore cleanup errors
        
        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()

    def process_vad_recording(self):
        """Process recording after VAD detects silence."""
        if self.is_processing:
            return
        self._process_audio()
        # Restart listening after processing
        if self.recorder.vad_enabled:
            time.sleep(0.5)  # Brief pause before restarting
            self.recorder.start_continuous()

    def _process_audio(self):
        """Common audio processing logic."""
        self.is_processing = True
        try:
            audio = self.recorder.get_audio_data()
            audio_stream = self.processor.get_audio_stream(audio)
            if audio_stream is None:
                print(f"{colorama.Fore.YELLOW}No audio recorded. Try speaking longer.{colorama.Style.RESET_ALL}")
                return
            self.el_client.convert_audio(audio_stream)
        finally:
            self.is_processing = False

    def handle_recording(self, event):
        if self.is_processing:
            return  # Ignore if already processing
            
        if self.recorder.is_recording:
            print(
                f"\n{colorama.Fore.GREEN}Recording stopped, processing audio...{
                    colorama.Style.RESET_ALL}"
            )
            self.recorder.stop()
            self._process_audio()
            
            # Restart VAD listening if in automatic mode
            if self.recorder.vad_enabled:
                self.recorder.start_continuous()
        else:
            print(
                f"\n{colorama.Fore.GREEN}Start recording, press space to stop...{
                    colorama.Style.RESET_ALL}"
            )
            self.recorder.start()

    def start_vad_mode(self):
        """Start continuous VAD listening mode."""
        if self.recorder.vad_enabled:
            print(f"{colorama.Fore.CYAN}=== VAD Mode Active ==={colorama.Style.RESET_ALL}")
            print(f"{colorama.Fore.CYAN}Speak naturally - recording starts/stops automatically{colorama.Style.RESET_ALL}")
            print(f"{colorama.Fore.CYAN}Press SPACE to manually trigger, Ctrl+C to exit{colorama.Style.RESET_ALL}")
            self.recorder.start_continuous()
