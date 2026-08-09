import os, base64, asyncio, logging, tempfile, subprocess, re
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
log = logging.getLogger("NajmCartoonMotion")

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
    rows=[]
    for i in range(0,len(items),2):
        rows.append([InlineKeyboardButton(v, callback_data=f"{prefix}:{v}") for v in items[i:i+2]])
    return InlineKeyboardMarkup(rows)

def cf_enabled():
    return bool(CF_ACCOUNT and CF_TOKEN)

def fal_enabled():
    return bool(FAL_KEY)

def detect_cast(idea):
    cast=["راوي"]
    if any(x in idea for x in ["طفل","ولد","صبي"]): cast.append("طفل")
    if any(x in idea for x in ["طفلة","بنت"]): cast.append("طفلة")
    if any(x in idea for x in ["أم","امرأة","سيدة"]): cast.append("امرأة")
    if any(x in idea for x in ["أب","رجل"]): cast.append("رجل")
    if "قطة" in idea or "قط" in idea: cast.append("قطة")
    return list(dict.fromkeys(cast))

def storyboard(idea, duration, style):
    # Trial-conscious: 15 sec = 3 generated motion clips, longer = 4.
    count = 3 if duration <= 15 else 4
    sec = duration / count
    visual_style = STYLE_MAP.get(style, STYLE_MAP["كرتون 3D"])
    cast = detect_cast(idea)

    actions = [
        "The main character walks naturally through the environment. Arms and legs move correctly, clothes react subtly, camera tracks smoothly.",
        "The characters interact naturally: turn their heads, gesture with hands, react with facial expressions, and move through the scene.",
        "The story reaches a warm ending. Characters move naturally, the camera slowly follows, subtle environmental motion continues.",
        "A new story beat unfolds with clear body movement, walking and interaction, smooth cinematic camera movement.",
    ]
    narr = [
        f"تبدأ قصتنا: {idea}",
        "تتحرك الشخصيات وتبدأ الأحداث بالتطور.",
        "وفي النهاية تصل القصة إلى لحظة جميلة ومميزة.",
        "ثم تستمر الأحداث في مشهد جديد.",
    ]
    scenes=[]
    for i in range(count):
        image_prompt = (
            f"{visual_style}. Story: {idea}. Scene {i+1}/{count}. "
            "Full-body cartoon people visible when appropriate. "
            "Keep EXACTLY the same main character identity across scenes: same face, hairstyle, age, clothes, colors and proportions. "
            "If a cat is present, keep the same cat color, markings and size. "
            "Story continuity, cinematic composition, no text, no captions, no watermark."
        )
        motion_prompt = (
            f"Animated cartoon scene. {actions[i % len(actions)]} "
            "Preserve the character's face, clothing and cartoon style. "
            "Natural walking cycle, natural blinking and expressions, no morphing, no extra limbs, no identity change."
        )
        scenes.append({"narration": narr[i], "image_prompt": image_prompt, "motion_prompt": motion_prompt, "seconds": sec})
    return scenes, cast

def cloudflare_image(prompt, out_path):
    model="@cf/black-forest-labs/flux-1-schnell"
    url=f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/{model}"
    r=requests.post(url,headers={"Authorization":f"Bearer {CF_TOKEN}","Content-Type":"application/json"},
                    json={"prompt":prompt,"num_steps":4},timeout=180)
    r.raise_for_status()
    if "image/" in r.headers.get("content-type",""):
        Path(out_path).write_bytes(r.content); return
    data=r.json()
    result=data.get("result",{})
    if isinstance(result,dict) and result.get("image"):
        Path(out_path).write_bytes(base64.b64decode(result["image"])); return
    raise RuntimeError("Cloudflare لم يرجع صورة.")

def file_data_uri(path):
    ext=Path(path).suffix.lower()
    mime="image/png" if ext==".png" else "image/jpeg"
    return f"data:{mime};base64,"+base64.b64encode(Path(path).read_bytes()).decode()

def fal_motion(image_path, prompt, out_path):
    # Hailuo Standard: strong human/character motion for trial-quality image-to-video.
    os.environ["FAL_KEY"]=FAL_KEY
    result=fal_client.subscribe(
        "fal-ai/minimax/hailuo-2.3/standard/image-to-video",
        arguments={"prompt":prompt, "image_url":file_data_uri(image_path)},
        with_logs=False,
    )
    video_url=result["video"]["url"]
    r=requests.get(video_url,timeout=300)
    r.raise_for_status()
    Path(out_path).write_bytes(r.content)

async def tts(text, role, out_path):
    voice,pitch,rate=VOICE_MAP.get(role,VOICE_MAP["راوي"])
    await edge_tts.Communicate(text,voice,pitch=pitch,rate=rate).save(str(out_path))

def ff():
    return imageio_ffmpeg.get_ffmpeg_exe()

