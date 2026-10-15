package com.najm.tubenew;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.graphics.Color;
import android.graphics.Typeface;
import android.content.res.ColorStateList;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.view.KeyEvent;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.SeekBar;
import android.widget.Button;
import android.widget.Toast;
import android.net.Uri;

import com.google.android.exoplayer2.ExoPlayer;
import com.google.android.exoplayer2.Player;
import com.google.android.exoplayer2.MediaItem;
import com.google.android.exoplayer2.DefaultLoadControl;
import com.google.android.exoplayer2.PlaybackException;
import com.google.android.exoplayer2.source.MediaSource;
import com.google.android.exoplayer2.source.ProgressiveMediaSource;
import com.google.android.exoplayer2.source.MergingMediaSource;
import com.google.android.exoplayer2.source.hls.HlsMediaSource;
import com.google.android.exoplayer2.source.dash.DashMediaSource;
import com.google.android.exoplayer2.upstream.DefaultHttpDataSource;
import com.google.android.exoplayer2.upstream.HttpDataSource;
import com.google.android.exoplayer2.upstream.DefaultDataSource;
import com.google.android.exoplayer2.trackselection.DefaultTrackSelector;
import com.google.android.exoplayer2.ui.PlayerView;

import org.schabi.newpipe.extractor.stream.StreamInfo;
import org.schabi.newpipe.extractor.stream.VideoStream;
import org.schabi.newpipe.extractor.stream.AudioStream;

import java.util.List;
import java.util.Locale;

