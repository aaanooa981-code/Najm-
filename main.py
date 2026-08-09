import os, asyncio, logging, tempfile, subprocess, base64
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont
import edge_tts
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN=os.getenv('TELEGRAM_BOT_TOKEN','').strip()
CF_ACCOUNT=os.getenv('CLOUDFLARE_ACCOUNT_ID','').strip()
CF_TOKEN=os.getenv('CLOUDFLARE_API_TOKEN','').strip()
logging.basicConfig(level=logging.INFO)
VOICE_MAP={'سعودي':'ar-SA-HamedNeural','فصحى':'ar-SA-ZariyahNeural','عربي عامي':'ar-EG-ShakirNeural','حماسي':'ar-SA-HamedNeural'}

def cf_enabled(): return bool(CF_ACCOUNT and CF_TOKEN)

def storyboard(idea,duration):
    n=3 if duration<=15 else (5 if duration<=30 else 8); sec=duration/n; out=[]
    for i in range(n):
        narr=f'شاهد هذه الفكرة بشكل مختلف. {idea}' if i==0 else ('إذا أعجبتك النتيجة، جرّبها الآن.' if i==n-1 else 'نستعرض أهم التفاصيل بصورة واضحة وجذابة.')
        prompt=f'Cinematic premium social media advertisement about: {idea}. Scene {i+1} of {n}. Realistic lighting, premium composition, consistent style, no text, no watermark.'
        out.append((narr,prompt,sec))
    return out

def local_image(idea,no,aspect,path):
    size=(1280,720) if aspect=='16:9' else ((1080,1080) if aspect=='1:1' else (720,1280))
    img=Image.new('RGB',size,(20+no*8,28,55+no*6)); d=ImageDraw.Draw(img); w,h=size
    d.rounded_rectangle((int(w*.08),int(h*.2),int(w*.92),int(h*.8)),radius=32,fill=(40,48,78),outline=(150,160,200),width=3)
    try: font=ImageFont.truetype('DejaVuSans.ttf',max(24,int(w*.045)))
    except: font=ImageFont.load_default()
    d.text((int(w*.12),int(h*.34)),f'Najm Video AI - Scene {no}',fill='white',font=font)
    d.text((int(w*.12),int(h*.5)),idea[:60],fill=(225,225,235),font=font)
    img.save(path)

def cloudflare_image(prompt,path):
    model='@cf/black-forest-labs/flux-1-schnell'
    url=f'https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/{model}'
    r=requests.post(url,headers={'Authorization':f'Bearer {CF_TOKEN}','Content-Type':'application/json'},json={'prompt':prompt,'num_steps':4},timeout=180); r.raise_for_status()
    if 'image/' in r.headers.get('content-type',''):
        Path(path).write_bytes(r.content); return True
    data=r.json(); result=data.get('result',{})
    if isinstance(result,dict) and result.get('image'):
        Path(path).write_bytes(base64.b64decode(result['image'])); return True
    return False

async def make_voice(text,style,path): await edge_tts.Communicate(text,VOICE_MAP.get(style,'ar-SA-HamedNeural')).save(str(path))

def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

