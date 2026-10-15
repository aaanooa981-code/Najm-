package com.najm.tubenew;

import org.schabi.newpipe.extractor.NewPipe;
import org.schabi.newpipe.extractor.ServiceList;
import org.schabi.newpipe.extractor.InfoItem;
import org.schabi.newpipe.extractor.Image;
import org.schabi.newpipe.extractor.search.SearchInfo;
import org.schabi.newpipe.extractor.stream.StreamInfo;
import org.schabi.newpipe.extractor.stream.StreamInfoItem;
import org.schabi.newpipe.extractor.downloader.Downloader;
import org.schabi.newpipe.extractor.downloader.Request;
import org.schabi.newpipe.extractor.downloader.Response;

import android.text.TextUtils;
import android.util.Log;
import org.json.JSONArray;
import org.json.JSONObject;

import okhttp3.OkHttpClient;
import okhttp3.RequestBody;
import okhttp3.MediaType;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.LinkedHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/** NAJM Tube own search surface; ExoPlayer and NewPipeExtractor remain separate reusable libraries. */
public final class YoutubeData {
    public static final ExecutorService IO = Executors.newFixedThreadPool(3);
    public static final class VideoResult {
        public final String name, url, uploader, thumbnail, duration;
        VideoResult(String name, String url, String uploader, String thumbnail, String duration) {
            this.name=name;this.url=url;this.uploader=uploader;this.thumbnail=thumbnail;this.duration=duration;
        }
    }
    private static final String UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";
    private static final OkHttpClient HTTP = new OkHttpClient.Builder()
        .connectTimeout(12, TimeUnit.SECONDS)
        .readTimeout(18, TimeUnit.SECONDS)
        .followRedirects(true).build();
    private static volatile boolean initialized;
    private YoutubeData() {}

    public static synchronized void initialize() {
        if(initialized)return;
        NewPipe.init(new Downloader() {
            @Override public Response execute(Request request) throws IOException {
                okhttp3.Request.Builder rb=new okhttp3.Request.Builder().url(request.url());
                rb.header("User-Agent", UA);
                final Map<String,List<String>> headers=request.headers();
                if(headers!=null) {
                    for(Map.Entry<String,List<String>> e : headers.entrySet()) {
                        if(e.getValue()!=null)for(String value:e.getValue()) {
                            if(value!=null)rb.addHeader(e.getKey(),value);
                        }
                    }
                }
                String method=request.httpMethod();
                byte[] body=request.dataToSend();
                if("HEAD".equalsIgnoreCase(method))rb.head();
                else if("POST".equalsIgnoreCase(method)||"PUT".equalsIgnoreCase(method)) {
                    rb.method(method, RequestBody.create(MediaType.parse("application/json; charset=utf-8"),body==null?new byte[0]:body));
                }else rb.get();
                try(okhttp3.Response r=HTTP.newCall(rb.build()).execute()) {
                    return new Response(r.code(),r.message(),r.headers().toMultimap(),
                        r.body()==null?"":r.body().string(),r.request().url().toString());
                }
            }
        });
        initialized=true;
    }

    public static List<VideoResult> search(String text) throws Exception {
        String q=text==null?"":text.trim();
        if(q.isEmpty())throw new IllegalArgumentException("اكتب كلمة للبحث");
        Exception htmlFailure=null, extractorFailure=null;
        try {
            List<VideoResult> page=searchYoutubeWeb(q);
            if(!page.isEmpty())return page;
            htmlFailure=new IOException("يوتيوب أعاد صفحة دون فيديوهات");
        }catch(Exception e) { htmlFailure=e;Log.w("NAJM_SEARCH","Web search fallback",e); }
        try {
            List<VideoResult> page=searchExtractor(q);
            if(!page.isEmpty())return page;
            extractorFailure=new IOException("المصدر الثاني أعاد نتائج فارغة");
        }catch(Exception e) {extractorFailure=e;Log.w("NAJM_SEARCH","Extractor fallback",e);}
        String reason=shortError(htmlFailure);
        if(extractorFailure!=null)reason+=" | "+shortError(extractorFailure);
        throw new IOException("لم يستطع محرك البحث تحميل نتائج يوتيوب: "+reason);
    }