/** Standalone NAJM video screen; shares the lightweight ExoPlayer playback engine with V1.1. */
public final class VideoActivity extends Activity {
    private FrameLayout stage;
    private LinearLayout center;
    private TextView status, heading;
    private Button play, retryButton, webFallback;
    private SeekBar timeline;
    private ExoPlayer player;
    private final Handler ui=new Handler(Looper.getMainLooper());
    private boolean scrubbing=false;
    private boolean destroyed=false;
    private String videoTitle;
    private String videoUrl;
    private final java.util.concurrent.atomic.AtomicInteger loadRequest = new java.util.concurrent.atomic.AtomicInteger();
    private long readyAt;
    private final Runnable hide = () -> {
        if(center!=null && player!=null && player.isPlaying())center.setVisibility(View.INVISIBLE);
    };
    private final Runnable progress=new Runnable(){
        @Override public void run(){
            if(destroyed || player==null)return;
            if(!scrubbing){
                long duration=player.getDuration(),pos=player.getCurrentPosition();
                if(duration>0&&pos>=0)timeline.setProgress((int)Math.min(1000,pos*1000L/duration));
            }
            ui.postDelayed(this,500);
        }
    };
    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().setStatusBarColor(Color.BLACK);
        getWindow().setNavigationBarColor(Color.BLACK);
        videoTitle=getIntent().getStringExtra("title");
        String link=getIntent().getStringExtra("url");
        videoUrl=link;
        if(link==null){finish();return;}
        createPlayer();
        createLayout();
        resolveStream(link);
    }
    private void createPlayer(){
        DefaultTrackSelector selector=new DefaultTrackSelector(this);
        selector.setParameters(selector.buildUponParameters()
                .setMaxVideoSize(854,480).setExceedVideoConstraintsIfNecessary(true));
        DefaultLoadControl buffer=new DefaultLoadControl.Builder()
                .setBufferDurationsMs(3000,25000,1200,1800).build();
        player=new ExoPlayer.Builder(this).setTrackSelector(selector).setLoadControl(buffer).build();
        player.addListener(new Player.Listener(){
            @Override public void onIsPlayingChanged(boolean playing){
                if(play!=null)play.setText(playing?"Ⅱ":"▶");
                if(playing)scheduleHide();
                else if(center!=null)center.setVisibility(View.VISIBLE);
            }
            @Override public void onPlaybackStateChanged(int state){
                if(status==null)return;
                if(state==Player.STATE_BUFFERING)status.setText("جاري تحميل الفيديو...");
                if(state==Player.STATE_READY){
                    long delay=android.os.SystemClock.elapsedRealtime()-readyAt;
                    status.setText("جودة اقتصادية • بدأ التشغيل خلال "+(delay/1000)+" ثانية");
                }
                if(state==Player.STATE_ENDED){status.setText("انتهى الفيديو");center.setVisibility(View.VISIBLE);}
            }
            @Override public void onPlayerError(PlaybackException error){
                String detail=error.getErrorCodeName();
                Throwable cause=error;
                while(cause!=null){
                    if(cause instanceof HttpDataSource.InvalidResponseCodeException){
                        int code=((HttpDataSource.InvalidResponseCodeException)cause).responseCode;
                        detail="الخادم رفض تدفق الفيديو (HTTP "+code+")";
                        break;
                    }
                    cause=cause.getCause();
                }
                showError("تعذر تشغيل الفيديو: "+detail);
            }
        });
    }
    private void createLayout(){
        stage=new FrameLayout(this);stage.setBackgroundColor(Color.BLACK);
        PlayerView view=new PlayerView(this);
        view.setPlayer(player);view.setUseController(false);
        stage.addView(view,new FrameLayout.LayoutParams(-1,-1));
        View touch=new View(this);
        stage.addView(touch,new FrameLayout.LayoutParams(-1,-1));
        touch.setOnClickListener(v->{
            center.setVisibility(center.getVisibility()==View.VISIBLE?View.INVISIBLE:View.VISIBLE);
            if(center.getVisibility()==View.VISIBLE)scheduleHide();
        });
        touch.setOnTouchListener(new View.OnTouchListener(){
            long lastTap=0;float x=0;
            @Override public boolean onTouch(View v,android.view.MotionEvent e){
                if(e.getAction()==android.view.MotionEvent.ACTION_UP){
                    long now=android.os.SystemClock.uptimeMillis();
                    float newX=e.getX();
                    if(now-lastTap<300 && Math.abs(newX-x)<dp(110)){
                        int width=v.getWidth();
                        if(newX<width*0.36f)seek(-10000);
                        else if(newX>width*0.64f)seek(10000);
                        else toggle();
                        lastTap=0;
                        return true;
                    }
                    lastTap=now;x=newX;
                }
                return false;
            }
        });
        LinearLayout top=new LinearLayout(this);
        top.setPadding(dp(12),dp(8),dp(12),dp(6));
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.setBackgroundColor(0x99000000);
        Button back=button("رجوع");
        back.setOnClickListener(v->finish());
        top.addView(back,new LinearLayout.LayoutParams(dp(90),dp(43)));
        heading=new TextView(this);
        heading.setText(videoTitle==null?"نجم تيوب":videoTitle);
        heading.setTextColor(Color.WHITE);heading.setTextSize(16);
        heading.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        heading.setSingleLine(true);heading.setEllipsize(android.text.TextUtils.TruncateAt.END);
        heading.setPadding(dp(14),0,dp(8),0);
        top.addView(heading,new LinearLayout.LayoutParams(0,dp(45),1));
        webFallback=button("مشغل بديل");
        webFallback.setTextSize(12);
        webFallback.setVisibility(View.GONE);
        webFallback.setOnClickListener(v->openWebFallback());
        top.addView(webFallback,new LinearLayout.LayoutParams(dp(110),dp(43)));
        retryButton=button("إعادة");
        retryButton.setTextSize(12);
        retryButton.setVisibility(View.GONE);
        retryButton.setOnClickListener(v->{
            if(player!=null)player.stop();
            resolveStream(videoUrl);
        });
        top.addView(retryButton,new LinearLayout.LayoutParams(dp(72),dp(43)));
        stage.addView(top,new FrameLayout.LayoutParams(-1,-2,Gravity.TOP));

        center=new LinearLayout(this);
        center.setOrientation(LinearLayout.HORIZONTAL);
        center.setGravity(Gravity.CENTER);
        center.setBackgroundColor(0x22000000);
        Button rewind=button("↶ 10");
        play=button("▶");
        Button forward=button("10 ↷");
        rewind.setOnClickListener(v->{seek(-10000);scheduleHide();});
        play.setOnClickListener(v->{toggle();scheduleHide();});
        forward.setOnClickListener(v->{seek(10000);scheduleHide();});
        center.addView(rewind,new LinearLayout.LayoutParams(dp(95),dp(65)));
        LinearLayout.LayoutParams pp=new LinearLayout.LayoutParams(dp(90),dp(65));pp.setMargins(dp(10),0,dp(10),0);
        center.addView(play,pp);
        center.addView(forward,new LinearLayout.LayoutParams(dp(95),dp(65)));
        stage.addView(center,new FrameLayout.LayoutParams(-2,-2,Gravity.CENTER));
        LinearLayout bottom=new LinearLayout(this);
        bottom.setOrientation(LinearLayout.VERTICAL);
        bottom.setPadding(dp(15),dp(8),dp(15),dp(9));
        bottom.setBackgroundColor(0xAA000000);
        timeline=new SeekBar(this);
        timeline.setMax(1000);
        if(android.os.Build.VERSION.SDK_INT>=21){
            timeline.setProgressTintList(ColorStateList.valueOf(0xFFFF0033));
            timeline.setThumbTintList(ColorStateList.valueOf(0xFFFF0033));
        }
        bottom.addView(timeline,new LinearLayout.LayoutParams(-1,dp(31)));
        timeline.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){
            @Override public void onProgressChanged(SeekBar b,int p,boolean user){}
            @Override public void onStartTrackingTouch(SeekBar b){scrubbing=true;ui.removeCallbacks(hide);}
            @Override public void onStopTrackingTouch(SeekBar b){
                scrubbing=false;
                long duration=player.getDuration();
                if(duration>0&&player.isCurrentMediaItemSeekable())
                    player.seekTo(duration*b.getProgress()/1000);
                scheduleHide();
            }
        });
        status=new TextView(this);
        status.setText("جاري استخراج رابط الفيديو...");
        status.setTextColor(0xFFD7D7D7);status.setTextSize(12);
        status.setPadding(dp(5),0,dp(5),0);
        bottom.addView(status);
        stage.addView(bottom,new FrameLayout.LayoutParams(-1,-2,Gravity.BOTTOM));
        setContentView(stage);
        ui.post(progress);
    }
    private void resolveStream(String address){
        if(address==null||address.isEmpty())return;
        int request=loadRequest.incrementAndGet();
        retryButton.setVisibility(View.GONE);
        webFallback.setVisibility(View.GONE);
        status.setText("جاري تجهيز فيديو يوتيوب...");
        YoutubeData.IO.execute(()->{
            try{
                StreamInfo info=YoutubeData.video(address);
                VideoStream muxed=choose(info.getVideoStreams());
                VideoStream separated=choose(info.getVideoOnlyStreams());
                AudioStream audio=chooseAudio(info.getAudioStreams());
                final String manifest=info.getHlsUrl();
                final String hls=manifest==null?"":manifest;
                final String dash=info.getDashMpdUrl()==null?"":info.getDashMpdUrl();
                // Prefer complete MP4+audio stream. Use separate video/audio only if necessary.
                String videoUrl=muxed!=null&&muxed.isUrl()?muxed.getContent():null;
                String onlyVideo=separated!=null&&separated.isUrl()?separated.getContent():null;
                String audioUrl=audio!=null&&audio.isUrl()?audio.getContent():null;
                if(videoUrl==null && (onlyVideo==null||audioUrl==null) && hls.isEmpty() && dash.isEmpty()){
                    if(!info.getErrors().isEmpty()){
                        Throwable problem=info.getErrors().get(0);
                        throw new Exception("تعذر استخراج مسار الفيديو: "+problem.getClass().getSimpleName());
                    }
                    throw new Exception("المقطع لا يوفر تدفقًا متوافقًا");
                }
                ui.post(()->{
                    if(destroyed||player==null||loadRequest.get()!=request)return;
                    try{
                        DefaultHttpDataSource.Factory http=new DefaultHttpDataSource.Factory()
                            .setUserAgent("Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/131.0.0.0 Mobile Safari/537.36")
                            .setConnectTimeoutMs(11000)
                            .setReadTimeoutMs(15000)
                            .setAllowCrossProtocolRedirects(true);
                        DefaultDataSource.Factory factory=new DefaultDataSource.Factory(this,http);
                        MediaSource source;
                        if(videoUrl!=null) {
                            source=new ProgressiveMediaSource.Factory(factory)
                                .createMediaSource(MediaItem.fromUri(Uri.parse(videoUrl)));
                        } else if(onlyVideo!=null && audioUrl!=null){
                            MediaSource v=new ProgressiveMediaSource.Factory(factory)
                                .createMediaSource(MediaItem.fromUri(Uri.parse(onlyVideo)));
                            MediaSource a=new ProgressiveMediaSource.Factory(factory)
                                .createMediaSource(MediaItem.fromUri(Uri.parse(audioUrl)));
                            source=new MergingMediaSource(true,v,a);
                        }else if(!hls.isEmpty()){
                            source=new HlsMediaSource.Factory(factory)
                                .createMediaSource(MediaItem.fromUri(Uri.parse(hls)));
                        }else{
                            source=new DashMediaSource.Factory(factory)
                                .createMediaSource(MediaItem.fromUri(Uri.parse(dash)));
                        }
                        readyAt=android.os.SystemClock.elapsedRealtime();
                        player.setMediaSource(source);player.prepare();player.play();
                        status.setText("جاري بدء الفيديو...");
                        scheduleHide();
                    }catch(Exception e){showError("تعذر تجهيز الفيديو: "+shortError(e));}
                });
            }catch(Exception e){
                String message=e.getMessage()==null?e.getClass().getSimpleName():e.getMessage();
                ui.post(()->{
                    if(destroyed||loadRequest.get()!=request)return;
                    showError("تعذر تجهيز هذا الفيديو: "+message);
                });
            }
        });
    }
    private void showError(String explanation) {
        if(status!=null)status.setText(explanation);
        if(center!=null)center.setVisibility(View.VISIBLE);
        if(retryButton!=null)retryButton.setVisibility(View.VISIBLE);
        if(webFallback!=null)webFallback.setVisibility(View.VISIBLE);
    }
    private String shortError(Exception e){
        String m=e.getMessage();
        if(m==null||m.trim().isEmpty())return e.getClass().getSimpleName();
        return m.length()>150?m.substring(0,150):m;
    }
    private void openWebFallback(){
        if(videoUrl==null)return;
        Intent i=new Intent(this,WebPlayerActivity.class);
        i.putExtra("url",videoUrl);
        startActivity(i);
    }
    private VideoStream choose(List<VideoStream> list){
        if(list==null)return null;
        VideoStream selected=null;
        int best=-100000;
        for(VideoStream stream:list){
            if(!stream.isUrl())continue;
            int height=stream.getHeight();
            if(height<=0){
                try{height=Integer.parseInt(stream.getResolution().replaceAll("[^0-9]",""));}catch(Exception ignored){height=360;}
            }
            // Highest stream <=480; if none available, choose the smallest higher stream.
            int score=height<=480?10000+height:1000-height;
            if(stream.getCodec()!=null && stream.getCodec().toLowerCase(Locale.US).contains("avc"))score+=100;
            if(score>best){best=score;selected=stream;}
        }
        return selected;
    }
    private AudioStream chooseAudio(List<AudioStream> list){
        if(list==null)return null;
        AudioStream candidate=null;int best=Integer.MIN_VALUE;
        for(AudioStream stream:list){
            if(!stream.isUrl())continue;
            int rate=stream.getAverageBitrate();
            int score=rate<=160?rate:160-(rate-160);
            if(stream.getFormat()!=null && stream.getFormat().toString().contains("M4A"))score+=1000;
            if(score>best){best=score;candidate=stream;}
        }
        return candidate;
    }
    private void toggle(){if(player.isPlaying())player.pause();else player.play();}
    private void seek(long delta){
        if(player==null||!player.isCurrentMediaItemSeekable())return;
        long end=player.getDuration();
        long target=Math.max(0,player.getCurrentPosition()+delta);
        if(end>0)target=Math.min(target,end);
        player.seekTo(target);center.setVisibility(View.VISIBLE);scheduleHide();
    }
    private void scheduleHide(){ui.removeCallbacks(hide);ui.postDelayed(hide,3600);}
    private Button button(String text){
        Button b=new Button(this);
        b.setAllCaps(false);b.setText(text);b.setTextColor(Color.WHITE);
        b.setTextSize(18);b.setBackgroundColor(0xFF313131);
        return b;
    }
    private int dp(int n){return (int)(getResources().getDisplayMetrics().density*n+0.5f);}
    @Override public boolean onKeyDown(int keyCode,KeyEvent event){
        if(player!=null){
            if(keyCode==KeyEvent.KEYCODE_DPAD_CENTER||keyCode==KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE){toggle();return true;}
            if(keyCode==KeyEvent.KEYCODE_DPAD_LEFT){seek(-10000);return true;}
            if(keyCode==KeyEvent.KEYCODE_DPAD_RIGHT){seek(10000);return true;}
        }
        return super.onKeyDown(keyCode,event);
    }
    @Override protected void onStop(){if(player!=null)player.pause();super.onStop();}
    @Override protected void onDestroy(){
        destroyed=true;loadRequest.incrementAndGet();ui.removeCallbacksAndMessages(null);
        if(player!=null){player.release();player=null;}
        super.onDestroy();
    }
}
