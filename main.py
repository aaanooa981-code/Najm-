import os, base64, asyncio, tempfile, subprocess, time
from pathlib import Path
import requests, edge_tts, imageio_ffmpeg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN=os.getenv("TELEGRAM_BOT_TOKEN","").strip()
CF_ACCOUNT=os.getenv("CLOUDFLARE_ACCOUNT_ID","").strip()
CF_TOKEN=os.getenv("CLOUDFLARE_API_TOKEN","").strip()
ACTIVE_JOBS={}

SEEDANCE_MODEL="bytedance/seedance-2.0-mini"
RESOLUTION="480p"
DURATION=5

YAHYA_IMAGE_PROMPT = (
    "High quality stylized 3D animated family-film character, not 2D cartoon, not photorealistic. "
    "Yahya is a six-year-old Arab boy with warm friendly facial features, short black hair, "
    "brown eyes, child proportions, wearing a clean white thobe. Full body visible. "
    "Modern warm Arab family home interior, hallway leading toward stairs, soft daylight. "
    "Consistent character design suitable for a recurring children's series. No text, no watermark."
)

YAHYA_MOTION_PROMPT = (
    "Yahya, the same six-year-old 3D Arab boy in the reference image, walks naturally forward "
    "through the hallway toward the stairs. His legs and arms move with a believable child walking cycle. "
    "He turns his head toward his mother off camera, smiles, lightly raises one hand and responds naturally. "
    "Preserve exactly the same face, hair, white thobe, age and body proportions. "
    "Smooth 3D family animation, stable face, no morphing, no extra fingers or limbs, natural body motion. "
    "Camera gently follows him. No subtitles, no text."
)

ARABIC_LINE="حاضر يا أمي."

def ff():
    return imageio_ffmpeg.get_ffmpeg_exe()

def fmt(t):
    t=int(t)
    return f"{t//60:02d}:{t%60:02d}"

def cf_image(prompt,path):
    url=f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    r=requests.post(
        url,
        headers={"Authorization":f"Bearer {CF_TOKEN}","Content-Type":"application/json"},
        json={"prompt":prompt,"num_steps":4},
        timeout=150
    )
    r.raise_for_status()
    if "image/" in r.headers.get("content-type",""):
        Path(path).write_bytes(r.content)
        return
    data=r.json().get("result",{})
    if isinstance(data,dict) and data.get("image"):
        Path(path).write_bytes(base64.b64decode(data["image"]))
        return
    raise RuntimeError("Cloudflare لم يرجع صورة يحيى.")

def image_data_uri(path):
    return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode("ascii")

def seedance_video(image_path,out_path):
    url=f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run"
    payload={
        "model": SEEDANCE_MODEL,
        "input": {
            "image": image_data_uri(image_path),
            "prompt": YAHYA_MOTION_PROMPT,
            "duration": DURATION,
            "resolution": RESOLUTION,
            "aspect_ratio": "9:16",
            "fps": 24,
            "camera_fixed": False,
            "generate_audio": False,
            "watermark": False,
            "use_virtual_avatar": True
        }
    }
    r=requests.post(
        url,
        headers={"Authorization":f"Bearer {CF_TOKEN}","Content-Type":"application/json"},
        json=payload,
        timeout=600
    )
    r.raise_for_status()
    data=r.json()

    # Current Cloudflare third-party AI response format.
    if data.get("state") == "Completed":
        video_url=(data.get("result") or {}).get("video")
    else:
        result=data.get("result") or {}
        video_url=result.get("video") if isinstance(result,dict) else None

    if not video_url:
        detail=data.get("errors") or data.get("messages") or data
        raise RuntimeError(f"Seedance لم يرجع فيديو مكتمل: {detail}")

    vr=requests.get(video_url,timeout=240)
    vr.raise_for_status()
    Path(out_path).write_bytes(vr.content)

async def tts_yahya(out_path):
    # Temporary Arabic child-like voice for the motion test.
    # The downloaded ElevenLabs preview is only a preview and cannot synthesize new dialogue.
    await edge_tts.Communicate(
        ARABIC_LINE,
        "ar-SA-ZariyahNeural",
        pitch="+28Hz",
        rate="+8%"
    ).save(str(out_path))

def mux(video,audio,out):
    subprocess.run(
        [ff(),"-y","-i",str(video),"-i",str(audio),
         "-c:v","copy","-c:a","aac","-shortest","-movflags","+faststart",str(out)],
        check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL
    )