    private static String shortError(Exception e) {
        if(e==null)return "غير معروف";
        String message=e.getMessage();
        if(message==null || message.length()==0)return e.getClass().getSimpleName();
        // Do not display full HTML, URLs, cookies or server response bodies.
        return message.length()>90?message.substring(0,90):message;
    }

    private static List<VideoResult> searchExtractor(String query) throws Exception {
        initialize();
        SearchInfo results=SearchInfo.getInfo(ServiceList.YouTube.getSearchExtractor(query));
        List<VideoResult> out=new ArrayList<>();
        for(InfoItem item:results.getRelatedItems()) {
            if(!(item instanceof StreamInfoItem))continue;
            StreamInfoItem v=(StreamInfoItem)item;
            String img="";
            List<Image> thumbs=v.getThumbnails();
            if(thumbs!=null && !thumbs.isEmpty())img=thumbs.get(thumbs.size()-1).getUrl();
            out.add(new VideoResult(v.getName(),v.getUrl(),v.getUploaderName(),img,formatDuration(v.getDuration())));
            if(out.size()>=30)break;
        }
        // NewPipeExtractor can silently turn a parser exception into an empty result list.
        if(out.isEmpty() && !results.getErrors().isEmpty()) {
            Throwable e=results.getErrors().get(0);
            throw new IOException("تعذر تفسير نتائج يوتيوب ("+e.getClass().getSimpleName()+")",e);
        }
        return out;
    }

    private static List<VideoResult> searchYoutubeWeb(String query) throws Exception {
        String url="https://www.youtube.com/results?search_query="+java.net.URLEncoder.encode(query,"UTF-8")+"&hl=ar&gl=SA";
        okhttp3.Request req=new okhttp3.Request.Builder().url(url)
            .header("User-Agent", UA).header("Accept-Language","ar-SA,ar;q=0.9,en;q=0.7")
            .header("Accept","text/html").build();
        String html;
        try(okhttp3.Response resp=HTTP.newCall(req).execute()){
            if(!resp.isSuccessful())throw new IOException("رد يوتيوب HTTP "+resp.code());
            if(resp.body()==null)throw new IOException("صفحة يوتيوب فارغة");
            html=resp.body().string();
        }
        String json=extractInitialData(html);
        JSONObject data=new JSONObject(json);
        JSONObject contents=data.optJSONObject("contents");
        JSONObject renderer=contents==null?null:contents.optJSONObject("twoColumnSearchResultsRenderer");
        JSONObject primary=renderer==null?null:renderer.optJSONObject("primaryContents");
        JSONObject sections=primary==null?null:primary.optJSONObject("sectionListRenderer");
        JSONArray entries=sections==null?null:sections.optJSONArray("contents");
        if(entries==null)throw new IOException("تغير تنسيق صفحة نتائج يوتيوب");
        LinkedHashMap<String,VideoResult> out=new LinkedHashMap<>();
        for(int i=0;i<entries.length();i++){
            JSONObject row=entries.optJSONObject(i);
            JSONObject section=row==null?null:row.optJSONObject("itemSectionRenderer");
            JSONArray results=section==null?null:section.optJSONArray("contents");
            if(results==null)continue;
            for(int j=0;j<results.length();j++){
                JSONObject item=results.optJSONObject(j);
                if(item==null)continue;
                VideoResult result=parseYoutubeItem(item);
                if(result!=null && !out.containsKey(result.url))out.put(result.url,result);
                if(out.size()>=30)return new ArrayList<>(out.values());
            }
        }
        return new ArrayList<>(out.values());
    }

