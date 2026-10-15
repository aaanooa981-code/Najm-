package com.najm.tubenew;

import org.schabi.newpipe.extractor.NewPipe;
import org.schabi.newpipe.extractor.ServiceList;
import org.schabi.newpipe.extractor.InfoItem;
import org.schabi.newpipe.extractor.search.SearchInfo;
import org.schabi.newpipe.extractor.stream.StreamInfo;
import org.schabi.newpipe.extractor.stream.StreamInfoItem;
import org.schabi.newpipe.extractor.downloader.Downloader;
import org.schabi.newpipe.extractor.downloader.Request;
import org.schabi.newpipe.extractor.downloader.Response;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.RequestBody;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import javax.annotation.Nonnull;

/** Network search + extraction are isolated from the UI/player. No SmartTube UI code is reused. */
public final class YoutubeData {
    public static final ExecutorService IO = Executors.newFixedThreadPool(3);
    private static final OkHttpClient HTTP = new OkHttpClient.Builder()
        .connectTimeout(12, TimeUnit.SECONDS)
        .readTimeout(18, TimeUnit.SECONDS)
        .followRedirects(true)
        .build();
    private static volatile boolean initialized;

    private YoutubeData() {}

    public static synchronized void initialize() {
        if (initialized) return;
        NewPipe.init(new Downloader() {
            @Override
            public Response execute(@Nonnull Request request) throws IOException {
                okhttp3.Request.Builder builder = new okhttp3.Request.Builder().url(request.url());
                builder.header("User-Agent", "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36");
                final Map<String,List<String>> headers = request.headers();
                if (headers != null) {
                    for (Map.Entry<String,List<String>> entry : headers.entrySet()) {
                        if (entry.getValue()!=null)
                            for (String value : entry.getValue()) {
                                if (value != null) builder.addHeader(entry.getKey(), value);
                            }
                    }
                }
                String method=request.httpMethod();
                byte[] data=request.dataToSend();
                if ("HEAD".equalsIgnoreCase(method)) {
                    builder.head();
                } else if ("POST".equalsIgnoreCase(method) || "PUT".equalsIgnoreCase(method)) {
                    MediaType type = MediaType.parse("application/json; charset=utf-8");
                    builder.method(method, RequestBody.create(type, data==null?new byte[0]:data));
                } else {
                    builder.get();
                }
                try (okhttp3.Response result = HTTP.newCall(builder.build()).execute()) {
                    String body = result.body()!=null ? result.body().string() : "";
                    return new Response(result.code(), result.message(), result.headers().toMultimap(),
                        body, result.request().url().toString());
                }
            }
        });
        initialized=true;
    }

    public static List<StreamInfoItem> search(String query) throws Exception {
        initialize();
        SearchInfo results=SearchInfo.getInfo(ServiceList.YouTube.getSearchExtractor(query));
        List<StreamInfoItem> videos=new ArrayList<>();
        for (InfoItem item : results.getRelatedItems()) {
            if (item instanceof StreamInfoItem) videos.add((StreamInfoItem)item);
            if (videos.size() >= 36) break;
        }
        return videos;
    }
    public static StreamInfo video(String url) throws Exception {
        initialize();
        return StreamInfo.getInfo(ServiceList.YouTube, url);
    }
}