async def progress(msg,state,start,stop):
    while not stop.is_set():
        try:
            await msg.edit_text(
                "🎬 Najm Video AI v4.0 — Seedance Test\n"
                f"⏱ {fmt(time.time()-start)}\n"
                f"📊 {state['pct']}%\n"
                f"⚙️ {state['stage']}\n\n"
                "اختبار واحد فقط: 5 ثوانٍ • 480p"
            )
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop.wait(),10)
        except asyncio.TimeoutError:
            pass

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    ready=bool(TOKEN and CF_ACCOUNT and CF_TOKEN)
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 جرّب يحيى 5 ثوانٍ",callback_data="test:yahya")]])
    await update.message.reply_text(
        "🎬 Najm Video AI v4.0\n"
        + ("✅ Cloudflare جاهز\n" if ready else "❌ يوجد مفتاح Cloudflare ناقص\n")
        + "\nاختبار تحريك حقيقي ليحيى 3D عبر Seedance 2.0 Mini.\n"
          "الدقة: 480p\nالمدة: 5 ثوانٍ\n\n"
          "لن ننشئ قصة كاملة قبل نجاح هذا الاختبار.",
        reply_markup=kb
    )

async def cancel(update:Update,context:ContextTypes.DEFAULT_TYPE):
    task=ACTIVE_JOBS.get(update.effective_chat.id)
    if task and not task.done():
        task.cancel()
        await update.message.reply_text("🛑 تم طلب إلغاء الاختبار.")
    else:
        await update.message.reply_text("لا يوجد اختبار جارٍ.")

async def run_test(chat_id,bot):
    startt=time.time()
    state={"pct":5,"stage":"تجهيز يحيى 3D"}
    msg=await bot.send_message(chat_id,"🎬 بدأ اختبار يحيى...")
    stop=asyncio.Event()
    ticker=asyncio.create_task(progress(msg,state,startt,stop))
    try:
        with tempfile.TemporaryDirectory() as td_s:
            td=Path(td_s)
            img=td/"yahya.png"
            raw=td/"yahya_seedance.mp4"
            voice=td/"yahya_voice.mp3"
            final=td/"yahya_test_final.mp4"

            state["pct"]=15
            state["stage"]="إنشاء صورة يحيى 3D"
            await asyncio.wait_for(asyncio.to_thread(cf_image,YAHYA_IMAGE_PROMPT,img),timeout=180)

            state["pct"]=35
            state["stage"]="Seedance يحرك يحيى فعليًا"
            await asyncio.wait_for(asyncio.to_thread(seedance_video,img,raw),timeout=660)

            state["pct"]=85
            state["stage"]="إضافة الجملة العربية"
            await asyncio.wait_for(tts_yahya(voice),timeout=120)

            state["pct"]=95
            state["stage"]="تركيب الفيديو"
            await asyncio.to_thread(mux,raw,voice,final)

            state["pct"]=100
            state["stage"]="اكتمل"
            stop.set()
            try:
                await ticker
            except Exception:
                pass

            await msg.edit_text(
                f"✅ نجح اختبار يحيى\n⏱ {fmt(time.time()-startt)}\n"
                "🎞 5 ثوانٍ • 480p • تحريك Seedance"
            )
            with final.open("rb") as f:
                await bot.send_video(
                    chat_id,
                    video=f,
                    caption="✅ اختبار يحيى 3D — تحريك حقيقي\nالصوت الحالي مؤقت للاختبار."
                )
    except asyncio.CancelledError:
        stop.set()
        try: await ticker
        except Exception: pass
        try: await msg.edit_text("🛑 تم إلغاء الاختبار.")
        except Exception: pass
        raise
    except Exception as e:
        stop.set()
        try: await ticker
        except Exception: pass
        text=str(e)
        if "402" in text or "billing" in text.lower() or "balance" in text.lower():
            text="Cloudflare رفض تشغيل Seedance بسبب الفوترة/الرصيد. فعّل وسيلة الدفع ثم أعد الاختبار."
        try:
            await msg.edit_text(f"❌ فشل الاختبار:\n{text}")
        except Exception:
            await bot.send_message(chat_id,f"❌ فشل الاختبار:\n{text}")
    finally:
        ACTIVE_JOBS.pop(chat_id,None)

async def callback(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    if q.data=="test:yahya":
        chat=q.message.chat_id
        old=ACTIVE_JOBS.get(chat)
        if old and not old.done():
            return await q.edit_message_text("يوجد اختبار جارٍ. استخدم /cancel لإلغائه.")
        await q.edit_message_text("✅ تم إرسال اختبار يحيى إلى المحرك.")
        task=asyncio.create_task(run_test(chat,context.bot))
        ACTIVE_JOBS[chat]=task

async def text_handler(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "هذه نسخة اختبار الحركة أولًا. أرسل /start ثم اضغط «جرّب يحيى 5 ثوانٍ»."
    )

async def error_handler(update,context):
    try:
        if update and update.effective_chat:
            await context.bot.send_message(update.effective_chat.id,f"❌ خطأ داخل البوت:\n{context.error}")
    except Exception:
        pass

def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN غير موجود.")
    app=Application.builder().token(TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("cancel",cancel))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler))
    app.add_error_handler(error_handler)
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
