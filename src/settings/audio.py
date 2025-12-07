import os

class AudioSettings:
    def __init__(self, mode: int = 0, sample_rate=48000, channels=1, input_device=None):
        self.mode = mode
        self.sample_rate = sample_rate
        self.channels = channels
        self.input_device = input_device  # Device index or None for default

    def valid_modes(self):
        return [0, 1]

    @classmethod
    def from_env(cls, input_device=None):
        return cls(
            mode=int(os.getenv("MODE", 0)),
            sample_rate=int(os.getenv("SAMPLE_RATE", 48000)),
            channels=int(os.getenv("CHANNELS", 1)),
            input_device=input_device
        )
