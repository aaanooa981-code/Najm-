package com.najm.tubelite;

import android.app.Activity;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.Toast;

import com.google.android.exoplayer2.ExoPlayer;
import com.google.android.exoplayer2.DefaultLoadControl;
import com.google.android.exoplayer2.MediaItem;
import com.google.android.exoplayer2.PlaybackException;
import com.google.android.exoplayer2.Player;
import com.google.android.exoplayer2.trackselection.DefaultTrackSelector;
import com.google.android.exoplayer2.ui.PlayerView;

public final class MainActivity extends Activity {
    private ExoPlayer player;
    private LinearLayout controls;
    private EditText urlInput;
    private Button playPause;
    private SeekBar seek;
    private TextView status;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean dragging;
    private final Runnable hide = () -> {
        if (player != null && player.isPlaying()) controls.setVisibility(View.INVISIBLE);
    };
    private final Runnable tick = new Runnable() {
        @Override public void run() {
            if (player != null && seek != null) {
                long duration = player.getDuration();
                long position = player.getCurrentPosition();
                if (!dragging && duration > 0 && position >= 0)
                    seek.setProgress((int)Math.min(1000L, position * 1000L / duration));
                handler.postDelayed(this, 550);
            }
        }
    };
    @Override public void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        if (android.os.Build.VERSION.SDK_INT >= 21) {
            getWindow().setStatusBarColor(Color.BLACK);
            getWindow().setNavigationBarColor(Color.BLACK);
        }
        DefaultTrackSelector selector = new DefaultTrackSelector(this);
        selector.setParameters(selector.buildUponParameters()
            .setMaxVideoSize(854,480)
            .setExceedVideoConstraintsIfNecessary(false));
        DefaultLoadControl loadControl = new DefaultLoadControl.Builder()
            .setBufferDurationsMs(2500,20000,1000,1500).build();
        player = new ExoPlayer.Builder(this).setTrackSelector(selector)
            .setLoadControl(loadControl).build();

        LinearLayout root = new LinearLayout(this);
        root.setBackgroundColor(Color.BLACK);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setLayoutDirection(View.LAYOUT_DIRECTION_LTR);
        LinearLayout header = new LinearLayout(this);
        header.setBackgroundColor(0xFF202020);
        header.setPadding(dp(8), dp(4), dp(8), dp(4));
        urlInput = new EditText(this);
        urlInput.setSingleLine(true);
        urlInput.setTextSize(13f);
        urlInput.setTextColor(Color.WHITE);
        urlInput.setHintTextColor(0xFFAAAAAA);
        urlInput.setHint("رابط بث فيديو MP4 / HLS / DASH");
        urlInput.setInputType(android.text.InputType.TYPE_CLASS_TEXT |
            android.text.InputType.TYPE_TEXT_VARIATION_URI);
        urlInput.setImeOptions(EditorInfo.IME_ACTION_GO);
        urlInput.setOnEditorActionListener((v, id, event) -> {
            if (id == EditorInfo.IME_ACTION_GO) { openStream(); return true; }
            return false;
        });
        header.addView(urlInput, new LinearLayout.LayoutParams(0, dp(43), 1f));
        Button open = button("تشغيل");
        open.setOnClickListener(v -> openStream());
        header.addView(open, new LinearLayout.LayoutParams(dp(84), dp(43)));
        root.addView(header);

        FrameLayout videoFrame = new FrameLayout(this);
        PlayerView playerView = new PlayerView(this);
        playerView.setBackgroundColor(Color.BLACK);
        playerView.setUseController(false);
        playerView.setPlayer(player);
        videoFrame.addView(playerView, new FrameLayout.LayoutParams(-1,-1));

        // Touch-to-toggle player controls, and D-pad remote support.
        View touch = new View(this);
        videoFrame.addView(touch, new FrameLayout.LayoutParams(-1,-1));
        touch.setOnClickListener(v -> {
            controls.setVisibility(controls.getVisibility()==View.VISIBLE?View.INVISIBLE:View.VISIBLE);
            if (controls.getVisibility()==View.VISIBLE) scheduleHide();
        });

