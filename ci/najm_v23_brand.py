#!/usr/bin/env python3
"""Apply the user's approved red/gold star icon before Android APK signing.

Do NOT rewrite signed APKs. Inject source resources first so Gradle produces
a correctly aligned/signed final APK for Android vehicle displays.
"""
from pathlib import Path
import base64, struct

encoded=Path("ci/najm_logo_96_palette_png.b64").read_text().strip()
png=base64.b64decode(encoded, validate=True)
assert png[:8] == b"\x89PNG\r\n\x1a\n"
width,height=struct.unpack(">II",png[16:24])
assert width == height == 96

resources=Path("SmartTube/smarttubetv/src/main/res/mipmap-nodpi")
resources.mkdir(parents=True,exist_ok=True)
(resources/"najm_tube_icon.png").write_bytes(png)
# Build a branded 320x180 banner if Pillow is available. The original launcher
# banner remains the fallback, preserving a valid image on SDK-limited runners.
try:
    from PIL import Image,ImageDraw,ImageFont
    from io import BytesIO
    icon=Image.open(BytesIO(png)).convert("RGBA")
    canvas=Image.new("RGBA",(320,180),(12,12,15,255))
    icon.thumbnail((156,156), Image.Resampling.LANCZOS)
    canvas.alpha_composite(icon,(12+(156-icon.width)//2,12+(156-icon.height)//2))
    draw=ImageDraw.Draw(canvas)
    font=ImageFont.load_default()
    draw.text((170,70),"NAJM TUBE",fill=(255,215,90,255),font=font)
    draw.rectangle((170,97,305,100),fill=(229,15,25,255))
    canvas.save(resources/"najm_tube_banner.png",format="PNG",optimize=True)
except ImportError:
    print("Pillow unavailable: original banner maintained")
print(f"Approved NAJM star/play logo preserved as Android source resource ({width}x{height}).")
