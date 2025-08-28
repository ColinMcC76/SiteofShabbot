# ✅ Split-Process Design: Website API ⇄ Bot (Control Server)
# This gives you TWO separate processes:
#  1) panel_api.py  — public-facing FastAPI that your website calls
#  2) bot_control_server (embedded in your bot process) — localhost-only control API that actually drives Discord
# The public API forwards each request (after auth) to the bot’s localhost control port. No tokens in the browser.
#
# ┌──────────────┐        HTTPS        ┌────────────────┐     localhost (or VPN)     ┌────────────────────┐
# │  Web Frontend│  ───────────────▶  │  panel_api.py  │  ───────────────────────▶  │  bot_control_server │
# └──────────────┘                     └────────────────┘                             └────────────────────┘
#                                                                                          (inside botV3.py)
#
# Notes:
# - The control server binds to 127.0.0.1 by default. If your bot is on a different box, set BOT_CONTROL_HOST to a private IP
#   and firewall it so only panel_api can reach it (or place both behind Tailscale/WireGuard).
# - Use long random API keys for BOTH layers.


# =============================
# 1) panel_api.py  (standalone)
# =============================
# pip install fastapi uvicorn[standard] pydantic httpx

import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
import uvicorn
import httpx

PANEL_API_KEY = os.getenv("PANEL_API_KEY", "CHANGE_ME")  # external key your web app uses
BOT_CONTROL_URL = os.getenv("BOT_CONTROL_URL", "http://127.0.0.1:8765")  # where the bot’s control server listens
BOT_CONTROL_KEY = os.getenv("BOT_CONTROL_KEY", "CHANGE_ME_TOO")  # shared secret between panel_api and bot

app = FastAPI(title="Shabbot Public Panel API")

def require_api_key(x_api_key: str = Header(None)):
    if x_api_key != PANEL_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ----- Models matching the bot control API -----
class SayPayload(BaseModel):
    channel_id: int
    message: str

class VoiceJoinPayload(BaseModel):
    voice_channel_id: int

class VoiceLeavePayload(BaseModel):
    guild_id: int

class PlayYTPayload(BaseModel):
    url: str
    voice_channel_id: Optional[int] = None

class VolumePayload(BaseModel):
    level: int

class SFXPayload(BaseModel):
    voice_channel_id: int
    name: str

class SpeakPayload(BaseModel):
    voice_channel_id: int
    text: str

class EquipmentPayload(BaseModel):
    text_channel_id: int
    voice_channel_id: Optional[int] = None
    descriptor: Optional[str] = None

class PersonaPayload(BaseModel):
    mode: str

class VoiceNamePayload(BaseModel):
    name: str

async def forward(method: str, path: str, json: dict | None = None):
    url = f"{BOT_CONTROL_URL}{path}"
    headers = {"X-Internal-Key": BOT_CONTROL_KEY}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.request(method, url, json=json, headers=headers)
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
        except Exception:
            detail = r.text
        raise HTTPException(r.status_code, detail)
    return r.json()

@app.get("/api/ping")
async def ping():
    # Combine both healths
    try:
        data = await forward("GET", "/ctl/ping", None)
        return {"ok": True, "bot": data.get("bot")}
    except Exception as e:
        raise HTTPException(503, f"Bot control unreachable: {e}")

@app.post("/api/say", dependencies=[Depends(require_api_key)])
async def say(p: SayPayload):
    return await forward("POST", "/ctl/say", p.model_dump())

@app.post("/api/join", dependencies=[Depends(require_api_key)])
async def join(p: VoiceJoinPayload):
    return await forward("POST", "/ctl/join", p.model_dump())

@app.post("/api/leave", dependencies=[Depends(require_api_key)])
async def leave(p: VoiceLeavePayload):
    return await forward("POST", "/ctl/leave", p.model_dump())

@app.post("/api/playyt", dependencies=[Depends(require_api_key)])
async def playyt(p: PlayYTPayload):
    return await forward("POST", "/ctl/playyt", p.model_dump())

