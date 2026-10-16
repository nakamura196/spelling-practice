"""Spelling Practice App (index.html) の単語音声を Kokoro で事前生成する。

前提: ~/git/zenn/scripts/media/kokoro-ja/.venv（Kokoro と英語の spaCy モデル入り）、ffmpeg
使い方:
  ~/git/zenn/scripts/media/kokoro-ja/.venv/bin/python spelling/build-audio.py          # 未生成分だけ
  ~/git/zenn/scripts/media/kokoro-ja/.venv/bin/python spelling/build-audio.py --force  # 全部作り直す
出力: audio/<word>.mp3（ふつうの速さ）と audio/<word>.slow.mp3（ゆっくり）

単語は index.html の `{ en: "..." }` から拾うので、単語を足したら再実行するだけでよい。
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "audio"
VOICE = "af_heart"
# af_heart で崩れた語だけ別の声にする（Whisper の聞き取りで比較して決めた。
# af_heart: know→now, thump→somp, sail/little の前に雑音。af_bella はこの4語は正しいが in/is/own/width が崩れる）
# 2026-10-08 追加分: af_heart で saw→Isa, straw→Istra, law→La, highway→Taiwei, scream→A scream。af_bella では正しく聞き取れた
# he / change / than はどの声でも Here・Chain・Then と聞き取られた（発音記号を直接与えても同じ）。af_heart のまま
VOICE_FOR = {w: "af_bella" for w in ("know", "thump", "sail", "little", "saw", "straw", "law", "highway", "scream", "sack", "yellow", "round")}
SPEED = 0.9
SLOW_TEMPO = 0.7  # ゆっくり版は Kokoro に遅く読ませると雑音が出るので、ffmpeg で引き延ばす
SR = 24000
force = "--force" in sys.argv

html = (ROOT / "index.html").read_text(encoding="utf-8")
words = list(dict.fromkeys(re.findall(r'\ben:\s*"([^"]+)"', html)))
OUT.mkdir(exist_ok=True)

pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
pad = np.zeros(int(SR * 0.15), dtype=np.float32)  # 再生開始時の頭切れ防止
made = 0
for word in words:
    normal, slow = OUT / f"{word}.mp3", OUT / f"{word}.slow.mp3"
    if normal.exists() and slow.exists() and not force:
        continue
    # 末尾の "." で単語として言い切らせる（無いと語尾が上がる・崩れることがある）
    audio = np.concatenate([r.audio.numpy() for r in pipe(word + ".", voice=VOICE_FOR.get(word, VOICE), speed=SPEED)])
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
        sf.write(tmp.name, np.concatenate([pad, audio, pad]), SR)
        for out, tempo in ((normal, ""), (slow, f"atempo={SLOW_TEMPO},")):
            # 単語ごとの音量差をならす
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp.name,
                            "-af", f"{tempo}loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", str(SR),
                            "-ac", "1", "-b:a", "64k", str(out)], check=True)
    made += 1
print(f"words={len(words)} generated={made} voice={VOICE} -> {OUT}")
