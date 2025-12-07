import cmd
import os
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


class ElevenlabsLiveVCCmd(cmd.Cmd):
    intro = f"""{colorama.Fore.GREEN}{banner}\n{
        description}{colorama.Style.RESET_ALL}\n"""
    prompt = f"{colorama.Fore.LIGHTBLUE_EX}(live-vc){colorama.Style.RESET_ALL}"

    def __init__(self):
        super().__init__()
        self.audio_handler = AudioHandler.from_env()
        
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
    try:
        ElevenlabsLiveVCCmd().cmdloop()
    except KeyboardInterrupt:
        print("\nExiting gracefully...")
        exit(0)
