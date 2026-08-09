import os, base64, asyncio, logging, tempfile, subprocess
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont
import edge_tts
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import imageio_ffmpeg

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
CF_ACCOUNT = os.getenv('CLOUDFLARE_ACCOUNT_ID', '').strip()
CF_TOKEN = os.getenv('CLOUDFLARE_API_TOKEN', '').strip()

logging.basicConfig(level=logging.INFO)
VOICE_MAP = {
    'سعودي': 'ar-SA-HamedNeural',
    'فصحى': 'ar-SA-ZariyahNeural',
    'عربي عامي': 'ar-EG-ShakirNeural',
    'حماسي': 'ar-SA-HamedNeural',
}
STYLE_MAP = {
    'كرتون 3D': 'high quality 3D animated family movie style, expressive characters, soft cinematic lighting, colorful, polished',
    'كرتون أطفال': "friendly children's cartoon illustration, bright colors, cute expressive characters, simple clean shapes",
    'أنمي': 'high quality anime illustration, cinematic composition, expressive faces, detailed background',
    'رسوم 2D': 'clean 2D animated cartoon style, hand-drawn look, colorful, consistent character design',
}

def cf_enabled(): return bool(CF_ACCOUNT and CF_TOKEN)

def buttons(items, prefix):
    rows=[]
    for i in range(0,len(items),2):
        rows.append([InlineKeyboardButton(v, callback_data=f'{prefix}:{v}') for v in items[i:i+2]])
    return InlineKeyboardMarkup(rows)

def storyboard(idea, duration, style):
    count = 4 if duration <= 15 else (6 if duration <= 30 else 9)
    sec = duration / count
    visual_style = STYLE_MAP.get(style, STYLE_MAP['كرتون 3D'])
    beats = [
        'افتتاحية جذابة تعرف بالمكان والشخصية الرئيسية',
        'الشخصية تبدأ الحدث أو المشكلة',
        'تطور واضح في القصة مع حركة وتفاعل',
        'لقطة قريبة تظهر تعبيرات الشخصية',
        'انتقال إلى مكان أو حدث جديد',
        'لحظة مهمة أو مفاجأة في القصة',
        'الحل يبدأ بالظهور',
        'النتيجة النهائية',
        'نهاية جميلة ومؤثرة',
    ]
    scenes=[]
    for i in range(count):
        narration = f'{idea}. ' + ('تبدأ القصة من هنا.' if i==0 else 'تتطور الأحداث بطريقة ممتعة.' if i<count-1 else 'وهكذا تنتهي القصة بشكل جميل.')
        prompt = (
            f'{visual_style}. Story concept: {idea}. Scene {i+1}/{count}: {beats[i % len(beats)]}. '
            'Keep the SAME main character design, same face, same hair, same clothes and same colors across all scenes. '
            'Use coherent environment and story continuity. No text, no captions, no watermark, no logo.'
        )
        scenes.append((narration,prompt,sec))
    return scenes

def cloudflare_image(prompt, out_path):
    model='@cf/black-forest-labs/flux-1-schnell'
    url=f'https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/{model}'
    headers={'Authorization':f'Bearer {CF_TOKEN}','Content-Type':'application/json'}
    r=requests.post(url,headers=headers,json={'prompt':prompt,'num_steps':4},timeout=180)
    r.raise_for_status()
    if 'image/' in r.headers.get('content-type',''):
        Path(out_path).write_bytes(r.content); return
    data=r.json(); result=data.get('result',{})
    if isinstance(result,dict) and result.get('image'):
        Path(out_path).write_bytes(base64.b64decode(result['image'])); return
    raise RuntimeError('Cloudflare لم يرجع صورة.')

def ffmpeg(): return imageio_ffmpeg.get_ffmpeg_exe()

