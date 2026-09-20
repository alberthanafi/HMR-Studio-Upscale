"""Real-ESRGAN inference using official weights and Spandrel's RRDB loader."""
from pathlib import Path
import math
import os
import tempfile
import urllib.request
import json

import numpy as np
from PIL import Image, ImageOps, PngImagePlugin

ROOT = Path(__file__).resolve().parent
MODELS = {
    'Photo · Real-ESRGAN 4×': ('RealESRGAN_x4plus', 'v0.1.0'),
    'Anime · Real-ESRGAN 4×': ('RealESRGAN_x4plus_anime_6B', 'v0.2.2.4'),
    'Photo · Real-ESRGAN 2×': ('RealESRGAN_x2plus', 'v0.2.1'),
    'General photo · Real-ESRGAN v3': ('realesr-general-x4v3', 'v0.2.5.0'),
    'Photo · RealESRNet 4×': ('RealESRNet_x4plus', 'v0.1.1'),
    'Photo · Weak denoise v3': ('realesr-general-wdn-x4v3', 'v0.2.5.0'),
    'Anime · Fast v3 4×': ('realesr-animevideov3', 'v0.2.5.0'),
}
MODEL_DESCRIPTIONS = {
    'Photo · Real-ESRGAN 4×': 'General photos. Native 4× restoration with strong AI texture.',
    'Anime · Real-ESRGAN 4×': 'Anime and illustrations. Native 4× model for drawn edges and artwork.',
    'Photo · Real-ESRGAN 2×': 'Native 2× photo model. Avoids the larger 4× intermediate image.',
    'General photo · Real-ESRGAN v3': 'Compact native 4× general model with denoising. A smoother photo option.',
    'Photo · RealESRNet 4×': 'Native 4× non-GAN alternative. Softer detail with less synthesized texture.',
    'Photo · Weak denoise v3': 'Native 4× general model with weaker denoising. Retains more texture and source noise.',
    'Anime · Fast v3 4×': 'Compact native 4× anime model. Processes individual illustrations and animation stills.',
}
EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff'}

class Cancelled(Exception):
    pass

def check_cancel(cancel):
    if cancel():
        raise Cancelled('Cancelled')

def model_path(name, status=lambda _: None, cancel=lambda: False):
    for attempt in range(3):
        try:
            return _download_model(name, status, cancel)
        except OSError:
            check_cancel(cancel)
            if attempt == 2:
                raise
            status(f'Download interrupted. Retrying ({attempt + 2}/3)…')

def _download_model(name, status, cancel):
    model, version = MODELS[name]
    url = f'https://github.com/xinntao/Real-ESRGAN/releases/download/{version}/{model}.pth'
    return download_asset(model + '.pth', url, status, cancel)

def download_asset(filename, url, status=lambda _: None, cancel=lambda: False):
    for attempt in range(3):
        try:
            return _download_asset(filename, url, status, cancel)
        except OSError:
            check_cancel(cancel)
            if attempt == 2:
                raise
            status(f'Download interrupted. Retrying ({attempt + 2}/3)…')

def _download_asset(filename, url, status, cancel):
    folder = ROOT / 'models'
    folder.mkdir(exist_ok=True)
    destination = folder / filename
    if destination.exists():
        return destination
    fd, temporary = tempfile.mkstemp(dir=folder, suffix='.download')
    try:
        with os.fdopen(fd, 'w+b') as output:
            for retry in range(20):
                check_cancel(cancel)
                received = output.tell()
                request = urllib.request.Request(url, headers={'Range': f'bytes={received}-'} if received else {})
                try:
                    with urllib.request.urlopen(request, timeout=30) as response:
                        if received and response.status != 206:
                            output.seek(0)
                            output.truncate()
                            received = 0
                        elif received and not response.headers.get('Content-Range', '').startswith(f'bytes {received}-'):
                            raise OSError('Server returned an invalid download range.')
                        total = int(response.headers.get('Content-Length', 0)) + received
                        while True:
                            check_cancel(cancel)
                            block = response.read(256 * 1024)
                            if not block:
                                break
                            output.write(block)
                            received += len(block)
                            status(f'Downloading {filename}: {received / 1048576:.0f} / {total / 1048576:.0f} MB')
                        if not received or received != total:
                            raise OSError('Incomplete model download.')
                        break
                except OSError:
                    if retry == 19:
                        raise
                    status(f'Resuming {filename} after interrupted connection…')
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return destination

def load_model(name, device, half, status=lambda _: None, cancel=lambda: False):
    import torch
    from spandrel import ModelLoader, ImageModelDescriptor
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA is unavailable. Run Install.cmd and check your NVIDIA driver, or select CPU.')
    path = model_path(name, status, cancel)
    check_cancel(cancel)
    status('Loading Real-ESRGAN…')
    model = ModelLoader().load_from_file(str(path))
    if not isinstance(model, ImageModelDescriptor):
        raise RuntimeError('Unsupported model file.')
    model.to(device).eval()
    if half and device == 'cuda' and model.supports_half:
        model.half()
    return model

