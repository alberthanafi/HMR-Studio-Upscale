"""Offline user guide and product attribution."""
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QListWidget, QTextBrowser, QSplitter, QWidget)

PAGES = [
    ('What is HMR Studio?', '''
        <p>HMR Studio brings local image tools to your Windows desktop. HMR Upscale is its
        Real-ESRGAN image upscaler, designed to enlarge photos and artwork with AI.</p>
        <h3>Designed for local work</h3><p>Image processing happens on your computer.
        CUDA uses your NVIDIA graphics card; CPU mode is available when needed.</p>
        <h3>A good starting point</h3><p>Choose Photo · Real-ESRGAN 4×, NVIDIA CUDA,
        256-pixel tiles and FP16. Save as PNG to retain transparency.</p>
        <p>AI can invent or alter fine details. Review the result before using it.</p>'''),
    ('Quick start', '''
        <p>The left column compares original and processed images, the middle column holds the
        image queue, and the right column contains feature tabs. Drag column dividers to resize.
        Click × beside an image to remove it from the queue; its file is not deleted.
        Removal is disabled during processing. Live hardware readings are at the top;
        elapsed time, ETA, tile progress and the activity log are at the bottom.</p>
        <ol><li>Click <b>Add images</b> or drop image files into the window.</li>
        <li>Select a photo or anime model and choose 2×, 3× or 4× output.</li>
        <li>Choose NVIDIA CUDA for GPU acceleration, or CPU.</li>
        <li>Choose PNG or JPEG and an output folder.</li>
        <li>Enable the desired features and click <b>Process images</b>. Follow progress and messages below the preview.</li>
        <li>Select a completed image and move the comparison slider. Click
        <b>Open output folder</b> to find the saved files.</li></ol>
        <p>The selected model downloads on first use. Subsequent runs use the local copy.</p>'''),
    ('Models and output size', '''
        <p><b>Photo · Real-ESRGAN 4×:</b> general photographs and detailed images.</p>
        <p><b>Anime · Real-ESRGAN 4×:</b> illustrations and anime-style artwork.</p>
        <p><b>Photo · Real-ESRGAN 2×:</b> native 2× enlargement.</p>
        <p><b>General photo · Real-ESRGAN v3:</b> an alternative smoother restoration model.</p>
        <p><b>Photo · RealESRNet 4×:</b> a non-GAN alternative with softer detail and less synthesized texture.</p>
        <p><b>Photo · Weak denoise v3:</b> weaker denoising retains more source texture and noise. Best compared with General v3 on clean sources.</p>
        <p><b>Anime · Fast v3 4×:</b> a compact model for illustrations and animation stills. This app processes images, not video files.</p>
        <p>All seven models run locally on CUDA or CPU. Each downloads on first use.
        Model descriptions appear below the selector. Compare results on your source;
        no model is best for every image.</p>
        <h3>Damaged or already enlarged sources</h3><p>Enable <b>Clean compressed / already enlarged input</b>
        to reduce the source to 50% before inference. This can suppress existing block structure
        instead of sharpening it. Final dimensions remain the selected multiple of the original.
        It can soften detail; leave it off for clean originals. Missing facial detail cannot be
        faithfully recovered just by enlarging. PNG files record processing settings in metadata.</p>
        <h3>Model scale versus output size</h3><p>The model first processes at its native scale.
        If the requested output scale differs, the result is resized afterward. Choosing 2×
        output with a 4× model still requires a 4× intermediate image.</p>
        <h3>Portrait preset and face restoration</h3><p>Apply portrait preset selects General v3,
        cleanup, 85% GFPGAN face restoration, FP32 and 2× PNG. Face restoration is optional:
        Off, Gentle (60%), Strong (85%), or Maximum (100%). It aligns detected faces and blends
        reconstructed detail back into the image. Stronger settings can change facial features.
        Hands and clothing are not face-restored. If no face is detected, the upscaled image is kept.</p>
        <p>Face models download on first use and then work offline. Cancel is checked between faces;
        ETA excludes face restoration. Image files only; video is not included.</p>'''),
    ('Feature switches and presets', '''
        <p>Settings are grouped into four tabs: <b>Enhance</b> for upscaling and texture,
        <b>Faces</b> for the portrait preset and face enhancer, <b>Restore</b> for colorization
        and damage masks, and <b>Output</b> for processing and saving. Hover over a control for details.</p>
        <p>Each processing feature has an independent on/off switch. Turning off AI upscaling
        keeps the original dimensions (1×), while repair, colorization, detail and face enhancement
        can still run. With every processing feature off, image pixels are preserved; the output
        is still saved in your chosen format.</p>
        <p><b>Portrait preset ON</b> applies General v3, cleanup, 85% face_enhancer, 2× PNG and FP32.
        Turning it OFF restores the portrait/upscale settings from before activation. It does not
        toggle colorization, repair or detail. Those remain independently controlled.</p>
        <p><b>face_enhancer</b> separately enables GFPGAN. Select Gentle, Strong or Maximum.
        An Off strength also bypasses face restoration.</p>'''),
    ('Colorization preset', '''
        <p>Enable Colorization preset to predict colors for a black-and-white photograph using
        the ECCV16 colorization network by Richard Zhang and collaborators. It preserves source
        luminance and alpha while replacing chroma. Existing colors will also be replaced when enabled.</p>
        <p>Predicted colors are plausible guesses, not recovered historical colors. Inspect skin,
        clothing and backgrounds before keeping the result. The model runs locally on the selected
        device and downloads only on first use.</p>'''),
    ('Detail and hyper-realistic detail', '''
        <p><b>Detail preset</b> enhances existing edges and texture outside automatically detected
        face areas. <b>Hyper-realistic detail</b> increases texture and broad local contrast and also
        protects detected faces. Either switch can run independently; when both are enabled,
        the stronger pass runs once.</p>
        <p>These are texture/contrast filters, not generative reconstruction. They do not invent
        objects or guarantee realistic missing detail. Very damaged images can look oversharpened.</p>
        <p>Face protection applies to these detail passes only. Upscaling, colorization, repair and
        face_enhancer can still modify faces when separately enabled. Detection can miss small,
        obscured or profile faces; the activity log reports the number detected.</p>'''),
    ('Repair tears, scratches and missing areas', '''
        <ol><li>Select an image in the queue.</li><li>Click <b>Edit damage mask for selected image</b>.</li>
        <li>Paint white over the damage, including its edges. Use Erase or Undo to protect good areas.
        You can also import a same-size black/white mask.</li><li>Save the mask and enable Damage repair.</li>
        <li>Repeat for every queued image, then start processing.</li></ol>
        <p>LaMa fills marked tears, heavy scratches and missing regions using surrounding context.
        Unmarked pixels are unchanged by the repair stage. Other enabled stages may change them afterward.
        Transparent pixels inside marked damage become opaque.</p>
        <p>Repair uses at most a 1024-pixel longest-side working image to bound GPU memory. Only the
        repaired region is resized and composited back. Large holes or missing faces may require
        repeated manual editing; complete, faithful reconstruction cannot be guaranteed.</p>
        <p>The editor supports sources up to 30 MP. Masks are saved in the masks folder, associated
        with the source path, and restored when that source is re-added. If you replace a source
        at the same path, inspect or clear its old mask. Empty, fully white or mismatched masks are rejected.</p>
        <p>Processing order: repair → colorize → upscale → protected detail → face_enhancer → save.
        Tile ETA excludes all optional restoration stages. Cancel waits for the current model pass.</p>'''),
    ('CUDA, tiles and FP16', '''
        <p><b>NVIDIA CUDA</b> runs inference on GPU 0. <b>CPU</b> uses your processor and is slower.</p>
        <p><b>Tile size</b> sets how much of the source is processed at once. Start at 256;
        use 128 or 64 if GPU memory runs out. Larger tiles can consume substantially more VRAM.</p>
        <p><b>FP16</b> uses half precision on supported CUDA models to reduce memory use and
        improve speed. It has no effect in CPU mode. Disable it if results show precision artifacts.</p>
        <p>Tiles overlap to supply context. Tiling reduces GPU memory demand, but the assembled
        image still requires system RAM.</p>'''),
    ('Progress and estimated time', '''
        <p>The status area shows the current stage, queue percentage, image number, tile count
        and elapsed time. Queue progress counts processed files, including failures;
        100% does not mean every image succeeded.</p>
        <p><b>Image ETA</b> estimates remaining AI tile processing for the current image from
        completed tiles. It is not an estimate for the entire batch. Loading, final resizing
        and saving are excluded. The estimate adjusts as work progresses.</p>
        <p>The activity log records stages, saved paths and errors. Select text to copy it.
        Failure tracebacks are appended to <b>error.log</b> in the application folder.</p>
        <p>Cancel takes effect after the current tile or download read. Already saved results remain.</p>'''),
    ('CPU, GPU and memory readings', '''
        <p>The live readings show <b>system-wide</b> usage, including other applications.</p>
        <ul><li><b>CPU:</b> overall processor utilization.</li>
        <li><b>GPU:</b> NVIDIA GPU 0 utilization.</li>
        <li><b>VRAM:</b> used and total graphics memory.</li>
        <li><b>RAM:</b> used and total system memory, plus percentage.</li></ul>
        <p>Readings refresh roughly every second, subject to sensor response time. An unavailable
        reading means the sensor could not be queried; it does not mean zero usage.</p>'''),
    ('Output formats and comparison', '''
        <p><b>PNG</b> retains transparency. The alpha channel is resized with Lanczos.
        <b>JPEG</b> uses a white background for transparent areas.</p>
        <p>Results use the source filename plus the scale, such as <b>photo_4x.png</b>.
        A number is added when a filename already exists. Existing files are never overwritten.</p>
        <p>Select a completed queue item to compare it. The slider displays the original on
        the left and the upscaled version on the right. Move the slider fully left for original only,
        or fully right for upscaled only. Comparison is disabled until a result is available.
        The preview is scaled to fit the window.</p>
        <p>EXIF orientation is applied and ICC profiles are preserved. Other metadata is not copied.
        Animated inputs use the first frame. 16-bit and floating-point images are not supported.</p>'''),
    ('Troubleshooting and size limits', '''
        <h3>120 megapixel limit</h3><p>Both the native model intermediate and requested output
        must stay within the processing limit. A smaller tile does not reduce image dimensions.
        Resize or crop the source, or try the 2× model with 2× output. The error gives the dimensions.</p>
        <h3>GPU memory is full</h3><p>Choose 128 or 64 pixel tiles and retry. Close other GPU-heavy
        applications if necessary.</p>
        <h3>CUDA unavailable</h3><p>Run Install.cmd, check the NVIDIA driver, or choose CPU mode.</p>
        <h3>Download or model error</h3><p>Downloads retry automatically. Check your connection
        and retry the batch. If a cached model is corrupt, remove only that model’s .pth file
        from the models folder and retry to download it again.</p>
        <h3>Cannot save</h3><p>Check free disk space and choose a writable output folder.</p>
        <h3>A file failed</h3><p>Select its queue entry for the error. The activity log keeps
        the message, and the batch continues to the next file.</p>'''),
    ('Privacy and source safety', '''
        <p>Images are processed locally and are not uploaded. An internet connection is needed
        to install dependencies and download a model for the first time. Cached models work offline.</p>
        <p>Original images remain unchanged. Results are written to the selected output folder
        with unique names. Error logs can contain local file paths.</p>
        <p>Help and documentation are bundled with the application and work offline.</p>'''),
    ('About HMR Studio', '''
        <p style="color:#79e4bf"><b>HMR Studio • Upscale</b></p>
        <p style="color:#79e4bf">Copyright © 2026 Hanafi Mohd Radi. All rights reserved.</p>
        <p>HMR Upscale is a Windows desktop image upscaling application in HMR Studio.</p>
        <h3>Technology</h3><p>Python, PySide6 / Qt, PyTorch CUDA, Real-ESRGAN models,
        Spandrel, GFPGAN, facexlib, ECCV16 colorization, LaMa, OpenCV, Pillow, NumPy and psutil.</p>
        <h3>Third-party acknowledgments</h3><p>Real-ESRGAN by Xintao Wang and contributors
        supplies the pretrained models. Spandrel provides model loading and architecture support.
        Colorization uses work by Richard Zhang, Phillip Isola and Alexei A. Efros.
        Damage repair uses LaMa with the simple-lama-inpainting TorchScript distribution.
        This is an independent interface, not an official Real-ESRGAN release.</p>
        <h3>Copyright and third-party components</h3><p>The copyright notice applies to original
        HMR Studio application work. Third-party software and model components retain their
        respective copyrights and licenses. See the application README and installed packages
        for credits and license notices.</p>'''),
]


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Help · HMR Studio')
        self.resize(1080, 760)
        self.setMinimumSize(800, 560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(16)
        title = QLabel('Help & documentation')
        title.setStyleSheet('font-size: 23pt; font-weight: 600;')
        layout.addWidget(title)
        subtitle = QLabel('HMR Studio • Upscale   /   Your guide to better image results')
        subtitle.setStyleSheet('color: #9eacbc;')
        layout.addWidget(subtitle)
        toolbar = QHBoxLayout()
        home = QPushButton('Home')
        home.clicked.connect(lambda: self.navigate(0))
        about = QPushButton('About HMR Studio')
        about.clicked.connect(lambda: self.navigate(len(PAGES)-1))
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search documentation…')
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName('Search documentation')
        self.search.textChanged.connect(self.filter_pages)
        toolbar.addWidget(home)
        toolbar.addWidget(about)
        toolbar.addWidget(self.search, 1)
        layout.addLayout(toolbar)
        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(14)
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(8)
        self.topic_count = QLabel('BROWSE TOPICS')
        self.topic_count.setStyleSheet('color: #9eacbc; font-size: 9pt; font-weight: 600;')
        sidebar_layout.addWidget(self.topic_count)
        self.topics = QListWidget()
        self.topics.addItems(['Overview', 'Quick start', 'AI models & image size',
            'Feature switches & presets', 'Colorization', 'Detail & texture',
            'Damage repair & masks', 'CUDA & performance', 'Progress & time estimates',
            'Live hardware usage', 'Saving & comparing images', 'Troubleshooting',
            'Privacy & original files', 'About HMR Studio'])
        for index, (page_title, _) in enumerate(PAGES):
            self.topics.item(index).setToolTip(page_title)
        self.topics.setWordWrap(True)
        self.topics.setTextElideMode(Qt.ElideNone)
        self.topics.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.topics.setStyleSheet('QListWidget {padding: 6px;} QListWidget::item {padding: 10px 8px; border: none; margin-bottom: 2px;}')
        sidebar.setMinimumWidth(245)
        sidebar_layout.addWidget(self.topics)
        self.topics.setAccessibleName('Documentation topics')
        self.topics.currentRowChanged.connect(self.show_page)
        self.browser = QTextBrowser()
        self.browser.setAccessibleName('Help content')
        self.browser.setStyleSheet('QTextBrowser { background: #13181f; border: 1px solid #2a323c; border-radius: 8px; padding: 24px; color: #dce3eb; }')
        self.browser.setFont(QFont('Segoe UI', 11))
        self.browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        split.addWidget(sidebar)
        split.addWidget(self.browser)
        split.setSizes([260, 750])
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setCollapsible(0, False)
        split.setCollapsible(1, False)
        layout.addWidget(split, 1)
        close = QPushButton('Close')
        close.clicked.connect(self.close)
        layout.addWidget(close, alignment=Qt.AlignRight)
        self.navigate(0)

    def navigate(self, index):
        self.search.clear()
        self.topics.setCurrentRow(index)
        self.show_page(index)

    def show_page(self, index):
        if index < 0:
            return
        title, body = PAGES[index]
        self.browser.setHtml('<style>h1 {font-size:22px; color:#f1f5fa; margin-top:0; margin-bottom:20px;} '
                             'h3 {font-size:16px; color:#79e4bf; margin-top:24px; margin-bottom:10px;} '
                             'p {line-height:150%; margin-top:0; margin-bottom:14px;} '
                             'li {line-height:150%; margin-bottom:10px;} </style>'
                             f'<h1>{escape(title)}</h1>{body}')
        self.browser.verticalScrollBar().setValue(0)

    def filter_pages(self, query):
        query = query.strip().casefold()
        visible = []
        for index, (title, body) in enumerate(PAGES):
            match = query in (title + ' ' + body).casefold()
            self.topics.item(index).setHidden(not match)
            if match:
                visible.append(index)
        self.topic_count.setText(f'{len(visible)} MATCHING TOPICS' if query else 'BROWSE TOPICS')
        if not visible:
            self.topics.setCurrentRow(-1)
            self.browser.setHtml('<h1>No matching topics</h1><p>Try another search or clear the search field.</p>')
        else:
            index = self.topics.currentRow()
            self.topics.setCurrentRow(index if index in visible else visible[0])
            self.show_page(self.topics.currentRow())
