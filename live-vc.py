import cmd
import os
import argparse
import sounddevice as sd
from src.audio_handler import AudioHandler
import colorama
from dotenv import load_dotenv

load_dotenv()
colorama.init()

banner = """
██╗     ██╗██╗   ██╗███████╗    ██╗   ██╗ ██████╗
██║     ██║██║   ██║██╔════╝    ██║   ██║██╔════╝
██║     ██║██║   ██║█████╗█████╗██║   ██║██║
██║     ██║╚██╗ ██╔╝██╔══╝╚════╝╚██╗ ██╔╝██║
███████╗██║ ╚████╔╝ ███████╗     ╚████╔╝ ╚██████╗
╚══════╝╚═╝  ╚═══╝  ╚══════╝      ╚═══╝   ╚═════╝
"""

description = """Description: A live voice-changer utilizing elevenlabs voice-cloning API.
Author: https://github.com/cavoq
Version: 1.0.0
"""


def find_input_device(name_contains: str):
    """Find input device index by partial name match."""
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0 and name_contains.lower() in dev['name'].lower():
            return i, dev['name']
    return None, None


def select_input_device(args):
    """Select input device based on command-line args or auto-detect."""
    if args.wo_mic:
        idx, name = find_input_device("wo mic")
        if idx is not None:
            print(f"{colorama.Fore.CYAN}Using WO Mic: {name}{colorama.Style.RESET_ALL}")
            return idx
        else:
            print(f"{colorama.Fore.YELLOW}WO Mic not found, falling back to default{colorama.Style.RESET_ALL}")
            return None
    
    if args.microphone:
        idx, name = find_input_device("microphone array")
        if idx is not None:
            print(f"{colorama.Fore.CYAN}Using Microphone Array: {name}{colorama.Style.RESET_ALL}")
            return idx
        else:
            print(f"{colorama.Fore.YELLOW}Microphone Array not found, falling back to default{colorama.Style.RESET_ALL}")
            return None
    
    # Auto-detect: prefer WO Mic if available, else Microphone Array
    idx, name = find_input_device("wo mic")
    if idx is not None:
        print(f"{colorama.Fore.CYAN}Auto-detected WO Mic: {name}{colorama.Style.RESET_ALL}")
        return idx
    
    idx, name = find_input_device("microphone array")
    if idx is not None:
        print(f"{colorama.Fore.CYAN}Auto-detected Microphone: {name}{colorama.Style.RESET_ALL}")
        return idx
    
    print(f"{colorama.Fore.YELLOW}Using default input device{colorama.Style.RESET_ALL}")
    return None


def list_input_devices():
    """List all available input devices."""
    print(f"\n{colorama.Fore.CYAN}Available Input Devices:{colorama.Style.RESET_ALL}")
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            print(f"  [{i}] {dev['name']}")
    print()


class ElevenlabsLiveVCCmd(cmd.Cmd):
    intro = f"""{colorama.Fore.GREEN}{banner}\n{
        description}{colorama.Style.RESET_ALL}\n"""
    prompt = f"{colorama.Fore.LIGHTBLUE_EX}(live-vc){colorama.Style.RESET_ALL}"

    def __init__(self, input_device=None):
        super().__init__()
        self.audio_handler = AudioHandler.from_env(input_device=input_device)
        
        # Start VAD mode if enabled
        if self.audio_handler.recorder.vad_enabled:
            self.audio_handler.start_vad_mode()

    def do_clear(self, arg=None):
        """Clear the screen."""
        if os.name == 'nt':
            os.system('cls')
        else:
            os.system('clear')
        print(self.intro)

    def do_quit(self, arg=None):
        """Quit the program."""
        print(f"Exiting...")
        return True

    def do_set_mode(self, arg):
        """Set the mode to automatic (1) or manual (0)."""
        try:
            mode = int(arg)
            if mode not in self.audio_handler.recorder.settings.valid_modes():
                print(
                    f"{colorama.Fore.YELLOW}Invalid mode. Please enter 0 for manual or 1 for automatic.{
                        colorama.Style.RESET_ALL}"
                )
                return
            
            # Stop current recording if active
            if self.audio_handler.recorder.is_recording:
                self.audio_handler.recorder.stop()
            
            self.audio_handler.recorder.settings.mode = mode
            self.audio_handler.recorder.vad_enabled = (mode == 1)
            mode_str = "automatic (VAD)" if mode == 1 else "manual (press space)"
            print(
                f"{colorama.Fore.GREEN}Mode set to {mode_str}.{
                    colorama.Style.RESET_ALL}"
            )
            
            # Start VAD if switching to automatic
            if mode == 1:
                self.audio_handler.start_vad_mode()
                
        except ValueError:
            print(
                f"{colorama.Fore.YELLOW}Invalid input. Please enter 0 for manual or 1 for automatic.{
                    colorama.Style.RESET_ALL}"
            )

    def do_get_mode(self, arg):
        """Get the current mode (1 = automatic, 0 = manual)."""
        mode_str = "automatic (VAD)" if self.audio_handler.recorder.settings.mode == 1 else "manual (press space)"
        print(f"Current mode is {mode_str}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ElevenLabs Live Voice Changer")
    parser.add_argument("--microphone", action="store_true", help="Use Microphone Array as input")
    parser.add_argument("--wo-mic", action="store_true", help="Use WO Mic as input")
    parser.add_argument("--list-devices", action="store_true", help="List available input devices and exit")
    args = parser.parse_args()
    
    if args.list_devices:
        list_input_devices()
        exit(0)
    
    try:
        input_device = select_input_device(args)
        ElevenlabsLiveVCCmd(input_device=input_device).cmdloop()
    except KeyboardInterrupt:
        print("\nExiting gracefully...")
        exit(0)
