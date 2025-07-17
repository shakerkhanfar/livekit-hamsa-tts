"""Hamsa LiveKit TTS backend (PCM)"""
from __future__ import annotations
import asyncio, os, aiohttp
from dataclasses import dataclass, replace
from typing import Any, Optional
from livekit.agents import (
    APIConnectionError, APIConnectOptions, APIStatusError,
    APITimeoutError, tts, utils,
)
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS

HAMSA_ENDPOINT = "https://api.tryhamsa.com/v1/realtime/tts-stream"
PCM_RATE = 22_050
AUTH_HEADER = "Authorization"

@dataclass
class HamsaSettings:
    speaker: str
    dialect: str | None = None
    mulaw: bool = False
    def as_request_json(self, text: str) -> dict[str, Any]:
        body = {"text": text, "speaker": self.speaker, "mulaw": self.mulaw}
        if self.dialect:
            body["dialect"] = self.dialect
        return body

@dataclass
class _Opts:
    api_key: str
    settings: HamsaSettings
    sample_rate: int

class TTS(tts.TTS):
    def __init__(self, *, api_key: str | None, settings: HamsaSettings,
                 http_session: aiohttp.ClientSession | None = None) -> None:
        api_key = api_key or os.getenv("HAMSA_API_KEY")
        if not api_key:
            raise ValueError("Provide `api_key` or set HAMSA_API_KEY")
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=True, aligned_transcript=False),
            sample_rate=PCM_RATE, num_channels=1,
        )
        self._opts = _Opts(api_key, settings, PCM_RATE)
        self._sess: Optional[aiohttp.ClientSession] = http_session
        self._streams = []

    # get or create HTTP session
    def _ensure_session(self) -> aiohttp.ClientSession:
        if self._sess:
            return self._sess
        try:
            self._sess = utils.http_context.http_session()
        except RuntimeError:
            self._sess = aiohttp.ClientSession()
        return self._sess

    # LiveKit interface --------------------------------------------------
    def synthesize(self, text: str,
                   *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS):
        return _HamsaChunk(tts=self, input_text=text, conn_options=conn_options)

    def stream(self, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS):
        raise NotImplementedError("Hamsa exposes HTTP streaming only")

    async def aclose(self):
        for s in list(self._streams):
            await s.aclose()
        if self._sess and not self._sess.closed:
            await self._sess.close()
        self._streams.clear()

class _HamsaChunk(tts.ChunkedStream):
    def __init__(self, *, tts: TTS, input_text: str,
                 conn_options: APIConnectOptions):
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._tts, self._opts = tts, replace(tts._opts)
        tts._streams.append(self)

    async def _run(self, emitter: tts.AudioEmitter):
        body = self._opts.settings.as_request_json(self._input_text)
        emitter.initialize(request_id=utils.shortuuid(),
                           sample_rate=self._opts.sample_rate,
                           num_channels=1, mime_type="audio/pcm")
        try:
            async with self._tts._ensure_session().post(
                HAMSA_ENDPOINT, json=body,
                headers={AUTH_HEADER: f"Token {self._opts.api_key}"},
                timeout=aiohttp.ClientTimeout(sock_connect=self._conn_options.timeout),
            ) as resp:
                if resp.status != 200:
                    raise APIStatusError(await resp.text(), resp.status, None, None)
                async for chunk in resp.content.iter_chunked(4096):
                    emitter.push(chunk)
                emitter.flush()
        except asyncio.TimeoutError as e:
            raise APITimeoutError from e
        except aiohttp.ClientResponseError as e:
            raise APIStatusError(e.message, e.status, None, None) from e
        except Exception as e:
            raise APIConnectionError from e
