# HMR Studio • Upscale

<img src="assets/hmr-upscale.png" width="112" alt="HMR Studio Upscale icon">

**Local AI image upscaling and restoration for Windows.**

[Documentation](https://alberthanafi.github.io/HMR-Studio-Upscale/) · [Installation](https://alberthanafi.github.io/HMR-Studio-Upscale/installation.html) · [Third-party credits](THIRD_PARTY_NOTICES.md)

A Windows desktop image upscaler using official Real-ESRGAN models, PyTorch CUDA and a native PySide6 interface.

## Start

1. Install Python 3.10–3.13 (64-bit) if needed.
2. Double-click **Install.cmd**. The first installation downloads several GB of CUDA-enabled PyTorch dependencies. No separate CUDA Toolkit is needed; an NVIDIA driver compatible with CUDA 12.8 is required.
3. Double-click **Launch HMR Upscale.vbs**.
4. Add or drop images, enable desired features, choose a model and output folder, then click **Process images**.

The application environment lives in `.venv` beside the source. This is a ready-to-launch Python desktop application, not a standalone packaged executable.

## Features

- Independent enable/disable controls for AI upscaling, cleanup, portrait preset, face_enhancer, colorization, detail, hyper-realistic detail and damage repair. Portrait OFF restores the pre-preset portrait/upscale settings; unrelated features retain their state.
- Colorization preset: local ECCV16 neural color prediction for black-and-white images. Existing chroma is replaced; inferred colors are not historically guaranteed.
- Detail preset: texture enhancement outside detected faces. Hyper-realistic detail is stronger multiscale sharpening/local contrast, not generative reconstruction. When both are on, the stronger pass runs once. Protection only applies to these passes and depends on face detection.
- Damage repair: local LaMa inpainting for painted tears, scratches and missing regions. Select each image and use **Edit damage mask** (paint, erase, undo, clear or import a same-size black/white mask). White means repair. Masks persist in `masks/`. A mask is required for every queued image when repair is enabled.
- Repair keeps unmasked pixels unchanged at its own stage; subsequent enabled stages can modify them. Inference is bounded to a 1024-pixel longest side, then only the masked result is composited at original size. The editor supports sources up to 30 MP. Complete or faithful reconstruction of large missing regions is not guaranteed.
- Pipeline order: repair → colorize → upscale → protected detail → face_enhancer → save. Disable AI upscaling to retain 1× dimensions. Tile ETA excludes the optional restoration stages.
- Portrait preset: General v3, source cleanup, GFPGAN 1.4 face restoration at 85%, FP32, 2× PNG output. Face restoration is optional (off, 60%, 85%, 100%); it reconstructs plausible details and can change facial features. It does not restore hands or clothing.
- Help button (F1) with searchable offline documentation and About HMR Studio / copyright information.
- NVIDIA CUDA acceleration, including RTX 50-series support through PyTorch's CUDA 12.8 build; optional CPU mode.
- Seven model choices: RealESRGAN_x4plus, RealESRGAN_x4plus_anime_6B, RealESRGAN_x2plus, realesr-general-x4v3, RealESRNet_x4plus, realesr-general-wdn-x4v3 and realesr-animevideov3.
- Batch queue, cancellable tile processing, per-file failures, before/after slider.
- Live timestamped activity/error log, queue percentage, image/tile counters and elapsed time. Full failure tracebacks are appended to `error.log`.
- Current-image ETA estimated from completed tiles; excludes loading, final resizing and saving. It recalculates during inference and is an approximation, not a batch completion guarantee.
- Live system-wide CPU and RAM usage, NVIDIA GPU 0 utilization and VRAM usage. Sensors refresh roughly every second; unavailable GPU readings are shown explicitly. NVIDIA queries run in a background thread with a timeout.
- 2×, 3× and 4× output; non-native scales are resized after neural inference.
- Overlapping tiles with configurable size and optional FP16.
- PNG transparency (alpha resized with Lanczos) or JPEG with a white alpha background.
- EXIF orientation applied, ICC profiles preserved, unique output names; originals are untouched.
- Model downloads cached in `models/`. After the first download, that model works offline. Images are never uploaded.

## Limits and troubleshooting

For compressed or previously enlarged inputs, try **General photo · Real-ESRGAN v3** with
**Clean compressed / already enlarged input** enabled. Cleanup processes a 50% resized source
to reduce existing block artifacts, preserving the requested final dimensions. It trades fine
detail for smoother structure; leave it off for clean originals. No upscaler can guarantee
reconstruction of missing detail or an exact match to a separately restored reference.
PNG outputs embed the selected processing settings for reproducibility. Tile context is 64 pixels.

Image files only; no video. Optional face restoration uses GFPGAN 1.4 and facexlib; its time is excluded from the tile ETA. Supports 8-bit image input. 16-bit and floating-point sources are rejected to avoid silently losing precision. Animated inputs use their first frame. Metadata other than ICC profiles is not copied. Output is capped at 120 megapixels; tiling reduces GPU memory but the result still uses system RAM.

If GPU memory fills up, choose 128 or 64 pixel tiles and retry. CUDA errors: rerun Install.cmd, update your NVIDIA driver, or choose CPU. Cancellation waits for the current tile or network read (up to its timeout). Failed model downloads can be retried. If a cached model is corrupt, remove that model's `.pth` file from `models/` and retry.

## Development

The documentation website is generated from the offline help content: run `python tools/build_docs.py` after editing the help pages. GitHub Pages serves the `docs/` directory on the `main` branch.

Run `.venv\Scripts\python.exe app.py` to see console errors. Run `.venv\Scripts\python.exe -m unittest discover -s tests -v` for automated checks. Dependencies are pinned for the CUDA runtime; application dependencies are in `requirements.txt`.

## Credits

Colorization: Richard Zhang, Phillip Isola and Alexei A. Efros, https://github.com/richzhang/colorization. Vendored architecture and copyright/license are in `vendor/colorizers/`. Repair: LaMa, https://github.com/advimman/lama, with the TorchScript distribution from https://github.com/enesmsahin/simple-lama-inpainting. Both additional models are downloaded from their maintainers and cached locally.

Real-ESRGAN by Xintao Wang and contributors: https://github.com/xinntao/Real-ESRGAN (BSD-3-Clause). Official pretrained weights are downloaded directly from that project's releases. Model loading and architecture implementations use Spandrel: https://github.com/chaiNNer-org/spandrel (MIT; bundled architectures retain their licenses). GUI uses PySide6/Qt (LGPLv3/GPLv3/commercial); PyTorch uses its BSD-style license. GFPGAN (TencentARC) and facexlib supply optional face restoration, detection and parsing. Their licenses remain in installed packages and the respective upstream projects. This project is an independent interface, not an official Real-ESRGAN release.

PyTorch installation reference: https://pytorch.org/get-started/locally/
