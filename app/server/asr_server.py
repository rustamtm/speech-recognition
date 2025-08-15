import asyncio, json, time
import numpy as np
from websockets.server import serve
from faster_whisper import WhisperModel

SR = 16000

class ASRServer:
    def __init__(self, model_size="medium", compute_type="int8_float16"):
        self.model = WhisperModel(model_size, compute_type=compute_type)
        self.lang = None
        self.buf = np.zeros(0, dtype=np.float32)
        self.last_emit = 0.0
        self.last_partial = ""
        self.last_partial_time = 0.0

    def set_language(self, code):
        self.lang = code or None

    def append_pcm16(self, b: bytes):
        pcm = np.frombuffer(b, dtype=np.int16).astype(np.float32) / 32768.0
        self.buf = np.concatenate([self.buf, pcm])

    def pop_window(self, seconds=2.0, keep=1.0):
        need = int(SR * seconds)
        if len(self.buf) < need:
            return None
        window = self.buf[-need:]
        self.buf = self.buf[-int(SR * keep):]
        return window

    def transcribe_window(self, audio: np.ndarray):
        segs, info = self.model.transcribe(
            audio,
            language=self.lang,
            vad_filter=True,
            beam_size=1
        )
        text = "".join(s.text for s in segs).strip()
        return text

asr = ASRServer()

async def handler(ws):
    await ws.send(json.dumps({"type": "info", "message": "asr-ready"}))
    try:
        async for msg in ws:
            if isinstance(msg, bytes):
                asr.append_pcm16(msg)
                now = time.time()
                if now - asr.last_emit > 0.25:
                    window = asr.pop_window(seconds=2.0, keep=1.25)
                    if window is not None:
                        text = asr.transcribe_window(window)
                        if text and text != asr.last_partial:
                            await ws.send(json.dumps({"type": "partial", "text": text}))
                            asr.last_partial = text
                            asr.last_partial_time = now
                        elif text == asr.last_partial and now - asr.last_partial_time > 1.0:
                            await ws.send(json.dumps({"type": "final", "text": text}))
                            asr.last_partial = ""
                        asr.last_emit = now
            else:
                try:
                    obj = json.loads(msg)
                    if obj.get("type") == "control" and "setLanguage" in obj:
                        asr.set_language(obj["setLanguage"])
                        await ws.send(json.dumps({"type": "info", "message": f"lang-set:{asr.lang or 'auto'}"}))
                except Exception as e:
                    await ws.send(json.dumps({"type": "error", "message": str(e)}))
    except Exception as e:
        try:
            await ws.send(json.dumps({"type": "error", "message": f"ws:{e}"}))
        except:
            pass

async def main():
    async with serve(handler, "127.0.0.1", 8765, max_size=2**23):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
