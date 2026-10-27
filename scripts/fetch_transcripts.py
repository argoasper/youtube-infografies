#!/usr/bin/env python3
"""Detecta vídeos nous dels canals de canals.txt i en baixa la transcripció.

1. Resol l'ID de cada canal (yt-dlp, només un cop; es desa a estat/canals.json).
2. Llegeix el canal RSS públic de YouTube per saber els vídeos i la data.
3. Baixa la transcripció amb youtube-transcript-api (i yt-dlp com a reserva).
Desa cada vídeo a transcripcions/AAAA-MM-DD/<id>.md. Un vídeo es dona per
fet (estat/vistos.json) només quan se n'ha obtingut la transcripció.
"""
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET

ARREL = pathlib.Path(__file__).resolve().parent.parent
CANALS = ARREL / "canals.txt"
ESTAT = ARREL / "estat"
VISTOS = ESTAT / "vistos.json"
IDS = ESTAT / "canals.json"
SORTIDA = ARREL / "transcripcions"
HORES_ENRERE = int(os.environ.get("HORES_ENRERE", "36"))
IDIOMES = ["es", "es-ES", "es-419", "ca", "en"]
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
      "m": "http://search.yahoo.com/mrss/"}
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36"}


def llegeix_canals():
    out = []
    for l in CANALS.read_text(encoding="utf-8").splitlines():
        l = l.strip()
        if l and not l.startswith("#"):
            out.append(l)
    return out


def url_canal(c):
    if c.startswith("http"):
        return c.rstrip("/")
    if c.startswith("UC"):
        return f"https://www.youtube.com/channel/{c}"
    return f"https://www.youtube.com/{c if c.startswith('@') else '@' + c}"


def resol_id(c, cache):
    if c.startswith("UC"):
        return c
    if c in cache:
        return cache[c]
    r = subprocess.run(["yt-dlp", "--no-warnings", "--flat-playlist", "--playlist-end", "1", "-J",
                        url_canal(c) + "/videos"], capture_output=True, text=True, timeout=180)
    if r.returncode == 0:
        d = json.loads(r.stdout)
        cid = d.get("channel_id") or d.get("id")
        if cid and cid.startswith("UC"):
            cache[c] = cid
            return cid
    print(f"  ! no he pogut resoldre l'ID de {c}: {r.stderr.strip()[:200]}")
    return None


def rss(cid):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as f:
        arrel = ET.fromstring(f.read())
    canal = arrel.findtext("a:title", default="", namespaces=NS)
    videos = []
    for e in arrel.findall("a:entry", NS):
        videos.append({
            "id": e.findtext("yt:videoId", namespaces=NS),
            "titol": e.findtext("a:title", default="", namespaces=NS),
            "publicat": e.findtext("a:published", default="", namespaces=NS),
            "descripcio": e.findtext("m:group/m:description", default="", namespaces=NS),
            "canal": canal,
        })
    return videos


def transcripcio_api(vid):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return "", "sense biblioteca"
    try:
        api = YouTubeTranscriptApi()
        if hasattr(api, "fetch"):
            t = api.fetch(vid, languages=IDIOMES)
            return " ".join(s.text for s in t.snippets), ""
        t = YouTubeTranscriptApi.get_transcript(vid, languages=IDIOMES)
        return " ".join(s["text"] for s in t), ""
    except Exception as ex:  # noqa: BLE001
        return "", f"{type(ex).__name__}: {str(ex).splitlines()[0][:150] if str(ex) else ''}"


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


def transcripcio_ytdlp(vid, tmp):
    subprocess.run(["yt-dlp", "--no-warnings", "--skip-download", "--write-subs", "--write-auto-subs",
                    "--sub-langs", ",".join(IDIOMES), "--sub-format", "vtt",
                    "-o", str(tmp / "%(id)s.%(ext)s"), f"https://www.youtube.com/watch?v={vid}"],
                   capture_output=True, text=True, timeout=180)
    for idioma in IDIOMES:
        f = tmp / f"{vid}.{idioma}.vtt"
        if f.exists():
            return vtt_a_text(f.read_text(encoding="utf-8", errors="ignore"))
    return ""


def main():
    ESTAT.mkdir(exist_ok=True)
    vistos = set(json.loads(VISTOS.read_text())) if VISTOS.exists() else set()
    cache = json.loads(IDS.read_text()) if IDS.exists() else {}
    limit = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=HORES_ENRERE)
    tmp = ARREL / ".tmp"
    tmp.mkdir(exist_ok=True)
    nous = amb_text = 0

    for c in llegeix_canals():
        print(f"Canal: {c}")
        cid = resol_id(c, cache)
        if not cid:
            continue
        try:
            videos = rss(cid)
        except Exception as ex:  # noqa: BLE001
            print(f"  ! error RSS: {ex}")
            continue
        for v in videos:
            publicat = dt.datetime.fromisoformat(v["publicat"].replace("Z", "+00:00"))
            if publicat < limit or v["id"] in vistos:
                continue
            text, err = transcripcio_api(v["id"])
            if not text:
                text = transcripcio_ytdlp(v["id"], tmp)
            dia = publicat.date().isoformat()
            carpeta = SORTIDA / dia
            carpeta.mkdir(parents=True, exist_ok=True)
            url = f"https://www.youtube.com/watch?v={v['id']}"
            (carpeta / f"{v['id']}.md").write_text(
                f"---\nid: {v['id']}\nurl: {url}\ntitol: {json.dumps(v['titol'], ensure_ascii=False)}\n"
                f"canal: {json.dumps(v['canal'], ensure_ascii=False)}\npublicat: {v['publicat']}\n"
                f"te_transcripcio: {bool(text)}\n---\n\n## Descripció\n\n{v['descripcio']}\n\n"
                f"## Transcripció\n\n{text or '(no disponible)'}\n", encoding="utf-8")
            nous += 1
            if text:
                vistos.add(v["id"])
                amb_text += 1
            print(f"  + {v['titol']} ({dia}) transcripció: {'sí' if text else 'no — ' + err}")

    IDS.write_text(json.dumps(cache, indent=1, ensure_ascii=False))
    VISTOS.write_text(json.dumps(sorted(vistos), indent=0))
    print(f"Vídeos nous: {nous} · amb transcripció: {amb_text}")


if __name__ == "__main__":
    sys.exit(main())
