import os, base64, asyncio, logging, tempfile, subprocess, time
from pathlib import Path
import requests
import edge_tts
import fal_client
import imageio_ffmpeg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CF_ACCOUNT = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
CF_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
FAL_KEY = os.getenv("FAL_KEY", "").strip()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("NajmCartoonFast")

STYLE_MAP = {
    "كرتون 3D": "high quality 3D animated family film, expressive stylized human characters, cinematic soft lighting, colorful polished render",
    "كرتون أطفال": "friendly children's cartoon, cute stylized people, bright colors, clean shapes, warm expressive faces",
    "أنمي": "high quality anime, cinematic composition, expressive characters, detailed background",
    "رسوم 2D": "clean hand-drawn 2D cartoon, consistent character sheets, colorful animation look",
}

VOICE_MAP = {
    "راوي": ("ar-SA-HamedNeural", "+0Hz", "+0%"),
    "طفل": ("ar-SA-ZariyahNeural", "+25Hz", "+8%"),
    "طفلة": ("ar-SA-ZariyahNeural", "+35Hz", "+10%"),
    "رجل": ("ar-SA-HamedNeural", "-5Hz", "-2%"),
    "امرأة": ("ar-SA-ZariyahNeural", "+0Hz", "+0%"),
}

def buttons(items, prefix):
    rows = []
    for i in range(0, len(items), 2):
        rows.append([InlineKeyboardButton(v, callback_data=f"{prefix}:{v}") for v in items[i:i+2]])
    return InlineKeyboardMarkup(rows)

def cf_enabled():
    return bool(CF_ACCOUNT and CF_TOKEN)

def fal_enabled():
    return bool(FAL_KEY)

def detect_cast(idea):
    cast = ["راوي"]
    if any(x in idea for x in ["طفل","ولد","صبي","يحيى"]): cast.append("طفل")
    if any(x in idea for x in ["طفلة","بنت","ميار"]): cast.append("طفلة")
    if any(x in idea for x in ["أم","امرأة","سيدة","عائشة","خديجة","حسنا","جدة"]): cast.append("امرأة")
    if any(x in idea for x in ["أب","رجل","عم","عمر","أحمد"]): cast.append("رجل")
    if "قطة" in idea or "قط" in idea: cast.append("قطة")
    return list(dict.fromkeys(cast))

def storyboard(idea, duration, style):
    # FAST MODE: fewer motion calls = much faster and cheaper.
    count = 2 if duration <= 15 else 3
    scene_seconds = max(5, duration / count)
    visual_style = STYLE_MAP.get(style, STYLE_MAP["كرتون 3D"])

    actions = [
        "Main child character walks naturally through the environment, full body visible, correct walking cycle, natural arm swing, blinking, subtle smile, camera tracking.",
        "Characters interact naturally, turn heads, gesture, walk, react with facial expressions, smooth cinematic camera movement.",
        "Warm story ending, characters walk together or interact naturally, subtle background motion, stable faces and clothing."
    ]

    scenes = []
    for i in range(count):
        image_prompt = (
            f"{visual_style}. Story: {idea}. Scene {i+1}/{count}. "
            "Show full-body cartoon people when appropriate. "
            "Keep EXACTLY the same main character identity in every scene: same face, hairstyle, age, clothes, colors, proportions. "
            "If a cat appears, keep identical fur color and markings. "
            "Strong story continuity, no text, no captions, no watermark."
        )
        motion_prompt = (
            f"Animated cartoon video. {actions[i % len(actions)]} "
            "Preserve identity, face, clothes and cartoon style. "
            "Natural body motion, no morphing, no extra limbs, no identity change."
        )
        narration = (
            f"كان يا ما كان. {idea}" if i == 0
            else "وتستمر الأحداث بحركة ومرح، حتى تصل القصة إلى نهاية جميلة."
        )
        scenes.append({
            "image_prompt": image_prompt,
            "motion_prompt": motion_prompt,
            "narration": narration,
            "seconds": scene_seconds
        })
    return scenes, detect_cast(idea)