@app.post("/api/pause", dependencies=[Depends(require_api_key)])
async def pause(guild_id: int):
    return await forward("POST", f"/ctl/pause?guild_id={guild_id}")

@app.post("/api/resume", dependencies=[Depends(require_api_key)])
async def resume(guild_id: int):
    return await forward("POST", f"/ctl/resume?guild_id={guild_id}")

@app.post("/api/skip", dependencies=[Depends(require_api_key)])
async def skip(guild_id: int):
    return await forward("POST", f"/ctl/skip?guild_id={guild_id}")

@app.post("/api/stop", dependencies=[Depends(require_api_key)])
async def stop(guild_id: int):
    return await forward("POST", f"/ctl/stop?guild_id={guild_id}")

@app.post("/api/volume", dependencies=[Depends(require_api_key)])
async def volume(guild_id: int, p: VolumePayload):
    return await forward("POST", f"/ctl/volume?guild_id={guild_id}", p.model_dump())

@app.post("/api/sfx", dependencies=[Depends(require_api_key)])
async def sfx(p: SFXPayload):
    return await forward("POST", "/ctl/sfx", p.model_dump())

@app.post("/api/speak", dependencies=[Depends(require_api_key)])
async def speak(p: SpeakPayload):
    return await forward("POST", "/ctl/speak", p.model_dump())

@app.post("/api/equipmentcheck", dependencies=[Depends(require_api_key)])
async def equipmentcheck(p: EquipmentPayload):
    return await forward("POST", "/ctl/equipmentcheck", p.model_dump())

@app.post("/api/equipmentcheck/soundoff", dependencies=[Depends(require_api_key)])
async def equipmentcheck_soundoff(p: EquipmentPayload):
    return await forward("POST", "/ctl/equipmentcheck/soundoff", p.model_dump())

@app.post("/api/resetmemory", dependencies=[Depends(require_api_key)])
async def resetmemory(channel_id: int):
    return await forward("POST", f"/ctl/resetmemory?channel_id={channel_id}")

@app.post("/api/forget", dependencies=[Depends(require_api_key)])
async def forget(user_id: int):
    return await forward("POST", f"/ctl/forget?user_id={user_id}")

@app.post("/api/persona", dependencies=[Depends(require_api_key)])
async def persona(p: PersonaPayload):
    return await forward("POST", "/ctl/persona", p.model_dump())

@app.post("/api/voice", dependencies=[Depends(require_api_key)])
async def voice(p: VoiceNamePayload):
    return await forward("POST", "/ctl/voice", p.model_dump())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))


# =====================================================
# 2) bot_control_server (embed into your botV3.py file)
# =====================================================
# This runs INSIDE the bot process and exposes a localhost-only control API.
# pip install fastapi uvicorn[standard] pydantic

import asyncio
from fastapi import FastAPI as FastAPI2, HTTPException as HTTPException2, Depends as Depends2, Header as Header2
from pydantic import BaseModel as BaseModel2
import uvicorn as uvicorn2

# Reuse your existing bot, helpers, and constants from botV3.py:
# - bot (commands.Bot)
# - make_audio_source, get_stream, ai_tts, TTS_VOICE, temp_dir
# - channel_history, conversation_memory, PERSONAS, active_persona, DISCORD_LIMIT
# Ensure these exist above this block in your bot file.

BOT_CONTROL_KEY = os.getenv("BOT_CONTROL_KEY", "CHANGE_ME_TOO")
BOT_CONTROL_HOST = os.getenv("BOT_CONTROL_HOST", "127.0.0.1")
BOT_CONTROL_PORT = int(os.getenv("BOT_CONTROL_PORT", "8765"))

def require_internal_key(x_internal_key: str = Header2(None)):
    if x_internal_key != BOT_CONTROL_KEY:
        raise HTTPException2(status_code=401, detail="Unauthorized (internal)")

ctl = FastAPI2(title="Shabbot Internal Control API")