    private static VideoResult parseYoutubeItem(JSONObject item){
        JSONObject v=item.optJSONObject("videoRenderer");
        if(v!=null){
            String id=v.optString("videoId","");
            if(!id.matches("[A-Za-z0-9_-]{11}"))return null;
            String name=getText(v.optJSONObject("title"));
            String channel=getText(v.optJSONObject("ownerText"));
            if(channel.isEmpty())channel=getText(v.optJSONObject("longBylineText"));
            String dur=getText(v.optJSONObject("lengthText"));
            if(name.isEmpty())return null;
            return new VideoResult(name,"https://www.youtube.com/watch?v="+id,
                channel,"https://i.ytimg.com/vi/"+id+"/mqdefault.jpg",dur);
        }
        // YouTube sometimes returns lockupViewModel instead of videoRenderer.
        JSONObject lock=item.optJSONObject("lockupViewModel");
        if(lock!=null && "LOCKUP_CONTENT_TYPE_VIDEO".equals(lock.optString("contentType"))){
            String id=lock.optString("contentId","");
            if(!id.matches("[A-Za-z0-9_-]{11}"))return null;
            JSONObject metadata=lock.optJSONObject("metadata");
            JSONObject mv=metadata==null?null:metadata.optJSONObject("lockupMetadataViewModel");
            JSONObject title=mv==null?null:mv.optJSONObject("title");
            String name=title==null?"":title.optString("content","");
            if(name.isEmpty())return null;
            JSONObject thumbnail=lock.optJSONObject("contentImage");
            String image="";
            if(thumbnail!=null){
                JSONObject t=thumbnail.optJSONObject("thumbnailViewModel");
                JSONObject img=t==null?null:t.optJSONObject("image");
                JSONArray sources=img==null?null:img.optJSONArray("sources");
                if(sources!=null&&sources.length()>0)image=sources.optJSONObject(0).optString("url","");
            }
            return new VideoResult(name,"https://www.youtube.com/watch?v="+id,"",image,"");
        }
        return null;
    }
    private static String previewFrom(JSONObject thumbnail) {
        JSONArray thumbs=thumbnail==null?null:thumbnail.optJSONArray("thumbnails");
        if(thumbs==null||thumbs.length()==0)return "";
        JSONObject item=thumbs.optJSONObject(thumbs.length()-1);
        return item==null?"":item.optString("url","");
    }
    private static String getText(JSONObject o){
        if(o==null)return "";
        String plain=o.optString("simpleText","");
        if(!plain.isEmpty())return plain;
        JSONArray runs=o.optJSONArray("runs");
        if(runs==null)return "";
        StringBuilder out=new StringBuilder();
        for(int i=0;i<runs.length();i++){
            JSONObject r=runs.optJSONObject(i);
            if(r!=null)out.append(r.optString("text",""));
        }
        return out.toString();
    }
    /** Extract a single balanced JSON object instead of depending on fragile semicolon matching. */
    private static String extractInitialData(String html) throws IOException {
        int marker=html.indexOf("var ytInitialData = ");
        if(marker<0)marker=html.indexOf("ytInitialData = ");
        if(marker<0)throw new IOException("يوتيوب لم يرسل بيانات البحث");
        int start=html.indexOf('{',marker);
        if(start<0)throw new IOException("لا توجد بيانات نتائج");
        int level=0;
        boolean inString=false,escaped=false;
        for(int i=start;i<html.length();i++){
            char c=html.charAt(i);
            if(inString){
                if(escaped)escaped=false;
                else if(c=='\\')escaped=true;
                else if(c=='"')inString=false;
            }else{
                if(c=='"')inString=true;
                else if(c=='{')level++;
                else if(c=='}'){
                    if(--level==0)return html.substring(start,i+1);
                }
            }
        }
        throw new IOException("تعذر قراءة بيانات نتائج يوتيوب");
    }
    private static String formatDuration(long sec){
        if(sec<=0)return "";
        return String.format(java.util.Locale.US,"%d:%02d",sec/60,sec%60);
    }
    public static StreamInfo video(String url) throws Exception {
        initialize();
        return StreamInfo.getInfo(ServiceList.YouTube,url);
    }
}
