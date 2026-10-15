package com.najm.tubenew;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Button;
import android.net.Uri;
import java.util.HashMap;
import java.util.Map;

/**
 * Optional in-app fallback for videos that cannot be extracted as direct streams.
 * ExoPlayer stays the default; a YouTube embed only loads after an explicit tap.
 * Video availability on legacy WebView versions is not guaranteed.
 */
public final class WebPlayerActivity extends Activity {
    private WebView web;
    private FrameLayout root;
    private View fullScreen;
    private WebChromeClient.CustomViewCallback fullCallback;

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        String url=getIntent().getStringExtra("url");
        String id=extractId(url);
        if(id==null) {finish();return;}
        root=new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);
        setContentView(root);
        web=new WebView(this);
        web.setBackgroundColor(Color.BLACK);
        WebSettings settings=web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setLoadsImagesAutomatically(true);
        if(Build.VERSION.SDK_INT>=17) settings.setMediaPlaybackRequiresUserGesture(false);
        web.setWebViewClient(new WebViewClient() {
            @Override public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
                // Video site updates or unsupported old WebViews can require an alternative browser.
                android.util.Log.w("NAJM_WEB_PLAYER","WebView error: "+errorCode+" "+description);
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public void onShowCustomView(View view, CustomViewCallback callback) {
                if(fullScreen!=null) { callback.onCustomViewHidden(); return; }
                fullScreen=view;
                fullCallback=callback;
                web.setVisibility(View.GONE);
                root.addView(view,new FrameLayout.LayoutParams(-1,-1));
            }
            @Override public void onHideCustomView() { dismissFullscreen(); }
        });
        root.addView(web,new FrameLayout.LayoutParams(-1,-1));
        Button back=new Button(this);
        back.setText("↩ رجوع");
        back.setTextColor(Color.WHITE);
        back.setTextSize(12);
        back.setAllCaps(false);
        back.setBackgroundColor(0xAA171717);
        back.setOnClickListener(v->finish());
        FrameLayout.LayoutParams bp=new FrameLayout.LayoutParams(100,44,Gravity.TOP|Gravity.LEFT);
        root.addView(back,bp);
        TextView note=new TextView(this);
        note.setText("مشغل احتياطي — قد لا يعمل على أندرويد القديم");
        note.setTextColor(0xFFDDDDDD);
        note.setTextSize(11);
        note.setPadding(12,8,12,8);
        FrameLayout.LayoutParams np=new FrameLayout.LayoutParams(-2,-2,Gravity.BOTTOM|Gravity.CENTER_HORIZONTAL);
        root.addView(note,np);
        Map<String,String> headers=new HashMap<>();
        headers.put("Referer","https://www.youtube.com/");
        web.loadUrl("https://www.youtube.com/embed/"+id+"?autoplay=1&controls=1&playsinline=1&rel=0",headers);
    }
    private static String extractId(String url) {
        if(url==null)return null;
        try {
            Uri u=Uri.parse(url);
            String id=u.getQueryParameter("v");
            if(id==null || id.isEmpty())id=u.getLastPathSegment();
            return id!=null && id.matches("[A-Za-z0-9_-]{11}")?id:null;
        }catch(Exception ignored){return null;}
    }
    private void dismissFullscreen(){
        if(fullScreen!=null){
            root.removeView(fullScreen);
            fullScreen=null;
            web.setVisibility(View.VISIBLE);
            if(fullCallback!=null)fullCallback.onCustomViewHidden();
            fullCallback=null;
        }
    }
    @Override public void onBackPressed(){
        if(fullScreen!=null){dismissFullscreen();return;}
        super.onBackPressed();
    }
    @Override protected void onPause(){if(web!=null)web.onPause();super.onPause();}
    @Override protected void onResume(){super.onResume();if(web!=null)web.onResume();}
    @Override protected void onDestroy(){
        dismissFullscreen();
        if(web!=null){
            web.loadUrl("about:blank");
            root.removeView(web);
            web.destroy();
            web=null;
        }
        super.onDestroy();
    }
}
