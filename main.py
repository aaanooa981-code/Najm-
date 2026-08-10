import os, base64, asyncio, tempfile, subprocess, time
from pathlib import Path
import requests, edge_tts, imageio_ffmpeg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN=os.getenv("TELEGRAM_BOT_TOKEN","").strip()
CF_ACCOUNT=os.getenv("CLOUDFLARE_ACCOUNT_ID","").strip()
CF_TOKEN=os.getenv("CLOUDFLARE_API_TOKEN","").strip()
ACTIVE_JOBS={}

STYLE={
"كرتون 2D":"2D children's cartoon, hand-drawn storybook style, clean bold outlines, colorful cel shading, NOT photorealistic, same characters and clothes across scenes.",
"كرتون أطفال":"cute children's cartoon, bright colors, clean outlines, friendly illustrated people, NOT photorealistic, same characters across scenes.",
"أنمي":"family-friendly anime cartoon, clean line art, expressive faces, NOT photorealistic, same characters across scenes."
}
VOICE={"راوي":("ar-SA-HamedNeural","-8Hz","-5%"),"طفل":("ar-SA-ZariyahNeural","+28Hz","+8%")}

def btn(items,p):
    return InlineKeyboardMarkup([[InlineKeyboardButton(v,callback_data=f"{p}:{v}") for v in items[i:i+2]] for i in range(0,len(items),2)])

def cast(idea):
    return ["راوي","طفل"] if any(x in idea for x in ["طفل","ولد","يحيى"]) else ["راوي"]

def scenes(idea,dur,style):
    n=3 if dur<=15 else 5
    sec=dur/n
    out=[]
    for i in range(n):
        out.append({
          "prompt":STYLE[style]+f" Story: {idea}. Scene {i+1}/{n}. Same face, hair, clothes and age. No text, no watermark.",
          "text":f"كان يا ما كان. {idea}" if i==0 else ("وتستمر الأحداث بحماس ومرح." if i<n-1 else "وفي النهاية انتهى اليوم بلحظة جميلة."),
          "sec":sec
        })
    return out

def cf_image(prompt,path):
    url=f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    r=requests.post(url,headers={"Authorization":f"Bearer {CF_TOKEN}","Content-Type":"application/json"},json={"prompt":prompt,"num_steps":4},timeout=120)
    r.raise_for_status()
    if "image/" in r.headers.get("content-type",""):
        Path(path).write_bytes(r.content); return
    data=r.json().get("result",{})
    if isinstance(data,dict) and data.get("image"):
        Path(path).write_bytes(base64.b64decode(data["image"])); return
    raise RuntimeError("Cloudflare لم يرجع صورة.")

def ff(): return imageio_ffmpeg.get_ffmpeg_exe()

