package com.najm.tubenew;

import android.app.Activity;
import android.os.Bundle;
import android.content.Intent;
import android.content.res.Configuration;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.util.LruCache;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;

import org.schabi.newpipe.extractor.Image;
import org.schabi.newpipe.extractor.stream.StreamInfoItem;

import java.net.URL;
import java.io.InputStream;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;
import android.os.Handler;
import android.os.Looper;

/** All UI code authored for NAJM Tube; no original SmartTube screens or navigation. */
public final class HomeActivity extends Activity {
    private static final int BG=0xFF111111, PANEL=0xFF222222, MUTED=0xFFAAAAAA, GOLD=0xFFFFC947;
    private final Handler ui=new Handler(Looper.getMainLooper());
    private final ExecutorService imageThreads=Executors.newFixedThreadPool(2);
    private final LruCache<String, Bitmap> images=new LruCache<String,Bitmap>(12*1024*1024){
        @Override protected int sizeOf(String k,Bitmap b){return b.getByteCount();}
    };
    private final AtomicInteger queryVersion=new AtomicInteger();
    private EditText search;
    private LinearLayout cards;
    private TextView status;
    private ProgressBar loading;
    private String currentQuery="سيارات";
    private boolean destroyed=false;
    private int columns=2;

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().setStatusBarColor(Color.BLACK);
        getWindow().setNavigationBarColor(Color.BLACK);
        getWindow().getDecorView().setSystemUiVisibility(0);
        columns=getResources().getConfiguration().orientation==Configuration.ORIENTATION_LANDSCAPE?3:2;
        int screenDp=getResources().getConfiguration().screenWidthDp;
        if (screenDp<440) columns=1;
        createUi();
        runSearch(currentQuery);
    }

    private void createUi(){
        LinearLayout root=new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);
        root.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        LinearLayout top=new LinearLayout(this);
        top.setPadding(dp(14),dp(8),dp(14),dp(7));
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setBackgroundColor(0xFF191919);
        ImageView icon=new ImageView(this);
        icon.setImageResource(com.najm.tubenew.R.drawable.najm_icon);
        icon.setScaleType(ImageView.ScaleType.FIT_CENTER);
        top.addView(icon,new LinearLayout.LayoutParams(dp(50),dp(50)));
        TextView title=new TextView(this);
        title.setText("نجم تيوب");
        title.setTextColor(GOLD);
        title.setTextSize(22f);
        title.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        title.setPadding(dp(8),0,dp(12),0);
        top.addView(title);
        root.addView(top);

        LinearLayout searchBar=new LinearLayout(this);
        searchBar.setPadding(dp(12),dp(7),dp(12),dp(7));
        searchBar.setGravity(Gravity.CENTER_VERTICAL);
        searchBar.setOrientation(LinearLayout.HORIZONTAL);
        search=new EditText(this);
        search.setHint("ابحث عن الفيديوهات...");
        search.setHintTextColor(MUTED);
        search.setTextColor(Color.WHITE);
        search.setTextSize(17);
        search.setSingleLine(true);
        search.setPadding(dp(12),0,dp(12),0);
        search.setBackground(rounded(PANEL,14));
        search.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
        search.setOnEditorActionListener((v,action,event)->{
            if(action==EditorInfo.IME_ACTION_SEARCH){submitSearch();return true;}
            return false;
        });
        searchBar.addView(search,new LinearLayout.LayoutParams(0,dp(50),1));
        Button go=btn("بحث",0xFFC01822);
        go.setOnClickListener(v->submitSearch());
        LinearLayout.LayoutParams gp=new LinearLayout.LayoutParams(dp(86),dp(50));gp.setMargins(dp(7),0,0,0);
        searchBar.addView(go,gp);
        root.addView(searchBar);

        HorizontalScrollView categoryScroll=new HorizontalScrollView(this);
        categoryScroll.setHorizontalScrollBarEnabled(false);
        LinearLayout chips=new LinearLayout(this);
        chips.setPadding(dp(12),dp(2),dp(12),dp(9));
        chips.setOrientation(LinearLayout.HORIZONTAL);
        String[] cats={"الرئيسية","سيارات","تقنية","القرآن الكريم","أفلام وثائقية","رياضة","أخبار"};
        String[] q={"سيارات","سيارات","تقنية","قرآن كريم","وثائقي","ملخص مباريات","أخبار اليوم"};
        for(int i=0;i<cats.length;i++){
            final String keyword=q[i];
            Button b=btn(cats[i],i==0?0xFF7A4912:PANEL);
            LinearLayout.LayoutParams bp=new LinearLayout.LayoutParams(-2,dp(42));
            bp.setMargins(dp(4),0,dp(4),0);
            chips.addView(b,bp);
            b.setOnClickListener(v->{search.setText("");runSearch(keyword);});
        }
        categoryScroll.addView(chips);
        root.addView(categoryScroll);
        LinearLayout line=new LinearLayout(this);
        line.setGravity(Gravity.CENTER_VERTICAL);
        status=new TextView(this);
        status.setText("جاري جلب الفيديوهات...");
        status.setTextColor(Color.WHITE);
        status.setTextSize(14f);
        status.setPadding(dp(18),dp(6),dp(12),dp(7));
        line.addView(status,new LinearLayout.LayoutParams(0,dp(39),1));
        loading=new ProgressBar(this,null,android.R.attr.progressBarStyleSmall);
        line.addView(loading,new LinearLayout.LayoutParams(dp(34),dp(34)));
        root.addView(line);
        ScrollView scroll=new ScrollView(this);
        scroll.setFillViewport(true);
        cards=new LinearLayout(this);
        cards.setPadding(dp(9),dp(7),dp(9),dp(32));
        cards.setOrientation(LinearLayout.VERTICAL);
        scroll.addView(cards);
        root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        setContentView(root);
    }
    private void submitSearch(){
        String q=search.getText().toString().trim();
        if(q.isEmpty())return;
        InputMethodManager manager=(InputMethodManager)getSystemService(INPUT_METHOD_SERVICE);
        if(manager!=null)manager.hideSoftInputFromWindow(search.getWindowToken(),0);
        search.clearFocus();
        runSearch(q);
    }
    private void runSearch(String q){
        currentQuery=q;
        int requestId=queryVersion.incrementAndGet();
        status.setText("جاري البحث عن: "+q);
        loading.setVisibility(View.VISIBLE);
        cards.removeAllViews();
        YoutubeData.IO.execute(()->{
            try{
                List<StreamInfoItem> items=YoutubeData.search(q);
                ui.post(()->{
                    if(destroyed||queryVersion.get()!=requestId)return;
                    loading.setVisibility(View.GONE);
                    status.setText(items.isEmpty()?"لا توجد نتائج. جرّب كلمة أخرى":"الفيديوهات — "+items.size()+" نتيجة");
                    displayResults(items);
                });
            }catch(Exception e){
                String why=e.getMessage()==null?e.getClass().getSimpleName():e.getMessage();
                ui.post(()->{
                    if(destroyed||queryVersion.get()!=requestId)return;
                    loading.setVisibility(View.GONE);
                    status.setText("تعذر جلب الفيديوهات. تحقق من الإنترنت.");
                    TextView problem=new TextView(this);
                    problem.setText("تعذر الاتصال بمحرك البحث: "+why);
                    problem.setTextColor(0xFFFFB5B5);
                    problem.setTextSize(15);
                    problem.setPadding(dp(12),dp(15),dp(12),dp(15));
                    cards.addView(problem);
                    Button retry=btn("إعادة المحاولة",0xFFAE2020);
                    retry.setOnClickListener(v->runSearch(currentQuery));
                    cards.addView(retry,new LinearLayout.LayoutParams(-1,dp(49)));
                });
            }
        });
    }
    private void displayResults(List<StreamInfoItem> list){
        LinearLayout row=null;
        for(int i=0;i<list.size();i++){
            if(i%columns==0){
                row=new LinearLayout(this);
                row.setOrientation(LinearLayout.HORIZONTAL);
                cards.addView(row,new LinearLayout.LayoutParams(-1,-2));
            }
            final StreamInfoItem video=list.get(i);
            LinearLayout card=new LinearLayout(this);
            card.setOrientation(LinearLayout.VERTICAL);
            card.setPadding(dp(5),dp(6),dp(5),dp(12));
            card.setFocusable(true);
            card.setClickable(true);
            LinearLayout.LayoutParams cp=new LinearLayout.LayoutParams(0,-2,1);
            row.addView(card,cp);

            FrameLayout picture=new FrameLayout(this);
            picture.setBackground(rounded(0xFF242424,12));
            ImageView preview=new ImageView(this);
            preview.setScaleType(ImageView.ScaleType.CENTER_CROP);
            picture.addView(preview,new FrameLayout.LayoutParams(-1,-1));
            card.addView(picture,new LinearLayout.LayoutParams(-1,dp(columns==1?195:columns==2?130:110)));
            String url=null;
            if(video.getThumbnails()!=null&&!video.getThumbnails().isEmpty()){
                List<Image> thumbs=video.getThumbnails();
                url=thumbs.get(thumbs.size()/2).getUrl();
            }
            if(url!=null)loadPreview(preview,url);
            TextView name=new TextView(this);
            name.setText(video.getName());
            name.setTextColor(Color.WHITE);
            name.setTextSize(15);
            name.setMaxLines(2);
            name.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
            name.setPadding(dp(3),dp(8),dp(3),dp(3));
            card.addView(name);
            TextView sub=new TextView(this);
            String channel=video.getUploaderName();
            sub.setText((channel==null?"فيديو":channel) + duration(video.getDuration()));
            sub.setTextColor(MUTED);
            sub.setTextSize(12);
            sub.setMaxLines(1);
            card.addView(sub);
            card.setOnClickListener(v->{
                Intent intent=new Intent(this,VideoActivity.class);
                intent.putExtra("url",video.getUrl());
                intent.putExtra("title",video.getName());
                startActivity(intent);
            });
        }
    }
    private String duration(long seconds) {
        if(seconds<=0)return "";
        return "  •  "+String.format(Locale.US,"%d:%02d",seconds/60,seconds%60);
    }
    private void loadPreview(ImageView view,String link){
        Bitmap existing=images.get(link);
        if(existing!=null){view.setImageBitmap(existing);return;}
        view.setTag(link);
        imageThreads.execute(()->{
            try{
                java.net.HttpURLConnection conn=(java.net.HttpURLConnection)new URL(link).openConnection();
                conn.setConnectTimeout(8000);conn.setReadTimeout(9000);
                try(InputStream in=conn.getInputStream()){
                    BitmapFactory.Options opts=new BitmapFactory.Options();
                    opts.inSampleSize=2;
                    Bitmap bmp=BitmapFactory.decodeStream(in,null,opts);
                    if(bmp==null)return;
                    synchronized(images){images.put(link,bmp);}
                    ui.post(()->{if(!destroyed&&link.equals(view.getTag()))view.setImageBitmap(bmp);});
                }finally{conn.disconnect();}
            }catch(Exception ignored){}
        });
    }
    private GradientDrawable rounded(int color,int radius){
        GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(radius));return d;
    }
    private Button btn(String label,int color){
        Button b=new Button(this);
        b.setText(label);b.setAllCaps(false);b.setTextSize(14);
        b.setTextColor(Color.WHITE);b.setBackground(rounded(color,10));
        return b;
    }
    private int dp(int i){return (int)(getResources().getDisplayMetrics().density*i+0.5f);}
    @Override public void onBackPressed(){
        if(search.hasFocus()){search.clearFocus();return;}
        super.onBackPressed();
    }
    @Override protected void onDestroy(){destroyed=true;queryVersion.incrementAndGet();imageThreads.shutdownNow();super.onDestroy();}
}
