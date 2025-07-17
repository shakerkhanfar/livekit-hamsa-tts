cat > test_hamsa_livekit.py <<'PY'
import os, asyncio, wave, numpy as np, sounddevice as sd
from hamsa_tts import TTS, HamsaSettings

API_KEY = os.getenv("HAMSA_API_KEY") or "YOUR_API_KEY"

async def main():
    tts = TTS(api_key=API_KEY,
              settings=HamsaSettings(speaker="Majd", dialect="pls"))
    stream = tts.synthesize("مرحباً بكم جميعاً في همسة!")
    chunks: list[bytes] = []

    class Sink:
        def initialize(self, **kw): self.rate = kw["sample_rate"]
        def push(self, data: bytes): chunks.append(data)
        def flush(self):
            raw = b"".join(chunks)
            sd.play(np.frombuffer(raw, dtype=np.int16), samplerate=self.rate)
            sd.wait()
            with wave.open("hamsa_livekit.wav", "wb") as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(self.rate)
                wf.writeframes(raw)
            print("✅ Saved hamsa_livekit.wav")
        def push_timed_transcript(self,*_): pass
        def start_segment(self,*_): pass
        def end_input(self): pass

    await stream._run(Sink())
    await tts.aclose()

if __name__ == "__main__":
    asyncio.run(main())
PY