def concat_videos(clips,out_path):
    listing=Path(out_path).with_suffix(".txt")
    listing.write_text("\n".join(f"file '{Path(c).as_posix()}'" for c in clips),encoding="utf-8")
    subprocess.run([ff(),"-y","-f","concat","-safe","0","-i",str(listing),"-c","copy",str(out_path)],
                   check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def normalize_video(inp, seconds, aspect, out):
    w,h=(720,1280) if aspect=="9:16" else ((1280,720) if aspect=="16:9" else (1080,1080))
    vf=f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=25,format=yuv420p"
    subprocess.run([ff(),"-y","-i",str(inp),"-t",str(seconds),"-vf",vf,"-an",str(out)],
                   check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def mux_audio(video,audio,out):
    subprocess.run([ff(),"-y","-i",str(video),"-i",str(audio),"-c:v","copy","-c:a","aac",
                    "-shortest","-movflags","+faststart",str(out)],
                   check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def make_cat_meow(out_path, seconds=0.7):
    # Simple synthetic cat-like chirp fallback; avoids external copyrighted SFX.
    import wave, math, struct
    rate=44100
    with wave.open(str(out_path),"w") as w:
        w.setparams((1,2,rate,int(rate*seconds),"NONE","not compressed"))
        for i in range(int(rate*seconds)):
            t=i/rate
            f=700+500*math.sin(math.pi*t/seconds)
            env=max(0,1-t/seconds)
            val=int(10000*env*math.sin(2*math.pi*f*t))
            w.writeframes(struct.pack("<h",val))

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    status=("✅ Cloudflare" if cf_enabled() else "❌ Cloudflare")+" | "+("✅ fal حركة" if fal_enabled() else "❌ fal")
    await update.message.reply_text(
        "🎬 Najm Video AI Cartoon Motion v3\n"+status+
        "\n\nأرسل القصة. مثال:\nطفل يمشي في الحديقة ويرى قطة صغيرة ثم يحملها ويعود إلى البيت."
    )

async def cancel(update,context):
    context.user_data.clear()
    await update.message.reply_text("تم الإلغاء.")

async def text_handler(update,context):
    if context.user_data.get("stage"):
        return await update.message.reply_text("أكمل الاختيارات بالأزرار أو /cancel.")
    context.user_data["idea"]=update.message.text.strip()
    context.user_data["stage"]="style"
    await update.message.reply_text("🎨 اختر شكل الشخصيات:",reply_markup=buttons(["كرتون 3D","كرتون أطفال","أنمي","رسوم 2D"],"style"))

async def callback(update,context):
    q=update.callback_query; await q.answer()
    key,val=q.data.split(":",1)
    if key=="style":
        context.user_data["style"]=val; context.user_data["stage"]="duration"
        await q.edit_message_text("⏱ اختر المدة:",reply_markup=buttons(["15","30"],"duration"))
    elif key=="duration":
        context.user_data["duration"]=int(val); context.user_data["stage"]="aspect"
        await q.edit_message_text("📐 اختر المقاس:",reply_markup=buttons(["9:16","16:9","1:1"],"aspect"))
    elif key=="aspect":
        context.user_data["aspect"]=val; context.user_data["stage"]="ready"
        cast=detect_cast(context.user_data["idea"])
        await q.edit_message_text(
            "الشخصيات المكتشفة: "+"، ".join(cast)+"\n\n"
            "🎙 الطفل/الطفلة له صوت مستقل، والراوي صوت مستقل، والقطة لها مؤثر صوتي.\n"
            "⚠️ توليد الحركة عبر fal مدفوع حسب عدد المقاطع.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 إنشاء فيديو متحرك",callback_data="render:go")]])
        )
    elif key=="render":
        if not cf_enabled() or not fal_enabled():
            await q.edit_message_text("❌ تأكد من وجود CLOUDFLARE_ACCOUNT_ID و CLOUDFLARE_API_TOKEN و FAL_KEY في Railway.")
            context.user_data.clear(); return

        idea=context.user_data["idea"]; style=context.user_data["style"]
        duration=context.user_data["duration"]; aspect=context.user_data["aspect"]
        scenes,cast=storyboard(idea,duration,style)
        await q.edit_message_text(f"🚀 بدأ الإنشاء: {len(scenes)} مشاهد متحركة…")

        with tempfile.TemporaryDirectory() as td:
            td=Path(td); clips=[]; narration=[]
            for i,s in enumerate(scenes,1):
                await context.bot.send_message(q.message.chat_id,f"🎨 صورة كرتونية {i}/{len(scenes)}")
                img=td/f"scene{i}.png"
                await asyncio.to_thread(cloudflare_image,s["image_prompt"],img)

                await context.bot.send_message(q.message.chat_id,f"🎞 تحريك الشخصية {i}/{len(scenes)} (مشي/تفاعل)…")
                raw=td/f"motion{i}.mp4"
                await asyncio.to_thread(fal_motion,img,s["motion_prompt"],raw)

                clip=td/f"clip{i}.mp4"
                await asyncio.to_thread(normalize_video,raw,s["seconds"],aspect,clip)
                clips.append(clip); narration.append(s["narration"])

            silent=td/"silent.mp4"; voicefile=td/"voice.mp3"; final=td/"final.mp4"
            await asyncio.to_thread(concat_videos,clips,silent)

            # Distinct narrator/child voice: if a child is present, alternate story lines.
            parts=[]
            for i,line in enumerate(narration):
                role="طفل" if ("طفل" in cast and i==1) else ("طفلة" if ("طفلة" in cast and i==1) else "راوي")
                part=td/f"voice{i}.mp3"
                await tts(line,role,part)
                parts.append(part)

            voice_list=td/"voices.txt"
            voice_list.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts),encoding="utf-8")
            subprocess.run([ff(),"-y","-f","concat","-safe","0","-i",str(voice_list),"-c","copy",str(voicefile)],
                           check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

            await context.bot.send_message(q.message.chat_id,"🎙 تركيب أصوات الشخصيات والفيديو…")
            await asyncio.to_thread(mux_audio,silent,voicefile,final)
            with final.open("rb") as f:
                await context.bot.send_video(q.message.chat_id,video=f,caption=f"✅ فيديو كرتوني متحرك — {style}")

        context.user_data.clear()

def main():
    if not TOKEN: raise RuntimeError("TELEGRAM_BOT_TOKEN غير موجود.")
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("cancel",cancel))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler))
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