def cloudflare_image(prompt, out_path):
    model = "@cf/black-forest-labs/flux-1-schnell"
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/{model}"
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {CF_TOKEN}", "Content-Type": "application/json"},
        json={"prompt": prompt, "num_steps": 4},
        timeout=120,
    )
    r.raise_for_status()
    if "image/" in r.headers.get("content-type", ""):
        Path(out_path).write_bytes(r.content)
        return
    data = r.json()
    result = data.get("result", {})
    if isinstance(result, dict) and result.get("image"):
        Path(out_path).write_bytes(base64.b64decode(result["image"]))
        return
    raise RuntimeError("Cloudflare لم يرجع صورة.")

def file_data_uri(path):
    mime = "image/png" if str(path).lower().endswith(".png") else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(Path(path).read_bytes()).decode()

def fal_motion(image_path, prompt, out_path):
    os.environ["FAL_KEY"] = FAL_KEY
    result = fal_client.subscribe(
        "fal-ai/minimax/hailuo-2.3/standard/image-to-video",
        arguments={"prompt": prompt, "image_url": file_data_uri(image_path)},
        with_logs=False,
    )
    video_url = result["video"]["url"]
    r = requests.get(video_url, timeout=300)
    r.raise_for_status()
    Path(out_path).write_bytes(r.content)

async def make_scene(index, scene, td):
    img = td / f"scene{index}.png"
    raw = td / f"motion{index}.mp4"

    await asyncio.to_thread(cloudflare_image, scene["image_prompt"], img)
    await asyncio.to_thread(fal_motion, img, scene["motion_prompt"], raw)
    return raw

async def tts(text, role, out_path):
    voice, pitch, rate = VOICE_MAP.get(role, VOICE_MAP["راوي"])
    await edge_tts.Communicate(text, voice, pitch=pitch, rate=rate).save(str(out_path))

def ff():
    return imageio_ffmpeg.get_ffmpeg_exe()