# Schemas mirror panel_api
class SayPayload2(BaseModel2):
    channel_id: int
    message: str

class VoiceJoinPayload2(BaseModel2):
    voice_channel_id: int

class VoiceLeavePayload2(BaseModel2):
    guild_id: int

class PlayYTPayload2(BaseModel2):
    url: str
    voice_channel_id: Optional[int] = None

class VolumePayload2(BaseModel2):
    level: int

class SFXPayload2(BaseModel2):
    voice_channel_id: int
    name: str

class SpeakPayload2(BaseModel2):
    voice_channel_id: int
    text: str

class EquipmentPayload2(BaseModel2):
    text_channel_id: int
    voice_channel_id: Optional[int] = None
    descriptor: Optional[str] = None

class PersonaPayload2(BaseModel2):
    mode: str

class VoiceNamePayload2(BaseModel2):
    name: str

# --- helpers ---
async def _ensure_vc_for_channel(voice_channel_id: int) -> discord.VoiceClient:
    ch = bot.get_channel(voice_channel_id)
    if not isinstance(ch, discord.VoiceChannel):
        raise HTTPException2(400, f"{voice_channel_id} is not a voice channel")
    vc = discord.utils.get(bot.voice_clients, guild=ch.guild)
    if vc and vc.is_connected():
        if vc.channel != ch:
            await vc.move_to(ch)
        return vc
    return await ch.connect()

async def _send_text(channel_id: int, content: str):
    ch = bot.get_channel(channel_id)
    if ch is None:
        raise HTTPException2(404, f"Text channel {channel_id} not found")
    await ch.send(content[:DISCORD_LIMIT])

# --- endpoints ---
@ctl.get("/ctl/ping")
async def ctl_ping():
    return {"ok": True, "bot": str(bot.user) if bot.user else None}

@ctl.post("/ctl/say", dependencies=[Depends2(require_internal_key)])
async def ctl_say(p: SayPayload2):
    await _send_text(p.channel_id, p.message)
    return {"ok": True}

@ctl.post("/ctl/join", dependencies=[Depends2(require_internal_key)])
async def ctl_join(p: VoiceJoinPayload2):
    await _ensure_vc_for_channel(p.voice_channel_id)
    return {"ok": True}

@ctl.post("/ctl/leave", dependencies=[Depends2(require_internal_key)])
async def ctl_leave(p: VoiceLeavePayload2):
    guild = bot.get_guild(p.guild_id)
    if not guild:
        raise HTTPException2(404, "Guild not found")
    vc = discord.utils.get(bot.voice_clients, guild=guild)
    if vc and vc.is_connected():
        await vc.disconnect(force=True)
    return {"ok": True}

