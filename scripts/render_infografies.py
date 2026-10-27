#!/usr/bin/env python3
"""Genera la pàgina HTML d'infografies a partir d'un JSON.

Ús: python render_infografies.py entrada.json sortida.html

Format del JSON:
{
  "data": "2026-10-27",
  "periode": "últimes 72 hores",
  "videos": [{
    "titol": "...", "canal": "...", "data": "2026-10-26", "url": "...",
    "durada": "18 min", "tema": "Automatització",
    "idea_clau": "Una o dues frases.",
    "per_que": "Per què importa (1-2 frases).",
    "xifres": [{"valor": "3x", "etiqueta": "més ràpid"}],
    "eines": ["n8n", "Claude"],
    "passos": [{"titol": "...", "detall": "..."}],
    "consells": ["..."],
    "conclusio": "Una frase per emportar-se."
  }]
}
"""
import html
import json
import sys

e = html.escape

CSS = """
:root{
  /* Fitxes apilades com fulls de quadern tècnic: capçalera de canal, idea clau, pas a pas numerat */
  --paper:#f3f4f1; --sheet:#ffffff; --ink:#1b2321; --muted:#5d6b67; --line:#d9dfdc;
  --accent:#0f7a6c; --accent-soft:#e1f1ee; --mark:#c2410c; --mark-soft:#fbeadf;
  --display:"Bricolage Grotesque", "Avenir Next", system-ui, sans-serif;
  --body:"Source Sans 3", "Segoe UI", system-ui, sans-serif;
  --mono:"JetBrains Mono", ui-monospace, Menlo, monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --paper:#111615; --sheet:#1a2120; --ink:#e7ecea; --muted:#9aa8a4; --line:#2c3634;
  --accent:#4fc7b4; --accent-soft:#163a35; --mark:#f59a62; --mark-soft:#3a2418; color-scheme:dark}}
:root[data-theme="dark"]{
  --paper:#111615; --sheet:#1a2120; --ink:#e7ecea; --muted:#9aa8a4; --line:#2c3634;
  --accent:#4fc7b4; --accent-soft:#163a35; --mark:#f59a62; --mark-soft:#3a2418; color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font:16px/1.55 var(--body);
  padding-left:max(16px, env(safe-area-inset-left, 0px));padding-right:max(16px, env(safe-area-inset-right, 0px));padding-block:28px 56px}
.wrap{max-width:860px;margin:0 auto;display:flex;flex-direction:column;gap:28px}
header.top h1{font:700 clamp(28px,5vw,40px)/1.1 var(--display);margin:0 0 6px;text-wrap:balance}
header.top p{margin:0;color:var(--muted)}
nav.index{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
nav.index a{font:500 13px/1 var(--body);color:var(--accent);background:var(--accent-soft);padding:7px 11px;border-radius:999px;text-decoration:none}
nav.index a:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
article{background:var(--sheet);border:1px solid var(--line);border-radius:14px;padding:clamp(18px,4vw,32px);display:flex;flex-direction:column;gap:20px;scroll-margin-top:16px}
.meta{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;font:500 12px/1.3 var(--mono);color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.meta .canal{color:var(--accent)}
.meta .tema{color:var(--mark);background:var(--mark-soft);padding:3px 8px;border-radius:6px}
h2{font:700 clamp(22px,3.6vw,30px)/1.15 var(--display);margin:0;text-wrap:balance}
.clau{font-size:18px;line-height:1.5;border-left:4px solid var(--accent);padding-left:14px;margin:0}
.perque{color:var(--muted);margin:0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.xifra{border:1px solid var(--line);border-radius:10px;padding:12px}
.xifra b{display:block;font:700 26px/1.1 var(--display);color:var(--accent);font-variant-numeric:tabular-nums}
.xifra span{font-size:13px;color:var(--muted)}
h3{font:600 12px/1 var(--mono);text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:0 0 10px}
.eines{display:flex;flex-wrap:wrap;gap:6px}
.eines span{font:500 13px/1 var(--mono);border:1px solid var(--line);padding:6px 9px;border-radius:6px}
ol.passos{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:12px;counter-reset:p}
ol.passos li{display:grid;grid-template-columns:34px 1fr;gap:12px;counter-increment:p}
ol.passos li::before{content:counter(p);width:30px;height:30px;border-radius:50%;background:var(--accent);color:var(--sheet);font:700 14px/30px var(--display);text-align:center}
ol.passos li div{min-width:0}
ol.passos strong{display:block;font-weight:600}
ol.passos p{margin:2px 0 0;color:var(--muted)}
ul.consells{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:8px}
ul.consells li{background:var(--mark-soft);border-radius:8px;padding:9px 12px}
.peu{display:flex;flex-wrap:wrap;gap:10px 18px;justify-content:space-between;align-items:center;border-top:1px dashed var(--line);padding-top:14px}
.peu em{font-style:normal;font-weight:600}
.peu a{color:var(--accent);font-weight:600;word-break:break-all}
.buit{background:var(--sheet);border:1px dashed var(--line);border-radius:14px;padding:28px;color:var(--muted)}
"""


