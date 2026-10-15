package com.najm.tubenew;

import android.util.Log;
import org.json.JSONArray;
import org.json.JSONObject;
import org.schabi.newpipe.extractor.Image;
import org.schabi.newpipe.extractor.stream.StreamInfoItem;
import org.schabi.newpipe.extractor.stream.StreamType;

import java.io.IOException;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.concurrent.TimeUnit;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

/**
 * Independent search fallback when Youtube changes its internal Search API
 * response or the NewPipeExtractor parser returns zero entries.
 * It reads publicly served desktop search pages, never a user's cookies/account.
 * No SmartTube UI or source code is copied.
 */
public final class YoutubeSearchFallback {
    private static final String TAG="NajmSearchFallback";
    private static final int MAX_RESULTS=32;
    private static final String DESKTOP_UA=
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 " +
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";
    private static final OkHttpClient CLIENT=new OkHttpClient.Builder()
            .connectTimeout(10,TimeUnit.SECONDS)
            .readTimeout(16,TimeUnit.SECONDS)
            .followRedirects(true).build();

    private YoutubeSearchFallback() {}

    public static List<StreamInfoItem> search(String query) throws Exception {
        String address="https://www.youtube.com/results?search_query=" +
                URLEncoder.encode(query,"UTF-8") + "&hl=ar&gl=SA";
        Request request=new Request.Builder().url(address)
                .header("User-Agent", DESKTOP_UA)
                .header("Accept-Language", "ar-SA,ar;q=0.9,en;q=0.7")
                .header("Accept", "text/html,application/xhtml+xml")
                .build();
        String html;
        try(Response response=CLIENT.newCall(request).execute()){
            if(!response.isSuccessful()) throw new IOException("YouTube HTTP "+response.code());
            if(response.body()==null)throw new IOException("YouTube returned empty response");
            html=response.body().string();
        }
        String data=findInitialJson(html);
        if(data==null)throw new IOException("YouTube search data unavailable");
        LinkedHashMap<String,StreamInfoItem> collected=new LinkedHashMap<>();
        scan(new JSONObject(data),collected,0);
        Log.d(TAG,"HTML search results: "+collected.size());
        return new ArrayList<>(collected.values());
    }

    static String findInitialJson(String html){
        int start=html.indexOf("ytInitialData =");
        if(start<0)start=html.indexOf("ytInitialData=");
        if(start<0)return null;
        start=html.indexOf('{',start);
        if(start<0)return null;
        boolean inString=false,escape=false;
        int depth=0;
        for(int i=start;i<html.length();i++){
            char c=html.charAt(i);
            if(inString){
                if(escape)escape=false;
                else if(c=='\\')escape=true;
                else if(c=='"')inString=false;
            }else if(c=='"')inString=true;
            else if(c=='{')depth++;
            else if(c=='}'){
                if(--depth==0)return html.substring(start,i+1);
            }
        }
        return null;
    }

    private static void scan(Object node,LinkedHashMap<String,StreamInfoItem> out,int depth) {
        if(node==null||depth>32||out.size()>=MAX_RESULTS)return;
        if(node instanceof JSONArray){
            JSONArray array=(JSONArray)node;
            for(int i=0;i<array.length()&&out.size()<MAX_RESULTS;i++)
                scan(array.opt(i),out,depth+1);
        }else if(node instanceof JSONObject){
            JSONObject obj=(JSONObject)node;
            JSONObject video=obj.optJSONObject("videoRenderer");
            if(video!=null)add(video,out);
            Iterator<String> keys=obj.keys();
            while(keys.hasNext()&&out.size()<MAX_RESULTS){
                String key=keys.next();
                if("videoRenderer".equals(key))continue;
                Object sub=obj.opt(key);
                if(sub instanceof JSONArray||sub instanceof JSONObject)scan(sub,out,depth+1);
            }
        }
    }

    private static void add(JSONObject v,LinkedHashMap<String,StreamInfoItem> out){
        String id=v.optString("videoId","");
        if(!id.matches("[A-Za-z0-9_-]{11}")||out.containsKey(id))return;
        String title=label(v.optJSONObject("title"));
        if(title.isEmpty())return;
        String url="https://www.youtube.com/watch?v="+id;
        StreamInfoItem item=new StreamInfoItem(0,url,title,StreamType.VIDEO_STREAM);
        String owner=label(v.optJSONObject("ownerText"));
        if(owner.isEmpty())owner=label(v.optJSONObject("longBylineText"));
        item.setUploaderName(owner);
        item.setDuration(parseDuration(label(v.optJSONObject("lengthText"))));
        item.setThumbnails(Collections.singletonList(
                new Image("https://i.ytimg.com/vi/"+id+"/hqdefault.jpg",
                        360,480, Image.ResolutionLevel.MEDIUM)));
        out.put(id,item);
    }

    private static String label(JSONObject object){
        if(object==null)return "";
        String simple=object.optString("simpleText","");
        if(!simple.isEmpty())return simple;
        JSONArray runs=object.optJSONArray("runs");
        if(runs!=null&&runs.length()>0){
            JSONObject first=runs.optJSONObject(0);
            if(first!=null)return first.optString("text","");
        }
        return "";
    }

    private static long parseDuration(String s){
        if(s==null||s.length()>12)return -1L;
        String[] parts=s.trim().split(":");
        if(parts.length<2||parts.length>3)return -1L;
        long total=0;
        try{
            for(String p:parts)total=total*60+Long.parseLong(p.trim());
            return total;
        }catch(Exception e){return -1L;}
    }
}
