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

FAL_MODEL = "fal-ai/minimax/hailuo-2.3-fast/standard/image-to-video"
SCENE_TIMEOUT_SECONDS = 480
SCENE_RETRIES = 1

logging.basicConfig(level=logging.INFO)
ACTIVE_JOBS = {}

CARTOON_STYLE = (
    "2D animated family cartoon, hand-drawn children's storybook style, "
    "clean bold outlines, colorful cel shading, friendly expressive faces, "
    "clearly illustrated people, NOT photorealistic, NOT live action, NOT realistic photography. "
    "Keep exactly the same character identity, face, hair, clothing colors and age across scenes. "
)

STYLE_MAP = {
    "كرتون 2D": CARTOON_STYLE,
    "كرتون أطفال": (
        "friendly children's 2D cartoon illustration, cute stylized human characters, "
        "bright colors, clean outlines, storybook animation, NOT photorealistic. "
    ),
    "أنمي": (
        "family-friendly anime cartoon illustration, clean line art, expressive faces, "
        "colorful animation frame, NOT photorealistic. "
    ),
}

VOICE_MAP = {
    "راوي": ("ar-SA-HamedNeural", "-8Hz", "-5%"),
    "طفل": ("ar-SA-ZariyahNeural", "+28Hz", "+8%"),
    "طفلة": ("ar-SA-ZariyahNeural", "+35Hz", "+10%"),
}

def buttons(items, prefix):
    rows=[]
    for i in range(0,len(items),2):
        rows.append([InlineKeyboardButton(v, callback_data=f"{prefix}:{v}") for v in items[i:i+2]])
    return InlineKeyboardMarkup(rows)

def services_ok():
    return bool(TOKEN and CF_ACCOUNT and CF_TOKEN and FAL_KEY)

def detect_cast(idea):
    cast=["راوي"]
    if any(x in idea for x in ["طفل","ولد","صبي","يحيى"]): cast.append("طفل")
    if any(x in idea for x in ["طفلة","بنت","ميار"]): cast.append("طفلة")
    if "قطة" in idea or "قط" in idea: cast.append("قطة")
    return list(dict.fromkeys(cast))

def storyboard(idea, duration, style):
    count = 2 if duration <= 15 else 3
    sec = duration / count
    visual_style = STYLE_MAP.get(style, CARTOON_STYLE)
    actions = [
        "The child walks naturally through the home or garden, full body visible, correct walking cycle, natural arm swing, blinking, friendly expression, smooth camera tracking.",
        "The cartoon characters interact naturally, turn their heads, gesture with hands, walk and react. Stable faces and clothes, no morphing.",
        "Warm ending with the same cartoon characters walking or interacting together, smooth simple motion and stable identity."
    ]
    scenes=[]
    for i in range(count):
        scenes.append({
            "image_prompt": visual_style + f" Story: {idea}. Scene {i+1}/{count}. "
                "Use the SAME child design in every scene: same face, hairstyle, skin tone, clothes and proportions. "
                "No text, no captions, no watermark.",
            "motion_prompt": "Animated 2D cartoon video. " + actions[i % len(actions)] +
                " Preserve the illustrated cartoon style and exact character identity. "
                "No realistic humans, no extra limbs, no face replacement.",
            "narration": f"كان يا ما كان. {idea}" if i == 0 else "وتستمر الأحداث حتى تصل القصة إلى نهاية جميلة.",
            "seconds": sec
        })
    return scenes, detect_cast(idea)

def cloudflare_image(prompt, out_path):
    model="@cf/black-forest-labs/flux-1-schnell"
    url=f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/{model}"
    r=requests.post(url, headers={"Authorization":f"Bearer {CF_TOKEN}","Content-Type":"application/json"},
                    json={"prompt":prompt,"num_steps":4}, timeout=120)
    r.raise_for_status()
    if "image/" in r.headers.get("content-type",""):
        Path(out_path).write_bytes(r.content); return
    data=r.json(); result=data.get("result",{})
    if isinstance(result,dict) and result.get("image"):
        Path(out_path).write_bytes(base64.b64decode(result["image"])); return
    raise RuntimeError("Cloudflare لم يرجع صورة للمشهد.")

def file_data_uri(path):
    return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode()

