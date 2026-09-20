"""Optional local colorization, masked damage repair and face-protected detail."""
import numpy as np
from PIL import Image, ImageFilter, ImageDraw
from engine import ROOT, download_asset, check_cancel


def carry_image(rgb, source):
    if 'A' in source.getbands():
        rgb.putalpha(source.getchannel('A'))
    rgb.info.update(source.info)
    return rgb


class Colorizer:
    def __init__(self, device, status, cancel):
        import torch
        from vendor.colorizers.eccv16 import eccv16
        path = download_asset('colorization_release_v2-9b330a0b.pth',
            'https://colorizers.s3.us-east-2.amazonaws.com/colorization_release_v2-9b330a0b.pth', status, cancel)
        check_cancel(cancel)
        self.device = device
        self.model = eccv16(pretrained=False)
        self.model.load_state_dict(torch.load(path, map_location='cpu', weights_only=True))
        self.model.to(device).eval()

    def apply(self, image, cancel=lambda: False):
        import torch
        import cv2
        check_cancel(cancel)
        # Predict chroma from luminance. Existing colors are intentionally replaced.
        small = image.convert('RGB').resize((256, 256), Image.Resampling.LANCZOS)
        lab = cv2.cvtColor(np.array(small).astype(np.float32) / 255, cv2.COLOR_RGB2LAB)
        tensor = torch.from_numpy(lab[:, :, 0].copy()).unsqueeze(0).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            ab = self.model(tensor)[0].permute(1, 2, 0).cpu().numpy()
        check_cancel(cancel)
        # Limit peak RAM by composing the chroma in horizontal strips.
        output = Image.new('RGB', image.size)
        channels = [Image.fromarray(ab[:, :, i]).resize(image.size, Image.Resampling.BILINEAR) for i in range(2)]
        for top in range(0, image.height, 256):
            check_cancel(cancel)
            box = (0, top, image.width, min(top+256, image.height))
            rgb = np.array(image.crop(box).convert('RGB')).astype(np.float32) / 255
            lightness = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)[:, :, :1]
            color = np.stack([np.array(channel.crop(box)) for channel in channels], axis=2)
            converted = cv2.cvtColor(np.concatenate([lightness, color], axis=2), cv2.COLOR_LAB2RGB)
            output.paste(Image.fromarray((converted.clip(0, 1)*255).round().astype(np.uint8)), (0, top))
        return carry_image(output, image)


class DamageRepair:
    def __init__(self, device, status, cancel):
        import torch
        path = download_asset('big-lama.pt',
            'https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt', status, cancel)
        check_cancel(cancel)
        self.device = device
        self.model = torch.jit.load(str(path), map_location=device).eval()

    def apply(self, image, mask, cancel=lambda: False):
        import torch
        if mask.size != image.size:
            raise ValueError('Repair mask dimensions do not match this image. Edit its damage mask again.')
        mask = mask.convert('L').point(lambda x: 255 if x > 127 else 0)
        if mask.getbbox() is None:
            raise ValueError('Repair mask is empty. Paint over tears, scratches or missing regions first.')
        if mask.getextrema() == (255, 255):
            raise ValueError('The entire image is masked. Leave some undamaged context for repair.')
        check_cancel(cancel)
        # Bounded inference memory; unmasked source pixels remain bit-for-bit unchanged.
        size = image.size
        ratio = min(1, 1024 / max(size))
        working = (max(8, round(size[0]*ratio)), max(8, round(size[1]*ratio)))
        rgb = np.array(image.convert('RGB').resize(working, Image.Resampling.LANCZOS)).astype(np.float32) / 255
        # BOX retains thin marked scratches when the image is reduced.
        binary = np.array(mask.resize(working, Image.Resampling.BOX)) > 0
        h, w = binary.shape
        pad = ((0, (-h)%8), (0, (-w)%8))
        rgb = np.pad(rgb, (*pad, (0, 0)), mode='symmetric')
        binary = np.pad(binary, pad, mode='symmetric').astype(np.float32)
        tensor = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).to(self.device)
        holes = torch.from_numpy(binary).unsqueeze(0).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            restored = self.model(tensor, holes)[0, :, :h, :w]
            pixels = restored.permute(1, 2, 0).clamp(0, 1).cpu().numpy()
        check_cancel(cancel)
        restored = Image.fromarray((pixels*255).round().astype(np.uint8)).resize(size, Image.Resampling.LANCZOS)
        result = Image.composite(restored, image.convert('RGB'), mask)
        # Marked transparent holes become opaque; other alpha remains untouched.
        if 'A' in image.getbands():
            result.putalpha(Image.composite(Image.new('L', size, 255), image.getchannel('A'), mask))
        result.info.update(image.info)
        return result


class FaceProtector:
    def __init__(self, device, status, cancel):
        from facexlib.detection import init_detection_model
        from portrait import ASSETS
        name = 'detection_Resnet50_Final.pth'
        download_asset(name, ASSETS[name], status, cancel)
        check_cancel(cancel)
        self.model = init_detection_model('retinaface_resnet50', device=device, model_rootpath=str(ROOT/'models'))

    def mask(self, image, status=lambda _: None, cancel=lambda: False):
        import torch
        check_cancel(cancel)
        small = image.convert('RGB')
        small.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        with torch.inference_mode():
            faces = self.model.detect_faces(np.array(small)[:, :, ::-1].copy(), 0.9)
        mask = Image.new('L', image.size, 0)
        draw = ImageDraw.Draw(mask)
        sx, sy = image.width/small.width, image.height/small.height
        for face in faces:
            x0, y0, x1, y1 = face[:4]
            dx, dy = (x1-x0)*.2, (y1-y0)*.25
            draw.rectangle(((x0-dx)*sx, (y0-dy)*sy, (x1+dx)*sx, (y1+dy)*sy), fill=255)
        check_cancel(cancel)
        status(f'Detail protection: {len(faces)} face(s) detected. Review the result for missed faces.')
        # Expand feather outside solid mask, never weaken protection inside it.
        from PIL import ImageChops
        return ImageChops.lighter(mask, mask.filter(ImageFilter.GaussianBlur(max(2, image.width/150))))


def enhance_detail(image, protected, hyper=False):
    if protected.size != image.size:
        raise ValueError('Face-protection mask dimensions do not match.')
    rgb = image.convert('RGB')
    # Bounded unsharp masking boosts existing texture; it does not invent new objects.
    enhanced = rgb.filter(ImageFilter.UnsharpMask(radius=1.2, percent=110 if hyper else 55, threshold=3))
    if hyper:
        enhanced = enhanced.filter(ImageFilter.UnsharpMask(radius=8, percent=22, threshold=5))
    return carry_image(Image.composite(rgb, enhanced, protected), image)