def make_scene_video(image_path, seconds, aspect, out_path):
    ff=ffmpeg(); w,h=(720,1280) if aspect=='9:16' else ((1280,720) if aspect=='16:9' else (1080,1080))
    frames=max(1,int(seconds*25))
    vf=(f'scale={w*2}:{h*2}:force_original_aspect_ratio=increase,crop={w*2}:{h*2},'
        f"zoompan=z='min(zoom+0.0010,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps=25,format=yuv420p")
    subprocess.run([ff,'-y','-loop','1','-i',str(image_path),'-vf',vf,'-t',str(seconds),'-an',str(out_path)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def concat_videos(clips,out_path):
    ff=ffmpeg(); txt=Path(out_path).with_suffix('.txt'); txt.write_text('\n'.join(f"file '{Path(c).as_posix()}'" for c in clips),encoding='utf-8')
    subprocess.run([ff,'-y','-f','concat','-safe','0','-i',str(txt),'-c','copy',str(out_path)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def mux_audio(video,audio,out_path):
    ff=ffmpeg(); subprocess.run([ff,'-y','-i',str(video),'-i',str(audio),'-c:v','copy','-c:a','aac','-shortest','-movflags','+faststart',str(out_path)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

async def voice(text,style,out_path):
    await edge_tts.Communicate(text,VOICE_MAP.get(style,'ar-SA-HamedNeural')).save(str(out_path))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    mode='🤖 مولد صور كرتونية AI جاهز' if cf_enabled() else '⚠️ يحتاج تفعيل Cloudflare للصور الكرتونية الحقيقية'
    await update.message.reply_text(f'🎬 Najm Video AI Cartoon v2\n{mode}\n\nأرسل القصة أو الفكرة، مثال:\nطفل وجد قطة صغيرة تحت المطر وأخذها إلى البيت')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear(); await update.message.reply_text('تم الإلغاء.')

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('stage'):
        return await update.message.reply_text('أكمل الخيارات بالأزرار أو استخدم /cancel.')
    context.user_data['idea']=update.message.text.strip(); context.user_data['stage']='style'
    await update.message.reply_text('🎨 اختر شكل الرسوم:',reply_markup=buttons(['كرتون 3D','كرتون أطفال','أنمي','رسوم 2D'],'style'))

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); key,val=q.data.split(':',1)
    if key=='style':
        context.user_data['style']=val; context.user_data['stage']='duration'; await q.edit_message_text('⏱ اختر المدة:',reply_markup=buttons(['15','30','60'],'duration'))
    elif key=='duration':
        context.user_data['duration']=int(val); context.user_data['stage']='aspect'; await q.edit_message_text('📐 اختر المقاس:',reply_markup=buttons(['9:16','16:9','1:1'],'aspect'))
    elif key=='aspect':
        context.user_data['aspect']=val; context.user_data['stage']='voice'; await q.edit_message_text('🎙 اختر الصوت:',reply_markup=buttons(['سعودي','فصحى','عربي عامي','حماسي'],'voice'))
    elif key=='voice':
        context.user_data['voice']=val; context.user_data['stage']='ready'; await q.edit_message_text('✅ جاهز للإنشاء',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🚀 إنشاء القصة الكرتونية',callback_data='render:go')]]))
    elif key=='render':
        if not cf_enabled():
            await q.edit_message_text('⚠️ الصور الكرتونية الحقيقية تحتاج متغيرين في Railway:\nCLOUDFLARE_ACCOUNT_ID\nCLOUDFLARE_API_TOKEN\n\nبعد إضافتهما أعد المحاولة.')
            context.user_data.clear(); return
        idea=context.user_data['idea']; style=context.user_data['style']; duration=context.user_data['duration']; aspect=context.user_data['aspect']; vstyle=context.user_data['voice']
        await q.edit_message_text('🚀 بدأ إنشاء القصة الكرتونية…')
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); clips=[]; narr=[]; scenes=storyboard(idea,duration,style)
            for i,(n,p,sec) in enumerate(scenes,1):
                await context.bot.send_message(q.message.chat_id,f'🎨 إنشاء الصورة الكرتونية {i}/{len(scenes)}')
                img=td/f's{i}.png'; clip=td/f's{i}.mp4'
                await asyncio.to_thread(cloudflare_image,p,img)
                await asyncio.to_thread(make_scene_video,img,sec,aspect,clip)
                clips.append(clip); narr.append(n)
            silent=td/'silent.mp4'; audio=td/'voice.mp3'; final=td/'final.mp4'
            await asyncio.to_thread(concat_videos,clips,silent)
            await context.bot.send_message(q.message.chat_id,'🎙 إنشاء الصوت العربي…')
            await voice(' '.join(narr),vstyle,audio)
            await context.bot.send_message(q.message.chat_id,'🎬 تركيب القصة الكرتونية…')
            await asyncio.to_thread(mux_audio,silent,audio,final)
            with final.open('rb') as f:
                await context.bot.send_video(q.message.chat_id,video=f,caption=f'✅ قصة كرتونية - {style}')
        context.user_data.clear()

def main():
    if not TOKEN: raise RuntimeError('TELEGRAM_BOT_TOKEN غير موجود.')
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start',start)); app.add_handler(CommandHandler('cancel',cancel)); app.add_handler(CallbackQueryHandler(callback)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler))
    app.run_polling(drop_pending_updates=True)

if __name__=='__main__': main()