        controls = new LinearLayout(this);
        controls.setOrientation(LinearLayout.HORIZONTAL);
        controls.setGravity(Gravity.CENTER);
        controls.setPadding(dp(6),dp(5),dp(6),dp(5));
        controls.setBackgroundColor(0x66000000);
        Button back = button("↶ 10");
        playPause = button("▶");
        Button fwd = button("10 ↷");
        back.setOnClickListener(v -> { jump(-10000); scheduleHide(); });
        playPause.setOnClickListener(v -> { toggle(); scheduleHide(); });
        fwd.setOnClickListener(v -> { jump(10000); scheduleHide(); });
        controls.addView(back, new LinearLayout.LayoutParams(dp(85), dp(55)));
        controls.addView(playPause, new LinearLayout.LayoutParams(dp(78), dp(55)));
        controls.addView(fwd, new LinearLayout.LayoutParams(dp(85), dp(55)));
        videoFrame.addView(controls,new FrameLayout.LayoutParams(-2,-2,Gravity.CENTER));
        seek = new SeekBar(this);
        seek.setMax(1000);
        FrameLayout.LayoutParams seekParams = new FrameLayout.LayoutParams(-1,dp(46),Gravity.BOTTOM);
        seekParams.setMargins(dp(12),0,dp(12),dp(2));
        videoFrame.addView(seek,seekParams);
        seek.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar s, int i, boolean user) {}
            @Override public void onStartTrackingTouch(SeekBar s) { dragging=true; handler.removeCallbacks(hide); }
            @Override public void onStopTrackingTouch(SeekBar s) {
                dragging=false;
                long duration=player.getDuration();
                if (duration>0 && player.isCurrentMediaItemSeekable())
                    player.seekTo(duration*s.getProgress()/1000L);
                scheduleHide();
            }
        });
        root.addView(videoFrame,new LinearLayout.LayoutParams(-1,0,1));
        status = new TextView(this);
        status.setPadding(dp(10),dp(5),dp(10),dp(5));
        status.setTextColor(0xFFC7C7C7);
        status.setTextSize(12f);
        status.setText("نجم تيوب لايت | تشغيل روابط الفيديو المباشرة | جودة 480p");
        root.addView(status);
        setContentView(root);

        player.addListener(new Player.Listener() {
            @Override public void onIsPlayingChanged(boolean playing) { showPlayState(); if (playing) scheduleHide(); }
            @Override public void onPlaybackStateChanged(int state) {
                if(state==Player.STATE_BUFFERING) status.setText("جاري تحميل الفيديو...");
                else if(state==Player.STATE_READY) status.setText("جاهز للتشغيل • الحد الأعلى 480p");
                else if(state==Player.STATE_ENDED) { status.setText("انتهى الفيديو"); controls.setVisibility(View.VISIBLE); }
            }
            @Override public void onPlayerError(PlaybackException error) {
                status.setText("تعذر التشغيل: " + error.getErrorCodeName());
                controls.setVisibility(View.VISIBLE);
            }
        });
        handler.post(tick);
    }

    private void openStream() {
        String address=urlInput.getText().toString().trim();
        if(address.isEmpty()) {
            Toast.makeText(this,"أدخل رابط بث مباشر",Toast.LENGTH_SHORT).show();return;
        }
        Uri uri=Uri.parse(address);
        String scheme=uri.getScheme();
        String host=uri.getHost();
        if(scheme==null || !(scheme.equalsIgnoreCase("http")||scheme.equalsIgnoreCase("https"))||host==null) {
            Toast.makeText(this,"الرابط يجب أن يكون HTTP أو HTTPS",Toast.LENGTH_LONG).show();return;
        }
        String h=host.toLowerCase(java.util.Locale.US);
        if(h.equals("youtube.com")||h.endsWith(".youtube.com")||h.equals("youtu.be")||h.endsWith(".youtu.be")) {
            Toast.makeText(this,"هذه نسخة محرك اختبار: روابط يوتيوب العادية غير مدعومة",Toast.LENGTH_LONG).show();return;
        }
        try {
            player.setMediaItem(MediaItem.fromUri(uri));
            player.prepare();
            player.play();
            controls.setVisibility(View.VISIBLE);
            status.setText("جاري بدء التشغيل...");
            urlInput.clearFocus();
            InputMethodManager imm=(InputMethodManager)getSystemService(INPUT_METHOD_SERVICE);
            if(imm!=null) imm.hideSoftInputFromWindow(urlInput.getWindowToken(),0);
        } catch(Exception e) {
            status.setText("تعذر فتح هذا الرابط");
        }
    }
    private void jump(long ms) {
        if(!player.isCurrentMediaItemSeekable()) return;
        long duration=player.getDuration();
        long target=Math.max(0,player.getCurrentPosition()+ms);
        if(duration>0) target=Math.min(duration,target);
        player.seekTo(target);
    }
    private void toggle() {
        if(player.isPlaying()) player.pause(); else player.play();
        showPlayState();
    }
    private void showPlayState() {
        if(playPause!=null) playPause.setText(player.isPlaying()?"❚❚":"▶");
    }
    private void scheduleHide() {
        handler.removeCallbacks(hide);
        handler.postDelayed(hide,3500);
    }
    @Override public boolean onKeyDown(int keyCode,KeyEvent event) {
        if(player!=null) {
            if(keyCode==KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE || keyCode==KeyEvent.KEYCODE_DPAD_CENTER) { toggle();return true; }
            if(keyCode==KeyEvent.KEYCODE_DPAD_LEFT) { jump(-10000);return true; }
            if(keyCode==KeyEvent.KEYCODE_DPAD_RIGHT) { jump(10000);return true; }
        }
        return super.onKeyDown(keyCode,event);
    }
    private Button button(String text) {
        Button b=new Button(this);
        b.setAllCaps(false);
        b.setText(text);
        b.setTextColor(Color.WHITE);
        b.setTextSize(14f);
        if(android.os.Build.VERSION.SDK_INT>=21)
            b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(0xFF303030));
        else b.setBackgroundColor(0xFF303030);
        return b;
    }
    private int dp(int val) {
        return (int)(getResources().getDisplayMetrics().density*val+0.5f);
    }
    @Override protected void onStop() { if(player!=null) player.pause(); super.onStop(); }
    @Override protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        if(player!=null){player.release();player=null;}
        super.onDestroy();
    }
}
