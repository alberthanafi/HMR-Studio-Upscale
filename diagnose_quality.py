from pathlib import Path
import json
import time
import numpy as np
from PIL import Image, ImageDraw
from engine import load_model, upscale, MODELS

folder = Path('test-output/quality')
folder.mkdir(parents=True, exist_ok=True)
source = Image.open('demo1/input1.png').convert('RGB')
box = (340, 440, 720, 780)
crop = source.crop(box)
crop.save(folder / 'crop.png')
panels = [('Input', crop.resize((760, 680)))]
metrics = {}
for name in [list(MODELS)[0], list(MODELS)[2]]:
    results = []
    for half in (False, True):
        model = load_model(name, 'cuda', half)
        start = time.monotonic()
        result = upscale(folder / 'crop.png', model, 2, 256)
        tag = ('x4' if name == list(MODELS)[0] else 'x2') + ('_fp16' if half else '_fp32')
        result.save(folder / (tag + '.png'))
        panels.append((tag, result))
        results.append(np.array(result).astype(float))
        print(tag, round(time.monotonic()-start, 2), flush=True)
        if not half:
            full = upscale(folder / 'crop.png', model, 2, 512)
            metrics[tag + '_tile_MAE'] = float(np.abs(np.array(full).astype(float)-results[-1]).mean())
        del model
    metrics[name + '_precision_MAE'] = float(np.abs(results[0]-results[1]).mean())
target = Image.open('demo1/yaya-celop1-upscaled2.png').convert('RGB')
sx, sy = target.width/source.width, target.height/source.height
panels.append(('Reference (different size)', target.crop(tuple(round(v*(sx if i%2==0 else sy)) for i,v in enumerate(box))).resize((760,680))))
canvas = Image.new('RGB', (760*3, 720*2), '#161b22')
draw=ImageDraw.Draw(canvas)
for index,(name,im) in enumerate(panels):
    x,y=index%3*760,index//3*720
    draw.text((x+10,y+8),name,fill='white')
    canvas.paste(im,(x,y+35))
canvas.save(folder/'comparison.jpg')
(folder/'metrics.json').write_text(json.dumps(metrics, indent=2))
print(metrics)