def normalize_video(inp, seconds, aspect, out):
    w, h = (720,1280) if aspect=="9:16" else ((1280,720) if aspect=="16:9" else (1080,1080))
    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=25,format=yuv420p"
    subprocess.run(
        [ff(),"-y","-i",str(inp),"-t",str(seconds),"-vf",vf,"-an",str(out)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

def concat_videos(clips, out_path):
    listing = Path(out_path).with_suffix(".txt")
    listing.write_text("\n".join(f"file '{Path(c).as_posix()}'" for c in clips), encoding="utf-8")
    subprocess.run(
        [ff(),"-y","-f","concat","-safe","0","-i",str(listing),"-c","copy",str(out_path)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

def mux_audio(video, audio, out):
    subprocess.run(
        [ff(),"-y","-i",str(video),"-i",str(audio),"-c:v","copy","-c:a","aac","-shortest","-movflags","+faststart",str(out)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    status = ("✅ Cloudflare" if cf_enabled() else "❌ Cloudflare") + " | " + ("✅ fal حركة" if fal_enabled() else "❌ fal")
    await update.message.reply_text(
        "⚡ Najm Video AI Cartoon Motion v3.1 FAST\n"
        + status +
        "\n\nالوضع السريع مفعّل.\n"
        "15 ثانية = مشهدان متحركان فقط لتقليل الانتظار والتكلفة.\n\n"
        "أرسل القصة مباشرة."
    )

async def cancel(update, context):
    context.user_data.clear()
    await update.message.reply_text("تم الإلغاء.")

async def text_handler(update, context):
    if context.user_data.get("stage"):
        return await update.message.reply_text("أكمل الخيارات بالأزرار أو /cancel.")
    context.user_data["idea"] = update.message.text.strip()
    context.user_data["stage"] = "style"
    await update.message.reply_text(
        "🎨 اختر شكل الشخصيات:",
        reply_markup=buttons(["كرتون 3D","كرتون أطفال","أنمي","رسوم 2D"], "style")
    )

async def callback(update, context):
    q = update.callback_query
    await q.answer()
    key, val = q.data.split(":",1)

    if key == "style":
        context.user_data["style"] = val
        context.user_data["stage"] = "duration"
        await q.edit_message_text("⏱ اختر المدة:", reply_markup=buttons(["15","30"], "duration"))

    elif key == "duration":
        context.user_data["duration"] = int(val)
        context.user_data["stage"] = "aspect"
        await q.edit_message_text("📐 اختر المقاس:", reply_markup=buttons(["9:16","16:9","1:1"], "aspect"))

    elif key == "aspect":
        context.user_data["aspect"] = val
        context.user_data["stage"] = "ready"
        scenes, cast = storyboard(context.user_data["idea"], context.user_data["duration"], context.user_data["style"])
        await q.edit_message_text(
            f"⚡ الوضع السريع: {len(scenes)} مشاهد متحركة\n"
            f"الشخصيات: {'، '.join(cast)}\n\n"
            "سيتم إنشاء المشاهد بالتوازي لتقليل وقت الانتظار.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 إنشاء سريع", callback_data="render:go")]])
        )

    elif key == "render":
        if not (cf_enabled() and fal_enabled()):
            await q.edit_message_text("❌ تأكد من مفاتيح Cloudflare و FAL_KEY في Railway.")
            context.user_data.clear()
            return

        idea = context.user_data["idea"]
        style = context.user_data["style"]
        duration = context.user_data["duration"]
        aspect = context.user_data["aspect"]

        scenes, cast = storyboard(idea, duration, style)
        started = time.time()
        await q.edit_message_text(f"⚡ بدأ الإنشاء السريع: {len(scenes)} مشاهد بالتوازي…")

        with tempfile.TemporaryDirectory() as td_str:
            td = Path(td_str)

            async def scene_job(i, scene):
                await context.bot.send_message(q.message.chat_id, f"🎨🎞 تجهيز المشهد {i}/{len(scenes)}…")
                return await make_scene(i, scene, td)

            # Parallel scene generation: major speed improvement.
            raws = await asyncio.gather(
                *[scene_job(i, s) for i, s in enumerate(scenes, 1)]
            )

            clips = []
            for i, (raw, scene) in enumerate(zip(raws, scenes), 1):
                clip = td / f"clip{i}.mp4"
                await asyncio.to_thread(normalize_video, raw, scene["seconds"], aspect, clip)
                clips.append(clip)

            silent = td / "silent.mp4"
            await asyncio.to_thread(concat_videos, clips, silent)

            await context.bot.send_message(q.message.chat_id, "🎙 تجهيز الصوت…")
            voice_parts = []
            for i, scene in enumerate(scenes):
                role = "طفل" if ("طفل" in cast and i == 1) else "راوي"
                vp = td / f"voice{i}.mp3"
                await tts(scene["narration"], role, vp)
                voice_parts.append(vp)

            voice_list = td / "voices.txt"
            voice_list.write_text("\n".join(f"file '{p.as_posix()}'" for p in voice_parts), encoding="utf-8")
            voice_file = td / "voice.mp3"
            subprocess.run(
                [ff(),"-y","-f","concat","-safe","0","-i",str(voice_list),"-c","copy",str(voice_file)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            final = td / "final.mp4"
            await asyncio.to_thread(mux_audio, silent, voice_file, final)
            elapsed = int(time.time() - started)

            with final.open("rb") as f:
                await context.bot.send_video(
                    q.message.chat_id,
                    video=f,
                    caption=f"✅ تم — الوضع السريع ⚡\n⏱ وقت الإنشاء: {elapsed//60}:{elapsed%60:02d}"
                )

        context.user_data.clear()

def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN غير موجود.")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