@ctl.post("/ctl/playyt", dependencies=[Depends2(require_internal_key)])
async def ctl_playyt(p: PlayYTPayload2):
    if p.voice_channel_id:
        await _ensure_vc_for_channel(p.voice_channel_id)
    try:
        title, stream_url, page = get_stream(p.url)
    except Exception as e:
        raise HTTPException2(400, f"yt-dlp error: {e}")

    vc = None
    if p.voice_channel_id:
        ch = bot.get_channel(p.voice_channel_id)
        vc = discord.utils.get(bot.voice_clients, guild=ch.guild)
    else:
        vc = next((v for v in bot.voice_clients if v.is_connected()), None)
    if not vc:
        raise HTTPException2(400, "Bot not in a voice channel (provide voice_channel_id)")

    try:
        source = make_audio_source(stream_url)
        audio = discord.PCMVolumeTransformer(source, volume=0.9)
        if vc.is_playing() or vc.is_paused():
            vc.stop()
        vc.play(audio)
    except Exception as e:
        raise HTTPException2(500, f"FFmpeg/playback error: {e}")

    try:
        text_ch = next((c for c in vc.channel.guild.text_channels if c.permissions_for(vc.channel.guild.me).send_messages), None)
        if text_ch:
            await text_ch.send(f\"▶️ **Now playing:** {title};
🔗 {page}")
    except Exception:
        pass

    return {"ok": True, "title": title}

@ctl.post("/ctl/pause", dependencies=[Depends2(require_internal_key)])
async def ctl_pause(guild_id: int):
    guild = bot.get_guild(guild_id)
    if not guild or not guild.voice_client:
        raise HTTPException2(400, "No voice client for guild")
    vc = guild.voice_client
    if vc.is_playing():
        vc.pause()
    return {"ok": True}

@ctl.post("/ctl/resume", dependencies=[Depends2(require_internal_key)])
async def ctl_resume(guild_id: int):
    guild = bot.get_guild(guild_id)
    if not guild or not guild.voice_client:
        raise HTTPException2(400, "No voice client for guild")
    vc = guild.voice_client
    if vc.is_paused():
        vc.resume()
    return {"ok": True}

@ctl.post("/ctl/skip", dependencies=[Depends2(require_internal_key)])
async def ctl_skip(guild_id: int):
    guild = bot.get_guild(guild_id)
    if not guild or not guild.voice_client:
        raise HTTPException2(400, "No voice client for guild")
    vc = guild.voice_client
    if vc.is_playing() or vc.is_paused():
        vc.stop()
    return {"ok": True}

@ctl.post("/ctl/stop", dependencies=[Depends2(require_internal_key)])
async def ctl_stop(guild_id: int):
    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException2(404, "Guild not found")
    vc = guild.voice_client
    if vc and vc.is_playing():
        vc.stop()
    return {"ok": True}

@ctl.post("/ctl/volume", dependencies=[Depends2(require_internal_key)])
async def ctl_volume(guild_id: int, p: VolumePayload2):
    guild = bot.get_guild(guild_id)
    if not guild or not guild.voice_client:
        raise HTTPException2(400, "No voice client for guild")
    vc = guild.voice_client
    if not vc.source or not isinstance(vc.source, discord.PCMVolumeTransformer):
        raise HTTPException2(400, "Current source not adjustable")
    level = max(0, min(p.level, 200))
    vc.source.volume = level / 100.0
    return {"ok": True, "level": level}

_SFX_TO_FILE = {
    "ouch": "ShabbotSaidWHAT",
    "flashbang": "flashbang",
    "who": "aliens",
    "real": "aliens-are-r-e-a-l",
    "like": "i-like-ya-and-i-want-ya",
    "eww": "negro-you-gay-boondocks",
    "moment": "boondocks-nibba-moment",
}

@ctl.post("/ctl/sfx", dependencies=[Depends2(require_internal_key)])
async def ctl_sfx(p: SFXPayload2):
    name = p.name.lower()
    if name not in _SFX_TO_FILE:
        raise HTTPException2(400, f"Unknown sfx '{name}'");
    path = f"sounds/{_SFX_TO_FILE[name]}.mp3";
    vc = await _ensure_vc_for_channel(p.voice_channel_id);
    if vc.is_playing():
        vc.stop()
    try:
        vc.play(discord.FFmpegPCMAudio(path))
    except Exception as e:
        raise HTTPException2(500, f"Could not play sound: {e}")
    return {"ok": True}

@ctl.post("/ctl/speak", dependencies=[Depends2(require_internal_key)])
async def ctl_speak(p: SpeakPayload2):
    vc = await _ensure_vc_for_channel(p.voice_channel_id)
    audio_bytes = await ai_tts(p.text, voice=TTS_VOICE)
    out_path = os.path.join(temp_dir, "speak_api.mp3")
    with open(out_path, "wb") as f:
        f.write(audio_bytes)
    if vc.is_playing():
        vc.stop()
    vc.play(discord.FFmpegPCMAudio(out_path))
    return {"ok": True}

@ctl.post("/ctl/equipmentcheck", dependencies=[Depends2(require_internal_key)])
async def ctl_equipmentcheck(p: EquipmentPayload2):
    system_prompt = (
        "You are Shabbot, a tactical squad AI trained for both military-style ops and recreational readiness checks. "
        "Write a gritty, motivational, 4–6 line briefing. Mention '<@&1098420268956913665>' as Soldier."
    )
    user_prompt = (
        f"Style: {p.descriptor}." if p.descriptor else "Generate briefing."
    )
    try:
        skit = await ai_chat("gpt-5", messages=[{"role": "system", "content": system_prompt},{"role":"user","content":user_prompt}], max_completion_tokens=2000)
    except Exception:
        skit = "**EQUIPMENT CHECK – COMMAND FAILED**
Fallback briefing activated."
    await _send_text(p.text_channel_id, skit)
    return {"ok": True}

@ctl.post("/ctl/equipmentcheck/soundoff", dependencies=[Depends2(require_internal_key)])
async def ctl_equipmentcheck_soundoff(p: EquipmentPayload2):
    system_prompt = (
        "You are Shabbot, a tactical squad AI. Write a 3–5 line high-intensity Equipment Check announcement."
    )
    user_prompt = f"Style: {p.descriptor}." if p.descriptor else "Generate briefing."
    try:
        skit = await ai_chat("gpt-5", messages=[{"role": "system", "content": system_prompt},{"role":"user","content":user_prompt}], max_completion_tokens=2000)
    except Exception:
        skit = "**EQUIPMENT CHECK – COMMAND FAILED**"

    await _send_text(p.text_channel_id, skit)

    if p.voice_channel_id:
        vc = await _ensure_vc_for_channel(p.voice_channel_id)
        audio_bytes = await ai_tts(skit, voice=TTS_VOICE)
        out_path = os.path.join(temp_dir, "eqcso_api.mp3")
        with open(out_path, "wb") as f:
            f.write(audio_bytes)
        if vc.is_playing():
            vc.stop()
        vc.play(discord.FFmpegPCMAudio(out_path))
    return {"ok": True}

@ctl.post("/ctl/resetmemory", dependencies=[Depends2(require_internal_key)])
async def ctl_resetmemory(channel_id: int):
    channel_history.pop(channel_id, None)
    return {"ok": True}

@ctl.post("/ctl/forget", dependencies=[Depends2(require_internal_key)])
async def ctl_forget(user_id: int):
    conversation_memory.get(str(user_id), []).clear()
    return {"ok": True}

@ctl.post("/ctl/persona", dependencies=[Depends2(require_internal_key)])
async def ctl_persona(p: PersonaPayload2):
    mode = p.mode.lower()
    if mode not in PERSONAS:
        raise HTTPException2(400, f"Invalid persona. Available: {', '.join(PERSONAS.keys())}")
    active_persona["system_prompt"] = PERSONAS[mode]
    return {"ok": True, "mode": mode}

@ctl.post("/ctl/voice", dependencies=[Depends2(require_internal_key)])
async def ctl_voice(p: VoiceNamePayload2):
    global TTS_VOICE
    allowed = ["alloy","ash","ballad","coral","echo","sage","shimmer","verse"]
    name = p.name.lower()
    if name not in allowed:
        raise HTTPException2(400, f"Unknown voice. Try: {', '.join(allowed)}")
    TTS_VOICE = name
    return {"ok": True, "voice": TTS_VOICE}

# ---- runner to start the control server alongside your bot (still a separate *process* from panel_api) ----
async def _start_control_server():
    config = uvicorn2.Config(ctl, host=BOT_CONTROL_HOST, port=BOT_CONTROL_PORT, log_level="warning")
    server = uvicorn2.Server(config)
    await server.serve()

# In your bot startup, schedule this alongside bot.start(...). For example:
# if __name__ == "__main__":
#     async def runner():
#         await asyncio.gather(
#             bot.start(os.getenv("DISCORD_BOT_TOKEN")),
#             _start_control_server(),
#         )
#     asyncio.run(runner())