async def fal_motion_async(image_path, prompt, out_path, progress_state, scene_no):
    os.environ["FAL_KEY"]=FAL_KEY
    last_error=None
    for attempt in range(SCENE_RETRIES+1):
        try:
            progress_state["stage"]=f"تحريك المشهد {scene_no} عبر fal" + (f" — إعادة محاولة {attempt}" if attempt else "")
            result=await fal_client.subscribe_async(
                FAL_MODEL,
                arguments={"prompt":prompt,"image_url":file_data_uri(image_path)},
                with_logs=False,
                start_timeout=180,
                client_timeout=SCENE_TIMEOUT_SECONDS,
            )
            video_url=result["video"]["url"]
            r=await asyncio.to_thread(requests.get, video_url, timeout=180)
            r.raise_for_status()
            Path(out_path).write_bytes(r.content)
            return
        except asyncio.CancelledError:
            raise
        except Exception as e:
            last_error=e
            if attempt < SCENE_RETRIES:
                await asyncio.sleep(3)
    raise RuntimeError(f"فشل تحريك المشهد {scene_no}: {last_error}")

async def tts(text, role, out_path):
    voice,pitch,rate=VOICE_MAP.get(role,VOICE_MAP["راوي"])
    await edge_tts.Communicate(text,voice,pitch=pitch,rate=rate).save(str(out_path))

def ff():
    return imageio_ffmpeg.get_ffmpeg_exe()

