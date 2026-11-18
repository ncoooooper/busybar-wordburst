# Wordburst

Count a chosen spoken word with local speech recognition and a separate pixel firework for every match.

Set a word, start the Mac companion, and place the bar near your screen. Say ‘amazing’ three times during a presentation and you get three hits. The counter is shared with the display. Wheel switches to the target editor, click changes the goal or refreshes the count, and Start sets a new target five hits above the current count.

## Recognize live speech

Install whisper.cpp and FFmpeg on the Mac. Download a compatible GGML model following [the upstream model instructions](https://github.com/ggml-org/whisper.cpp#quick-start). Use a multilingual model for Ukrainian. List microphone indices with `ffmpeg -f avfoundation -list_devices true -i empty`. Run `python3 companion/wordburst.py --microphone 0 --model /path/to/ggml-base.bin --language en --word amazing`. macOS asks for microphone access on first use. The computer recognizes short utterances locally after a pause. Recognition quality depends on microphone, language and model.

A live 16 kHz signed little-endian PCM source can also be piped into --pcm-stdin. For a recording, use `--wav talk.wav` instead of `--microphone 0` with 16 kHz mono PCM. Set Wordburst URL to `http://127.0.0.1:8770/wordburst` in the emulator and allow local port 8770. For hardware, bind the bridge to a trusted LAN address and enter that address on the device. Only the configured word, count, session ID and capture state travel to the display. Restarting the bridge starts a fresh count. Recognition of a long run of speech may be delayed until the next pause. The session runs only while you keep the companion open.

## Run locally

From this folder, run `~/.busy-emulator/bin/busy-emulator dev --once` with BUSY Bar Emulator open. Back exits.

![BUSY Bar front display](screenshots/front-1.png)
