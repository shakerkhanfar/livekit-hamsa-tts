cat > README.md <<'MD'
# livekit-hamsa-tts

A plug-in **Hamsa real-time TTS backend** for LiveKit Agents.  
Includes:

* `hamsa_tts.py` – backend (PCM, 22 kHz, mono)
* `test_hamsa_livekit.py` – minimal verification script

## Usage

```bash
python -m venv venv && source venv/bin/activate
pip install livekit-agents aiohttp sounddevice numpy
export HAMSA_API_KEY="YOUR_KEY"
python test_hamsa_livekit.py   # plays audio & saves hamsa_livekit.wav