def normalize_video(inp, seconds, aspect, out):
    w,h=(720,1280) if aspect=="9:16" else ((1280,720) if aspect=="16:9" else (1080,1080))
    vf=f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=25,format=yuv420p"
    subprocess.run([ff(),"-y","-i",str(inp),"-t",str(seconds),"-vf",vf,"-an",str(out)],
                   check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def concat_videos(clips,out_path):
    listing=Path(out_path).with_suffix(".txt")
    listing.write_text("\n".join(f"file '{Path(c).as_posix()}'" for c in clips),encoding="utf-8")
    subprocess.run([ff(),"-y","-f","concat","-safe","0","-i",str(listing),"-c","copy",str(out_path)],
                   check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def mux_audio(video,audio,out):
    subprocess.run([ff(),"-y","-i",str(video),"-i",str(audio),"-c:v","copy","-c:a","aac","-shortest","-movflags","+faststart",str(out)],
                   check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def fmt_time(seconds):
    seconds=max(0,int(seconds))
    return f"{seconds//60:02d}:{seconds%60:02d}"

async def progress_clock(message,state,started,stop_event):
    while not stop_event.is_set():
        txt=("🎬 Najm Video AI v3.4\n"
             f"⏱ الوقت: {fmt_time(time.time()-started)}\n"
             f"📊 التقدم التقريبي: {state['pct']}%\n"
             f"⚙️ {state['stage']}\n"
             f"🎞 المشاهد المكتملة: {state['done']}/{state['total']}\n\n"
             "يمكنك الإلغاء في أي وقت بـ /cancel")
        try: await message.edit_text(txt)
        except Exception: pass
        try: await asyncio.wait_for(stop_event.wait(), timeout=10)
        except asyncio.TimeoutError: pass

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🎬 Najm Video AI v3.4 ROBUST FAST\n"
        + ("✅ الخدمات جاهزة" if services_ok() else "❌ يوجد مفتاح ناقص")
        + "\n\nالنسخة الجديدة تمنع التعليق الطويل وتدعم /cancel الحقيقي.\nأرسل القصة مباشرة."
    )

async def cancel(update:Update,context:ContextTypes.DEFAULT_TYPE):
    chat_id=update.effective_chat.id
    task=ACTIVE_JOBS.get(chat_id)
    if task and not task.done():
        task.cancel()
        await update.message.reply_text("🛑 تم طلب إلغاء الفيديو الجاري.")
    else:
        context.user_data.clear()
        await update.message.reply_text("لا يوجد فيديو جارٍ الآن.")

async def text_handler(update:Update,context:ContextTypes.DEFAULT_TYPE):
    chat_id=update.effective_chat.id
    job=ACTIVE_JOBS.get(chat_id)
    if job and not job.done():
        return await update.message.reply_text("يوجد فيديو قيد الإنشاء. استخدم /cancel لإلغائه أولًا.")
    if context.user_data.get("stage"):
        return await update.message.reply_text("أكمل الاختيارات بالأزرار أو /cancel.")
    context.user_data["idea"]=update.message.text.strip()
    context.user_data["stage"]="style"
    await update.message.reply_text("🎨 اختر النمط:",reply_markup=buttons(["كرتون 2D","كرتون أطفال","أنمي"],"style"))

async def render_job(chat_id, bot, params):
    idea,style,duration,aspect=params
    scenes,cast=storyboard(idea,duration,style)
    started=time.time()
    state={"pct":3,"stage":"بدء المشروع","done":0,"total":len(scenes)}
    progress_message=await bot.send_message(chat_id,"🎬 بدء إنشاء الفيديو...")
    stop_event=asyncio.Event()
    clock=asyncio.create_task(progress_clock(progress_message,state,started,stop_event))
    try:
        with tempfile.TemporaryDirectory() as td_str:
            td=Path(td_str)
            async def scene_job(i,scene):
                state["stage"]=f"إنشاء الصورة الكرتونية للمشهد {i}"
                img=td/f"scene{i}.png"
                await asyncio.wait_for(asyncio.to_thread(cloudflare_image,scene["image_prompt"],img),timeout=150)
                state["pct"]=10+int(20*i/len(scenes))
                raw=td/f"motion{i}.mp4"
                await fal_motion_async(img,scene["motion_prompt"],raw,state,i)
                clip=td/f"clip{i}.mp4"
                await asyncio.to_thread(normalize_video,raw,scene["seconds"],aspect,clip)
                state["done"]+=1
                state["pct"]=30+int(50*state["done"]/len(scenes))
                return clip

            results=await asyncio.gather(*[scene_job(i,s) for i,s in enumerate(scenes,1)],return_exceptions=True)
            clips=[]; errors=[]
            for r in results:
                if isinstance(r,Exception): errors.append(str(r))
                else: clips.append(r)

            if not clips:
                raise RuntimeError("فشلت كل المشاهد. " + " | ".join(errors[:2]))
            if errors:
                await bot.send_message(chat_id,"⚠️ بعض المشاهد فشلت، سأكمل بالمشاهد الناجحة.")

            state["pct"]=84; state["stage"]="دمج المشاهد"
            silent=td/"silent.mp4"
            await asyncio.to_thread(concat_videos,clips,silent)

            state["pct"]=89; state["stage"]="تجهيز الصوت"
            role="طفل" if "طفل" in cast else "راوي"
            voice_file=td/"voice.mp3"
            narration=" ".join(s["narration"] for s in scenes)
            await asyncio.wait_for(tts(narration,role,voice_file),timeout=120)

            state["pct"]=95; state["stage"]="تركيب الفيديو النهائي"
            final=td/"final.mp4"
            await asyncio.to_thread(mux_audio,silent,voice_file,final)

            state["pct"]=100; state["stage"]="اكتمل"
            stop_event.set()
            try: await clock
            except Exception: pass
            try:
                await progress_message.edit_text(f"✅ اكتمل الفيديو\n⏱ الوقت الإجمالي: {fmt_time(time.time()-started)}\n📊 100%")
            except Exception: pass
            with final.open("rb") as f:
                await bot.send_video(chat_id,video=f,caption="✅ تم إنشاء الفيديو الكرتوني")
    except asyncio.CancelledError:
        stop_event.set()
        try: await clock
        except Exception: pass
        try: await progress_message.edit_text("🛑 تم إلغاء عملية إنشاء الفيديو.")
        except Exception: pass
        raise
    except Exception as e:
        stop_event.set()
        try: await clock
        except Exception: pass
        try: await progress_message.edit_text(f"❌ توقف الإنشاء:\n{e}")
        except Exception: await bot.send_message(chat_id,f"❌ توقف الإنشاء:\n{e}")
    finally:
        ACTIVE_JOBS.pop(chat_id,None)

async def callback(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    key,val=q.data.split(":",1)
    if key=="style":
        context.user_data["style"]=val; context.user_data["stage"]="duration"
        await q.edit_message_text("⏱ اختر المدة:",reply_markup=buttons(["15","30"],"duration"))
    elif key=="duration":
        context.user_data["duration"]=int(val); context.user_data["stage"]="aspect"
        await q.edit_message_text("📐 اختر المقاس:",reply_markup=buttons(["9:16","16:9","1:1"],"aspect"))
    elif key=="aspect":
        context.user_data["aspect"]=val; context.user_data["stage"]="ready"
        scenes,cast=storyboard(context.user_data["idea"],context.user_data["duration"],context.user_data["style"])
        await q.edit_message_text(
            f"جاهز ✅\nالمشاهد: {len(scenes)}\nالشخصيات: {'، '.join(cast)}\n\n"
            "هذه النسخة تلغي أي مشهد يتجاوز المهلة بدل أن تعلق ساعات.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 إنشاء",callback_data="render:go")]])
        )
    elif key=="render":
        chat_id=q.message.chat_id
        existing=ACTIVE_JOBS.get(chat_id)
        if existing and not existing.done():
            return await q.edit_message_text("يوجد فيديو قيد الإنشاء. استخدم /cancel أولًا.")
        params=(context.user_data["idea"],context.user_data["style"],context.user_data["duration"],context.user_data["aspect"])
        context.user_data.clear()
        await q.edit_message_text("✅ تم إرسال الطلب للمحرك. سيظهر العداد الآن.")
        task=asyncio.create_task(render_job(chat_id,context.bot,params))
        ACTIVE_JOBS[chat_id]=task

def main():
    if not TOKEN: raise RuntimeError("TELEGRAM_BOT_TOKEN غير موجود.")
    app=Application.builder().token(TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("cancel",cancel))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler))
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