def fitxa(i, v):
    xifres = "".join(f'<div class="xifra"><b>{e(x["valor"])}</b><span>{e(x["etiqueta"])}</span></div>'
                     for x in v.get("xifres", []))
    eines = "".join(f"<span>{e(t)}</span>" for t in v.get("eines", []))
    passos = "".join(f'<li><div><strong>{e(p["titol"])}</strong><p>{e(p["detall"])}</p></div></li>'
                     for p in v.get("passos", []))
    consells = "".join(f"<li>{e(c)}</li>" for c in v.get("consells", []))
    parts = [
        f'<div class="meta"><span class="canal">{e(v["canal"])}</span><span>{e(v.get("data",""))}</span>'
        f'<span>{e(v.get("durada",""))}</span>' + (f'<span class="tema">{e(v["tema"])}</span>' if v.get("tema") else "") + "</div>",
        f"<h2>{e(v['titol'])}</h2>",
        f'<p class="clau">{e(v["idea_clau"])}</p>',
    ]
    if v.get("per_que"):
        parts.append(f'<p class="perque">{e(v["per_que"])}</p>')
    if xifres:
        parts.append(f'<div class="grid">{xifres}</div>')
    if eines:
        parts.append(f'<section><h3>Eines i conceptes</h3><div class="eines">{eines}</div></section>')
    if passos:
        parts.append(f'<section><h3>Pas a pas</h3><ol class="passos">{passos}</ol></section>')
    if consells:
        parts.append(f'<section><h3>Consells i alertes</h3><ul class="consells">{consells}</ul></section>')
    parts.append(f'<div class="peu"><em>{e(v.get("conclusio",""))}</em>'
                 f'<a href="{e(v["url"])}" target="_blank" rel="noopener">{e(v["url"])}</a></div>')
    return f'<article id="v{i}">' + "".join(parts) + "</article>"


def main(entrada, sortida):
    d = json.load(open(entrada, encoding="utf-8"))
    vids = d.get("videos", [])
    index = "".join(f'<a href="#v{i}">{e(v["canal"])}</a>' for i, v in enumerate(vids, 1))
    cos = "".join(fitxa(i, v) for i, v in enumerate(vids, 1)) or \
        '<div class="buit">Avui cap dels canals que segueixes ha publicat vídeos nous.</div>'
    pagina = f"""<title>Infografies YouTube</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700&family=JetBrains+Mono:wght@500;600&family=Source+Sans+3:wght@400;600&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header class="top"><h1>Infografies de YouTube</h1>
<p>{e(d.get("data",""))} · {len(vids)} vídeos nous · {e(d.get("periode",""))}</p>
<nav class="index">{index}</nav></header>
{cos}
</div>"""
    open(sortida, "w", encoding="utf-8").write(pagina)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