def upscale(source, model, scale=4, tile=256, progress=lambda _: None, cancel=lambda: False,
            report=lambda _: None, cleanup=False):
    import torch
    if scale not in (2, 3, 4) or tile < 16:
        raise ValueError('Invalid scale or tile size.')
    with (source.copy() if isinstance(source, Image.Image) else Image.open(source)) as original:
        if original.mode.startswith('I') or original.mode == 'F':
            raise ValueError('16-bit/float images are not supported. Convert to 8-bit RGB first.')
        image = ImageOps.exif_transpose(original)
        alpha = image.convert('RGBA').getchannel('A') if 'A' in image.getbands() or 'transparency' in image.info else None
        rgb = image.convert('RGB')
        icc = original.info.get('icc_profile')
    width, height = rgb.size
    target = (width * scale, height * scale)
    # Optional resampling removes enlarged compression/block structure before inference.
    # Final dimensions and alpha always derive from the original, not the reduced input.
    if cleanup:
        report(dict(stage='Reducing source artifacts', done=0, total=0))
        rgb = rgb.resize((max(1, width // 2), max(1, height // 2)), Image.Resampling.LANCZOS)
        width, height = rgb.size
    native = model.scale
    if max(width * height * native ** 2, target[0] * target[1]) > 120_000_000:
        limit = int(math.sqrt(120_000_000 / max(native, scale) ** 2))
        raise ValueError(f'Processing source {width:,} × {height:,}; requested output {target[0]:,} × {target[1]:,}. '
                         f'The {native}× model needs a {width*native:,} × {height*native:,} intermediate image. '
                         f'This exceeds the 120 MP processing limit. Resize the source to at most '
                         f'{limit:,} × {limit:,} (or equivalent area), or use the 2× model with 2× output. '
                         'A smaller tile does not change this image-size limit.')
    output = Image.new('RGB', (width * native, height * native))
    total = math.ceil(width / tile) * math.ceil(height / tile)
    report(dict(stage='Upscaling', done=0, total=total, width=width, height=height))
    done = 0
    # Context overlap is discarded, so tile borders do not become hard seams.
    pad = 64
    with torch.inference_mode():
        for top in range(0, height, tile):
            for left in range(0, width, tile):
                check_cancel(cancel)
                right, bottom = min(left + tile, width), min(top + tile, height)
                x0, y0 = max(0, left - pad), max(0, top - pad)
                x1, y1 = min(width, right + pad), min(height, bottom + pad)
                array = np.array(rgb.crop((x0, y0, x1, y1)), dtype=np.float32) / 255
                tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0).to(device=model.device, dtype=model.dtype)
                result = model(tensor).squeeze(0).clamp_(0, 1).permute(1, 2, 0)
                pixels = (result.float().cpu().numpy() * 255).round().astype(np.uint8)
                patch = Image.fromarray(pixels).crop(((left-x0)*native, (top-y0)*native,
                                                    (right-x0)*native, (bottom-y0)*native))
                output.paste(patch, (left*native, top*native))
                del tensor, result, pixels
                done += 1
                progress(done / total)
                report(dict(stage='Upscaling', done=done, total=total))
    check_cancel(cancel)
    report(dict(stage='Finalizing image', done=total, total=total))
    if output.size != target:
        output = output.resize(target, Image.Resampling.LANCZOS)
    if alpha is not None:
        output.putalpha(alpha.resize(target, Image.Resampling.LANCZOS))
    if icc:
        output.info['icc_profile'] = icc
    return output

def save_output(image, source, folder, scale, extension='png', metadata=None):
    """Reserve a unique filename exclusively; never overwrite another image."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stem = f'{Path(source).stem}_{scale}x'
    index = 0
    while True:
        path = folder / f'{stem}{"_" + str(index) if index else ""}.{extension}'
        try:
            handle = path.open('xb')
            break
        except FileExistsError:
            index += 1
    try:
        with handle:
            if extension == 'jpg' and image.mode == 'RGBA':
                background = Image.new('RGB', image.size, 'white')
                background.paste(image, mask=image.getchannel('A'))
                image = background
            options = {}
            if extension == 'png' and metadata is not None:
                info = PngImagePlugin.PngInfo()
                info.add_text('HMR Upscale', json.dumps(metadata, ensure_ascii=False))
                options['pnginfo'] = info
            image.save(handle, format='JPEG' if extension == 'jpg' else 'PNG',
                       quality=95, icc_profile=image.info.get('icc_profile'), **options)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path
