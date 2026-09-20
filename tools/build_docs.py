"""Build dependency-free GitHub Pages documentation from the desktop help."""
import ast
from html import escape
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
tree = ast.parse((ROOT / 'help_dialog.py').read_text(encoding='utf-8'))
pages = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == 'PAGES' for t in n.targets))
out = ROOT / 'docs'
out.mkdir(exist_ok=True)
slugs = [re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-') + '.html' for title, _ in pages]
repo = 'https://github.com/alberthanafi/HMR-Studio-Upscale'
installation = '''<p>Run HMR Studio locally on a Windows computer. Processing uses your NVIDIA GPU through CUDA, or your CPU.</p>
<h2>Install and launch</h2><ol><li>Install 64-bit Python 3.10–3.13, including the Python command on PATH.</li>
<li>Download the repository ZIP from GitHub and extract it to a writable folder.</li>
<li>Double-click <strong>Install.cmd</strong>. Installation downloads several GB of dependencies.</li>
<li>Double-click <strong>Launch HMR Upscale.vbs</strong>.</li>
<li>Add images, choose features and an output folder, then select <strong>Process images</strong>.</li></ol>
<h2>CUDA requirements</h2><p>The installer uses PyTorch 2.7.1 with CUDA 12.8. Use a compatible NVIDIA driver. A separate CUDA Toolkit is not required. CPU processing is available but slower.</p>
<h2>First run</h2><p>Each selected model downloads on first use. Once cached, it works offline. Keep the application folder writable for the environment, model cache and outputs.</p>
<h2>Packaging</h2><p>This release launches through the supplied VBS file. A standalone EXE is not included.</p>'''
home = '''<p class="lead">Bring every pixel to life.</p><p>A Windows desktop workspace for local AI upscaling, portrait restoration, colorization and masked damage repair.</p>
<div class="cards"><section><h2>Upscale</h2><p>Seven AI models, 2×–4× output, CUDA acceleration and a before/after comparison.</p></section><section><h2>Restore</h2><p>Optional face enhancement, predicted color, protected texture and painted damage masks.</p></section><section><h2>Stay informed</h2><p>Live hardware readings, tile progress, estimated time and timestamped errors.</p></section></div>
<h2>Start here</h2><p><a class="button" href="installation.html">Installation guide →</a></p><p>Images stay on your computer. AI-generated detail and colors are estimates; compare results with the original.</p>'''
entries = [('index.html', 'Home', home), ('installation.html', 'Installation', installation)] + [(slug, title, body) for slug, (title, body) in zip(slugs, pages)]
css = '''*{box-sizing:border-box}body{margin:0;background:#10151c;color:#dce4ee;font:16px/1.75 system-ui,sans-serif}a{color:#80e8c7}header{padding:22px 5%;border-bottom:1px solid #2d3947;display:flex;align-items:center;gap:14px}header img{width:48px;height:48px}header strong{font-size:20px}header>a{margin-left:auto}.layout{max-width:1400px;margin:auto;display:grid;grid-template-columns:285px 1fr;gap:40px;padding:32px}nav a{display:block;padding:8px 12px;text-decoration:none;border-radius:6px;font-size:14px}nav a[aria-current]{background:#25483f;color:#a6ffe1}main{min-width:0;max-width:900px;padding:30px;background:#171e27;border:1px solid #2d3947;border-radius:14px}h1{font-size:34px;line-height:1.25;margin-top:0;color:#fff}h2,h3{color:#80e8c7;line-height:1.4;margin-top:30px}p,li{margin-bottom:14px}.lead{font-size:26px;color:#fff}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}.cards section{padding:15px;background:#10151c;border-radius:8px}.cards h2{margin-top:0;font-size:20px}.button{display:inline-block;padding:10px 18px;background:#80e8c7;color:#10251e;border-radius:7px;text-decoration:none;font-weight:700}footer{padding:28px 5%;color:#9fabb9;font-size:13px}.skip{position:absolute;left:-10000px}.skip:focus{left:10px;background:#10151c;padding:10px}@media(max-width:850px){.layout{grid-template-columns:1fr;padding:16px;gap:18px}nav{display:flex;flex-wrap:wrap;gap:4px}main{padding:22px}.cards{grid-template-columns:1fr}h1{font-size:28px}header{flex-wrap:wrap}}'''
(out / 'style.css').write_text(css, encoding='utf-8')
shutil.copy2(ROOT / 'assets/hmr-upscale.ico', out / 'favicon.ico')
shutil.copy2(ROOT / 'assets/hmr-upscale.png', out / 'icon.png')
(out / '.nojekyll').touch()
for filename, title, body in entries:
    nav = ''.join(f'<a href="{slug}"' + (' aria-current="page"' if slug == filename else '') + f'>{escape(name)}</a>' for slug, name, _ in entries)
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(title)} | HMR Studio • Upscale</title><meta name="description" content="Local AI image upscaling and restoration for Windows. Installation, features and documentation."><link rel="icon" href="favicon.ico"><link rel="stylesheet" href="style.css"></head><body><a class="skip" href="#content">Skip to content</a><header><img src="icon.png" alt=""><strong>HMR Studio • Upscale</strong><a href="{repo}">GitHub repository ↗</a></header><div class="layout"><nav aria-label="Documentation">{nav}</nav><main id="content"><h1>{escape(title)}</h1>{body}</main></div><footer>Copyright © 2026 Hanafi Mohd Radi. All rights reserved. Third-party components retain their respective licenses. <a href="{repo}/blob/main/THIRD_PARTY_NOTICES.md">Credits & notices</a></footer></body></html>'''
    (out / filename).write_text(html, encoding='utf-8')
print(f'Built {len(entries)} documentation pages.')