def scene_video(img,seconds,aspect,out):
    w,h=(1280,720) if aspect=='16:9' else ((1080,1080) if aspect=='1:1' else (720,1280))
    subprocess.run([ffmpeg(),'-y','-loop','1','-i',str(img),'-vf',f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},format=yuv420p','-t',str(seconds),'-r','25','-an',str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def concat(clips,out):
    listing=Path(out).with_suffix('.txt'); listing.write_text('\n'.join(f"file '{Path(x).as_posix()}'" for x in clips),encoding='utf-8')
    subprocess.run([ffmpeg(),'-y','-f','concat','-safe','0','-i',str(listing),'-c','copy',str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def mux(video,audio,out):
    subprocess.run([ffmpeg(),'-y','-i',str(video),'-i',str(audio),'-c:v','copy','-c:a','aac','-shortest','-movflags','+faststart',str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def kb(items,prefix):
    return InlineKeyboardMarkup([[InlineKeyboardButton(v,callback_data=f'{prefix}:{v}') for v in items[i:i+2]] for i in range(0,len(items),2)])

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    context.user_data.clear(); mode='🤖 AI عبر Cloudflare' if cf_enabled() else '🧪 وضع تجريبي مجاني'
    await update.message.reply_text(f'🎬 Najm Video AI Bot\n{mode}\n\nأرسل فكرة الفيديو، مثال:\nإعلان 15 ثانية لمصابيح LED للسيارات')

async def cancel(update,context): context.user_data.clear(); await update.message.reply_text('تم الإلغاء.')

async def text_handler(update,context):
    if context.user_data.get('stage'): return await update.message.reply_text('أكمل الاختيارات بالأزرار أو أرسل /cancel.')
    context.user_data['idea']=update.message.text.strip(); context.user_data['stage']='kind'
    await update.message.reply_text('اختر النوع:',reply_markup=kb(['إعلان','ريلز','قصة','منتج'],'kind'))

async def callback(update,context):
    q=update.callback_query; await q.answer(); key,value=q.data.split(':',1)
    if key=='kind':
        context.user_data['kind']=value; context.user_data['stage']='duration'; return await q.edit_message_text('اختر المدة:',reply_markup=kb(['15','30','60'],'duration'))
    if key=='duration':
        context.user_data['duration']=int(value); context.user_data['stage']='aspect'; return await q.edit_message_text('اختر المقاس:',reply_markup=kb(['9:16','16:9','1:1'],'aspect'))
    if key=='aspect':
        context.user_data['aspect']=value; context.user_data['stage']='voice'; return await q.edit_message_text('اختر الصوت:',reply_markup=kb(['سعودي','فصحى','عربي عامي','حماسي'],'voice'))
    if key=='voice':
        context.user_data['voice']=value; context.user_data['stage']='ready'; return await q.edit_message_text('جاهز ✅',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🚀 إنشاء الفيديو',callback_data='render:go')]]))
    if key=='render':
        await q.edit_message_text('🚀 بدأ إنشاء الفيديو…')
        idea=context.user_data['idea']; duration=context.user_data['duration']; aspect=context.user_data['aspect']; voice=context.user_data['voice']
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); clips=[]; narr=[]; scenes=storyboard(idea,duration)
            for idx,(n,p,sec) in enumerate(scenes,1):
                await context.bot.send_message(q.message.chat_id,f'🎨 المشهد {idx}/{len(scenes)}')
                img=td/f's{idx}.png'; clip=td/f's{idx}.mp4'; ok=False
                if cf_enabled():
                    try: ok=await asyncio.to_thread(cloudflare_image,p,img)
                    except: ok=False
                if not ok: await asyncio.to_thread(local_image,idea,idx,aspect,img)
                await asyncio.to_thread(scene_video,img,sec,aspect,clip); clips.append(clip); narr.append(n)
            silent=td/'silent.mp4'; final=td/'final.mp4'; await asyncio.to_thread(concat,clips,silent)
            try:
                audio=td/'voice.mp3'; await context.bot.send_message(q.message.chat_id,'🎙 إنشاء الصوت العربي…'); await make_voice(' '.join(narr),voice,audio); await asyncio.to_thread(mux,silent,audio,final)
            except: final.write_bytes(silent.read_bytes())
            with final.open('rb') as f: await context.bot.send_video(chat_id=q.message.chat_id,video=f,caption='✅ تم إنشاء الفيديو بواسطة Najm Video AI')
        context.user_data.clear()

def main():
    if not TOKEN: raise RuntimeError('TELEGRAM_BOT_TOKEN غير موجود في Railway Variables.')
    app=Application.builder().token(TOKEN).build(); app.add_handler(CommandHandler('start',start)); app.add_handler(CommandHandler('cancel',cancel)); app.add_handler(CallbackQueryHandler(callback)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler)); app.run_polling(drop_pending_updates=True)

if __name__=='__main__': main()
