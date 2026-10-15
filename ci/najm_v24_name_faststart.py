#!/usr/bin/env python3
"""NAJM Tube V2.4: user-requested Arabic launcher name + tunable safe video startup."""
from pathlib import Path
import xml.etree.ElementTree as ET

base=Path("SmartTube")
src=base/"smarttubetv/src"
common=base/"common/src/main/java/com/liskovsoft/smartyoutubetv2/common"

# Flavor resources override main. Fix the actual Android Beta launcher label.
for relative in (
    "main/res/values/strings.xml",
    "stbeta/res/values/strings.xml",
    "ststable/res/values/strings.xml",
):
    path=src/relative
    s=path.read_text()
    import re
    for key in ("app_name", "browse_title"):
        pattern=r'(<string\s+translatable="false"\s+name="'+key+r'">).*?(</string>)'
        s,n=re.subn(pattern,lambda m:m.group(1)+"<![CDATA[نجم تيوب]]>"+m.group(2),
                    s,count=1,flags=re.S)
        assert n==1,(relative,key)
    ET.fromstring(s)
    path.write_text(s)

# All alternate launcher icons/aliases use our branded logo too.
manifest=src/"main/AndroidManifest.xml"
m=manifest.read_text()
if 'android:icon="@mipmap/app_icon_alt"' in m:
    m=m.replace('android:icon="@mipmap/app_icon_alt"',
                'android:icon="@mipmap/najm_tube_icon"')
manifest.write_text(m)

# Keep user preferred playback buffer type; tune only startup condition.
init=common/"exoplayer/other/ExoPlayerInitializer.java"
s=init.read_text()
needle='''    private final PlayerData mPlayerData;'''
assert s.count(needle)==1
s=s.replace(needle,needle+'''
    private final Context mNajmContext;''',1)
needle='''        mPlayerData = PlayerData.instance(context);'''
assert s.count(needle)==1
s=s.replace(needle,'''        mNajmContext = context.getApplicationContext();
'''+needle,1)
needle='''        baseBuilder
                .setBufferDurationsMs(minBufferMs, maxBufferMs, bufferForPlaybackMs, bufferForPlaybackAfterRebufferMs);'''
assert s.count(needle)==1
s=s.replace(needle,'''        // Fast-start can be switched off in NAJM Tube settings if a slow
        // connection requires additional startup buffering.
        // Do not override explicit high-buffer modes or shorten rebuffer time.
        boolean najmFastStart = mNajmContext.getSharedPreferences(
                "najm_tube_player_preferences", Context.MODE_PRIVATE)
                .getBoolean("fast_start", true);
        if (najmFastStart && mPlayerData.getVideoBufferType() == PlayerData.BUFFER_MEDIUM) {
            bufferForPlaybackMs = 1_200;
        }
'''+needle,1)
init.write_text(s)

# Source-preparation to ready diagnostics, using monotonic time.
controller=common/"exoplayer/controller/ExoPlayerController.java"
s=controller.read_text()
needle='''    private boolean mOnSourceChanged;'''
assert s.count(needle)==1
s=s.replace(needle,needle+'''
    private long mNajmSourceStartMs = -1;''',1)
needle='''        mPlayer.prepare(mediaSource);'''
assert s.count(needle)==1
s=s.replace(needle,'''        mNajmSourceStartMs = android.os.SystemClock.elapsedRealtime();
'''+needle,1)
needle='''        boolean isPlayPressed = Player.STATE_READY == playbackState && playWhenReady;'''
assert s.count(needle)==1
s=s.replace(needle,'''        if (playbackState == Player.STATE_READY && mNajmSourceStartMs > 0) {
            long elapsed = android.os.SystemClock.elapsedRealtime() - mNajmSourceStartMs;
            Log.d(TAG, "NAJM video source ready after " + elapsed + " ms");
            mNajmSourceStartMs = -1;
        }
'''+needle,1)
controller.write_text(s)

# Expose a plain Arabic UI switch. Changing it affects new video player loads.
activity=src/"main/java/com/liskovsoft/smartyoutubetv2/tv/ui/playback/PlaybackActivity.java"
s=activity.read_text()
needle='''                          "إظهار خط التقدم الأحمر عند اختفاء الأزرار"
                  };'''
assert s.count(needle)==1
s=s.replace(needle,'''                          "إظهار خط التقدم الأحمر عند اختفاء الأزرار",
                      getSharedPreferences("najm_tube_player_preferences", MODE_PRIVATE)
                          .getBoolean("fast_start", true) ?
                          "بدء الفيديو السريع: تشغيل (اضغط للإيقاف)" :
                          "بدء الفيديو السريع: إيقاف (اضغط للتشغيل)"
                  };''',1)
needle='''                          if (which==0) chooseNajmAutoHide();
                          else {'''
assert s.count(needle)==1
s=s.replace(needle,'''                          if (which==0) chooseNajmAutoHide();
                          else if (which==2) {
                              android.content.SharedPreferences prefs =
                                  getSharedPreferences("najm_tube_player_preferences", MODE_PRIVATE);
                              prefs.edit().putBoolean("fast_start",
                                  !prefs.getBoolean("fast_start",true)).apply();
                              new android.app.AlertDialog.Builder(this)
                                  .setMessage("يُطبّق وضع بدء الفيديو على الفيديو التالي. عند ضعف الإنترنت أوقف الوضع السريع.")
                                  .setPositiveButton("موافق", (d, w) -> showNajmQuickSettings())
                                  .show();
                          } else {''',1)
activity.write_text(s)

print("NAJM V2.4: launcher name نجم تيوب in all flavors, fast start switch, low-risk source READY logs.")
