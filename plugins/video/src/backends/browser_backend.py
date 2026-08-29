import html as html_lib
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from plugins.video.src.encode import CHROMIUM_MISSING_HINT, frames_to_video
from plugins.video.src.storyboard import Storyboard, total_duration

_TEMPLATE = """<!doctype html><meta charset="utf-8"><style>
html,body{{margin:0;background:#000;overflow:hidden}}
.stage{{position:relative;width:{width}px;height:{height}px;overflow:hidden}}
.layer{{position:absolute;inset:0;background-repeat:no-repeat;background-position:center;
        background-size:{fit};opacity:0}}
.cap{{position:absolute;left:6%;right:6%;bottom:9%;
      font:700 {caption_px}px/1.15 -apple-system,system-ui,Segoe UI,sans-serif;
      color:#fff;text-shadow:0 4px 40px rgba(0,0,0,.85);opacity:0}}
</style>
<div class="stage" id="stage"></div>
<script>
const SLIDES = {slides_json};
const MOTION = {{
  'zoom-in':  ['scale(1)',            'scale(1.18)'],
  'zoom-out': ['scale(1.18)',         'scale(1)'],
  'pan-left': ['scale(1.15) translateX(3%)',  'scale(1.15) translateX(-3%)'],
  'pan-right':['scale(1.15) translateX(-3%)', 'scale(1.15) translateX(3%)'],
  'none':     ['scale(1)',            'scale(1)'],
}};
const stage = document.getElementById('stage');
const anims = [];
let start = 0;
SLIDES.forEach((s, i) => {{
  const layer = document.createElement('div');
  layer.className = 'layer';
  layer.style.backgroundImage = 'url("' + s.src + '")';
  stage.appendChild(layer);

  const dur = s.seconds * 1000;
  const tr  = s.transition_seconds * 1000;
  if (i > 0) start = start + SLIDES[i - 1].seconds * 1000 - tr;

  const [from, to] = MOTION[s.motion];
  anims.push(layer.animate([{{transform: from}}, {{transform: to}}],
    {{duration: dur, delay: start, fill: 'both'}}));

  if (i === 0) {{
    layer.style.opacity = 1;
  }} else {{
    anims.push(layer.animate([{{opacity: 0}}, {{opacity: 1}}],
      {{duration: Math.max(tr, 1), delay: start, fill: 'both'}}));
  }}

  if (s.caption) {{
    const cap = document.createElement('div');
    cap.className = 'cap';
    cap.textContent = s.caption;
    stage.appendChild(cap);
    anims.push(cap.animate(
      [{{opacity: 0, transform: 'translateY(40px)'}}, {{opacity: 1, transform: 'translateY(0)'}}],
      {{duration: 700, delay: start + 300, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'both'}}));
    anims.push(cap.animate([{{opacity: 1}}, {{opacity: 0}}],
      {{duration: 500, delay: start + dur - 500, fill: 'both'}}));
  }}
}});
anims.forEach(a => a.pause());
window.__seek = t => {{ anims.forEach(a => {{ a.currentTime = t; }}); }};
window.__seek(0);
</script>
"""


def build_scene_html(sb: Storyboard) -> str:
    slides = [
        {
            "src": slide.image.resolve().as_uri(),
            "caption": html_lib.escape(slide.caption) if slide.caption else "",
            "seconds": slide.seconds,
            "motion": slide.motion,
            "transition_seconds": 0.0 if slide.transition == "cut" else slide.transition_seconds,
        }
        for slide in sb.slides
    ]
    return _TEMPLATE.format(
        width=sb.preset.width,
        height=sb.preset.height,
        fit="contain" if sb.fit == "contain" else "cover",
        caption_px=max(int(sb.preset.width * 0.045), 24),
        slides_json=json.dumps(slides),
    )


def _launch_chromium(p):
    try:
        return p.chromium.launch(
            args=["--force-device-scale-factor=1", "--hide-scrollbars"]
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to launch Chromium — {CHROMIUM_MISSING_HINT}"
        ) from exc


def capture_frames(sb: Storyboard, workdir: Path) -> Path:
    frames_dir = workdir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    scene = workdir / "scene.html"
    scene.write_text(build_scene_html(sb))

    fps = sb.preset.fps
    frame_count = max(int(round(total_duration(sb) * fps)), 1)

    with sync_playwright() as p:
        browser = _launch_chromium(p)
        try:
            page = browser.new_page(
                viewport={"width": sb.preset.width, "height": sb.preset.height}
            )
            page.goto(scene.resolve().as_uri())
            page.wait_for_timeout(400)  # let images decode before the first capture
            for i in range(frame_count):
                page.evaluate("t => window.__seek(t)", i * 1000.0 / fps)
                # NEVER pass animations="disabled" here — it fast-forwards every
                # finite animation to completion and yields identical frames.
                page.screenshot(path=str(frames_dir / f"f{i:05d}.png"))
        finally:
            browser.close()

    return frames_dir


def render(sb: Storyboard, workdir: Path) -> Path:
    frames_dir = capture_frames(sb, workdir)
    return frames_to_video(frames_dir, sb.preset.fps, workdir / "silent.mp4")