def motion(img,sec,aspect,i,out):
    w,h=(720,1280) if aspect=="9:16" else ((1280,720) if aspect=="16:9" else (1080,1080))
    fps=25; frames=max(1,int(sec*fps))
    x="iw/2-(iw/zoom/2)+sin(on/18)*12"
    y="ih/2-(ih/zoom/2)+sin(on/22)*8"
    z="min(zoom+0.0012,1.12)" if i%2 else "if(lte(zoom,1.0),1.10,max(1.0,zoom-0.0008))"
    vf=f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,crop={w*2}:{h*2},zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps},format=yuv420p"
    subprocess.run([ff(),"-y","-loop","1","-i",str(img),"-vf",vf,"-t",str(sec),"-an",str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def concat(clips,out):
    txt=Path(out).with_suffix(".txt"); txt.write_text("\n".join(f"file '{Path(c).as_posix()}'" for c in clips),encoding="utf-8")
    subprocess.run([ff(),"-y","-f","concat","-safe","0","-i",str(txt),"-c","copy",str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

async def voice(text,role,out):
    v,p,r=VOICE.get(role,VOICE["راوي"])
    await edge_tts.Communicate(text,v,pitch=p,rate=r).save(str(out))

def mux(video,audio,out):
    subprocess.run([ff(),"-y","-i",str(video),"-i",str(audio),"-c:v","copy","-c:a","aac","-shortest",str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def fmt(t): t=int(t); return f"{t//60:02d}:{t%60:02d}"

async def clock(msg,state,start,stop):
    while not stop.is_set():
        try: await msg.edit_text(f"🎬 Najm Video AI v3.5 FREE\n⏱ {fmt(time.time()-start)}\n📊 {state['pct']}%\n⚙️ {state['stage']}\n🎞 {state['done']}/{state['total']}\n\n🆓 بدون fal")
        except: pass
        try: await asyncio.wait_for(stop.wait(),10)
        except asyncio.TimeoutError: pass

async def start(update,context):
    context.user_data.clear()
    ok=bool(TOKEN and CF_ACCOUNT and CF_TOKEN)
    await update.message.reply_text("🎬 Najm Video AI v3.5 FREE\n"+("✅ جاهز" if ok else "❌ مفتاح ناقص")+"\n\n🆓 لا يستخدم fal. أرسل القصة.")

async def cancel(update,context):
    t=ACTIVE_JOBS.get(update.effective_chat.id)
    if t and not t.done(): t.cancel(); await update.message.reply_text("🛑 تم طلب الإلغاء.")
    else: context.user_data.clear(); await update.message.reply_text("لا يوجد فيديو جارٍ.")

async def text(update,context):
    if ACTIVE_JOBS.get(update.effective_chat.id) and not ACTIVE_JOBS[update.effective_chat.id].done():
        return await update.message.reply_text("يوجد فيديو جارٍ. استخدم /cancel.")
    context.user_data={"idea":update.message.text.strip(),"stage":"style"}
    await update.message.reply_text("🎨 اختر النمط:",reply_markup=btn(["كرتون 2D","كرتون أطفال","أنمي"],"style"))

async def render(chat,bot,params):
    idea,style,dur,aspect=params; ss=scenes(idea,dur,style); startt=time.time()
    state={"pct":3,"stage":"بدء","done":0,"total":len(ss)}
    msg=await bot.send_message(chat,"🎬 بدء الإنشاء المجاني...")
    stop=asyncio.Event(); ct=asyncio.create_task(clock(msg,state,startt,stop))
    try:
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            async def one(i,s):
                state["stage"]=f"إنشاء الصورة {i}"
                img=td/f"s{i}.png"; await asyncio.to_thread(cf_image,s["prompt"],img)
                state["pct"]=10+int(45*i/len(ss))
                state["stage"]=f"تحريك المشهد {i}"
                clip=td/f"c{i}.mp4"; await asyncio.to_thread(motion,img,s["sec"],aspect,i,clip)
                state["done"]+=1; state["pct"]=55+int(25*state["done"]/len(ss))
                return clip
            res=await asyncio.gather(*[one(i,s) for i,s in enumerate(ss,1)],return_exceptions=True)
            clips=[r for r in res if not isinstance(r,Exception)]
            if not clips: raise RuntimeError("فشلت كل المشاهد.")
            state["pct"]=84; state["stage"]="دمج المشاهد"
            silent=td/"silent.mp4"; await asyncio.to_thread(concat,clips,silent)
            state["pct"]=90; state["stage"]="الصوت العربي"
            vf=td/"voice.mp3"; await voice(" ".join(s["text"] for s in ss),"طفل" if "طفل" in cast(idea) else "راوي",vf)
            state["pct"]=96; state["stage"]="التركيب النهائي"
            final=td/"final.mp4"; await asyncio.to_thread(mux,silent,vf,final)
            state["pct"]=100; stop.set()
            try: await ct
            except: pass
            await msg.edit_text(f"✅ اكتمل\n⏱ {fmt(time.time()-startt)}\n📊 100%")
            with final.open("rb") as f: await bot.send_video(chat,video=f,caption="✅ فيديو كرتوني مجاني 🆓")
    except asyncio.CancelledError:
        stop.set()
        try: await ct
        except: pass
        try: await msg.edit_text("🛑 تم الإلغاء.")
        except: pass
        raise
    except Exception as e:
        stop.set()
        try: await ct
        except: pass
        try: await msg.edit_text(f"❌ خطأ: {e}")
        except: pass
    finally:
        ACTIVE_JOBS.pop(chat,None)

async def cb(update,context):
    q=update.callback_query; await q.answer()
    k,v=q.data.split(":",1)
    if k=="style":
        context.user_data["style"]=v; context.user_data["stage"]="duration"
        await q.edit_message_text("⏱ اختر المدة:",reply_markup=btn(["15","30"],"duration"))
    elif k=="duration":
        context.user_data["duration"]=int(v); context.user_data["stage"]="aspect"
        await q.edit_message_text("📐 اختر المقاس:",reply_markup=btn(["9:16","16:9","1:1"],"aspect"))
    elif k=="aspect":
        context.user_data["aspect"]=v; context.user_data["stage"]="ready"
        await q.edit_message_text("🆓 جاهز — بدون fal\nالحركة سينمائية للصورة وليست حركة أطراف AI.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 إنشاء مجاني",callback_data="render:go")]]))
    elif k=="render":
        chat=q.message.chat_id
        p=(context.user_data["idea"],context.user_data["style"],context.user_data["duration"],context.user_data["aspect"])
        context.user_data.clear()
        await q.edit_message_text("✅ بدأ الوضع المجاني.")
        t=asyncio.create_task(render(chat,context.bot,p)); ACTIVE_JOBS[chat]=t

def main():
    if not TOKEN: raise RuntimeError("TELEGRAM_BOT_TOKEN غير موجود.")
    app=Application.builder().token(TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start",start)); app.add_handler(CommandHandler("cancel",cancel))
    app.add_handler(CallbackQueryHandler(cb)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text))
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__": main()
