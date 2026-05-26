"""
List available audio input devices.

Run this to discover the correct value for STT_INPUT_DEVICE_INDEX
in your .env file when using multiple microphones.

Example:
    python utils/list_audio_devices.py

Then add to .env:
    STT_INPUT_DEVICE_INDEX=1
"""

import pyaudio


def main():
    pa = pyaudio.PyAudio()

    print("Available audio input devices (microphones):\n")

    found = False
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info.get("maxInputChannels", 0) > 0:
            found = True
            print(f"Index {i}: {info['name']}")
            print(f"    Max input channels: {info['maxInputChannels']}")
            print(f"    Default sample rate: {int(info['defaultSampleRate'])}")
            print()

    pa.terminate()

    if not found:
        print("No input devices found.")
        return

    print("Instructions:")
    print("1. Identify your microphone from the list above.")
    print("2. Add the following line to your .env file:")
    print("   STT_INPUT_DEVICE_INDEX=<index>")
    print("   (replace <index> with the number shown, e.g. 1)")
    print()
    print("3. Restart the application for the change to take effect.")


if __name__ == "__main__":
    main()
