#!/usr/bin/env python3
"""Detecta vídeos nous dels canals de canals.txt i en baixa la transcripció.

Desa cada transcripció a transcripcions/AAAA-MM-DD/<id>.md i registra els
vídeos ja processats a estat/vistos.json perquè no es repeteixin.
"""
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys

ARREL = pathlib.Path(__file__).resolve().parent.parent
CANALS = ARREL / "canals.txt"
ESTAT = ARREL / "estat" / "vistos.json"
SORTIDA = ARREL / "transcripcions"
HORES_ENRERE = int(os.environ.get("HORES_ENRERE", "36"))  # marge per si un dia falla
VIDEOS_PER_CANAL = 10
IDIOMES = ["es", "es-ES", "ca", "en"]


def llegeix_canals():
    canals = []
    for linia in CANALS.read_text(encoding="utf-8").splitlines():
        linia = linia.strip()
        if not linia or linia.startswith("#"):
            continue
        if linia.startswith("http"):
            url = linia.rstrip("/")
        elif linia.startswith("UC"):
            url = f"https://www.youtube.com/channel/{linia}"
        else:
            url = f"https://www.youtube.com/{linia if linia.startswith('@') else '@' + linia}"
        canals.append(url + "/videos")
    return canals


def ytdlp(*args):
    cmd = ["yt-dlp", "--no-warnings", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)


def videos_recents(url_canal):
    r = ytdlp("--flat-playlist", "--playlist-end", str(VIDEOS_PER_CANAL), "-J", url_canal)
    if r.returncode != 0:
        print(f"  ! error llistant {url_canal}: {r.stderr.strip()[:300]}")
        return []
    dades = json.loads(r.stdout)
    return [e["id"] for e in dades.get("entries", []) if e.get("id")]


def vtt_a_text(vtt):
    linies, anterior = [], None
    for l in vtt.splitlines():
        l = l.strip()
        if not l or "-->" in l or l.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        l = re.sub(r"<[^>]+>", "", l).strip()
        if l and l != anterior:
            linies.append(l)
            anterior = l
    return " ".join(linies)


def processa_video(vid, carpeta_tmp):
    url = f"https://www.youtube.com/watch?v={vid}"
    r = ytdlp("-J", "--skip-download", url)
    if r.returncode != 0:
        print(f"  ! error metadades {vid}: {r.stderr.strip()[:300]}")
        return None
    info = json.loads(r.stdout)
    data = info.get("upload_date")  # AAAAMMDD
    if data:
        publicat = dt.datetime.strptime(data, "%Y%m%d").replace(tzinfo=dt.timezone.utc)
        if publicat < dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=HORES_ENRERE):
            return "antic"
    if info.get("live_status") in ("is_live", "is_upcoming"):
        return None

    ytdlp("--skip-download", "--write-subs", "--write-auto-subs",
          "--sub-langs", ",".join(IDIOMES), "--sub-format", "vtt",
          "-o", str(carpeta_tmp / "%(id)s.%(ext)s"), url)
    text = ""
    for idioma in IDIOMES:
        f = carpeta_tmp / f"{vid}.{idioma}.vtt"
        if f.exists():
            text = vtt_a_text(f.read_text(encoding="utf-8", errors="ignore"))
            break
    return {
        "id": vid,
        "url": url,
        "titol": info.get("title", ""),
        "canal": info.get("channel") or info.get("uploader", ""),
        "data": data or "",
        "durada_s": info.get("duration"),
        "descripcio": info.get("description", ""),
        "capitols": [c.get("title") for c in (info.get("chapters") or [])],
        "transcripcio": text,
    }


def main():
    vistos = set(json.loads(ESTAT.read_text())) if ESTAT.exists() else set()
    avui = dt.date.today().isoformat()
    carpeta = SORTIDA / avui
    tmp = ARREL / ".tmp"
    tmp.mkdir(exist_ok=True)
    nous = 0

    for canal in llegeix_canals():
        print(f"Canal: {canal}")
        for vid in videos_recents(canal):
            if vid in vistos:
                continue
            res = processa_video(vid, tmp)
            if res == "antic":
                vistos.add(vid)
                break  # la llista va de més nou a més antic
            if not res:
                continue
            carpeta.mkdir(parents=True, exist_ok=True)
            capitols = "\n".join(f"- {c}" for c in res["capitols"]) or "(sense capítols)"
            (carpeta / f"{vid}.md").write_text(
                f"---\nid: {res['id']}\nurl: {res['url']}\ntitol: {json.dumps(res['titol'], ensure_ascii=False)}\n"
                f"canal: {json.dumps(res['canal'], ensure_ascii=False)}\ndata: {res['data']}\n"
                f"durada_s: {res['durada_s']}\nte_transcripcio: {bool(res['transcripcio'])}\n---\n\n"
                f"## Descripció\n\n{res['descripcio']}\n\n## Capítols\n\n{capitols}\n\n"
                f"## Transcripció\n\n{res['transcripcio'] or '(no disponible)'}\n",
                encoding="utf-8")
            vistos.add(vid)
            nous += 1
            print(f"  + {res['titol']} (transcripció: {'sí' if res['transcripcio'] else 'no'})")

    ESTAT.parent.mkdir(exist_ok=True)
    ESTAT.write_text(json.dumps(sorted(vistos), indent=0))
    print(f"Vídeos nous: {nous}")


if __name__ == "__main__":
    sys.exit(main())
