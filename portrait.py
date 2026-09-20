"""Aligned GFPGAN restoration, blended into a Real-ESRGAN background."""
import numpy as np
from PIL import Image, ImageOps
from engine import ROOT, check_cancel, download_asset

ASSETS = {
    'GFPGANv1.4.pth': 'https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth',
    'detection_Resnet50_Final.pth': 'https://github.com/xinntao/facexlib/releases/download/v0.1.0/detection_Resnet50_Final.pth',
    'parsing_parsenet.pth': 'https://github.com/xinntao/facexlib/releases/download/v0.2.2/parsing_parsenet.pth',
}

class PortraitRestorer:
    def __init__(self, device, status=lambda _: None, cancel=lambda: False):
        import torch
        from spandrel import ModelLoader
        from facexlib.utils.face_restoration_helper import FaceRestoreHelper
        for name, url in ASSETS.items():
            download_asset(name, url, status, cancel)
        check_cancel(cancel)
        status('Loading portrait restoration…')
        self.device = torch.device(device)
        self.network = ModelLoader().load_from_file(str(ROOT / 'models/GFPGANv1.4.pth')).model.to(self.device).eval()
        self.helper = FaceRestoreHelper(1, face_size=512, use_parse=True,
                                        device=self.device, model_rootpath=str(ROOT / 'models'))

    def restore(self, source, background, strength=0.75, status=lambda _: None, cancel=lambda: False):
        import torch
        if not 0 <= strength <= 1:
            raise ValueError('Portrait strength must be between 0 and 1.')
        if strength == 0:
            return background
        check_cancel(cancel)
        with (source.copy() if isinstance(source, Image.Image) else Image.open(source)) as image:
            rgb = ImageOps.exif_transpose(image).convert('RGB')
        helper = self.helper
        helper.clean_all()
        helper.set_upscale_factor(background.width / rgb.width)
        helper.read_image(np.array(rgb)[:, :, ::-1].copy())
        status('Detecting and aligning faces…')
        with torch.inference_mode():
            count = helper.get_face_landmarks_5(only_center_face=False, resize=640, eye_dist_threshold=5)
            check_cancel(cancel)
            if not count:
                status('No suitable face detected; keeping the upscaled image.')
                return background
            helper.align_warp_face()
            for index, face in enumerate(helper.cropped_faces):
                check_cancel(cancel)
                status(f'Restoring face {index + 1}/{count}…')
                tensor = torch.from_numpy(face[:, :, ::-1].copy()).permute(2, 0, 1).float().unsqueeze(0)
                tensor = (tensor.to(self.device) / 255 - 0.5) / 0.5
                # GFPGAN expects [-1,1]. Fixed noise makes repeated runs reproducible.
                restored = self.network(tensor, return_rgb=False, randomize_noise=False)[0]
                if not torch.isfinite(restored).all():
                    raise RuntimeError('Face restoration produced invalid pixels. Try CPU processing.')
                pixels = ((restored.squeeze(0).clamp(-1, 1) + 1) * 127.5).permute(1, 2, 0).cpu().numpy()
                pixels = pixels[:, :, ::-1]
                blended = np.clip(pixels * strength + face * (1 - strength), 0, 255).round().astype(np.uint8)
                helper.add_restored_face(blended)
            check_cancel(cancel)
            status('Blending restored faces into image…')
            helper.get_inverse_affine(None)
            result = helper.paste_faces_to_input_image(upsample_img=np.array(background.convert('RGB'))[:, :, ::-1].copy())
        check_cancel(cancel)
        output = Image.fromarray(result[:, :, ::-1].astype(np.uint8))
        if output.size != background.size:
            output = output.resize(background.size, Image.Resampling.LANCZOS)
        if 'A' in background.getbands():
            output.putalpha(background.getchannel('A'))
        output.info.update(background.info)
        helper.clean_all()
        return output
