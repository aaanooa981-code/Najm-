#!/usr/bin/env python3
"""Apply the user's approved red/gold star icon before Android APK signing.

Do NOT rewrite signed APKs. Inject source resources first so Gradle produces
a correctly aligned/signed final APK for Android vehicle displays.
"""
from pathlib import Path
import base64, struct

encoded=Path("ci/najm_approved_3d_logo_128.b64").read_text().strip()
png=base64.b64decode(encoded, validate=True)
assert png[:8] == b"\x89PNG\r\n\x1a\n"
width,height=struct.unpack(">II",png[16:24])
assert width == height == 128
assert __import__('hashlib').sha256(png).hexdigest() == 'f4c1c77eec04de3e02e6a8f8787e593b5bec57b2fc7f491b8bac25652101e752'

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
# Use the exact approved design for all home/launcher icon aliases.
import re
manifest=Path("SmartTube/smarttubetv/src/main/AndroidManifest.xml")
m=manifest.read_text()
m,count=re.subn(r'android:icon="[^"]+"','android:icon="@mipmap/najm_tube_icon"',m)
assert count>=1, "Android launcher icon attributes not found"
m=re.sub(r'android:roundIcon="[^"]+"','android:roundIcon="@mipmap/najm_tube_icon"',m)
manifest.write_text(m)
print(f"Newly approved user's red/gold 3D star and Arabic name icon ({width}x{height}) set in launcher and home.")
