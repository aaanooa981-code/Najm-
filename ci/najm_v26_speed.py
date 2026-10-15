#!/usr/bin/env python3
"""NAJM Tube V2.6: fast thumbnail revisit, opt-in motion previews, avoid wasted card animation."""
from pathlib import Path

ROOT=Path("SmartTube")
MAIN=ROOT/"smarttubetv/src/main"
JAVA=MAIN/"java/com/liskovsoft/smartyoutubetv2/tv"

def once(src, before, after, what):
    n=src.count(before)
    if n!=1: raise RuntimeError(f"{what}: expected one matching anchor, found {n}")
    return src.replace(before,after,1)

cards=JAVA/"presenter/VideoCardPresenter.java"
s=cards.read_text()
# Upstream ViewUtil.glideOptions() deliberately disables decoded image memory
# cache (intended for animated images). It is a poor default for static
# thumbnails. Restore memory cache only for modern Android devices; keep old
# API21 behavior to avoid regressions on fragile TV ROMs.
needle='''.apply(ViewUtil.glideOptions())
                .dontAnimate()'''
s=once(s,needle,'''.apply(ViewUtil.glideOptions())
                .skipMemoryCache(VERSION.SDK_INT <= 21)
                .dontAnimate()''',"static thumbnail in-memory cache")
# The error thumbnail request also disables memory cache in ViewUtil options.
needle='''.load(video.cardImageUrl) // always working
                        //.placeholder(mDefaultCardImage)
                        .apply(ViewUtil.glideOptions())'''
s=once(s,needle,'''.load(video.cardImageUrl) // always working
                        //.placeholder(mDefaultCardImage)
                        .apply(ViewUtil.glideOptions())
                        .skipMemoryCache(VERSION.SDK_INT <= 21)
                        .dontAnimate()''',"fallback thumbnail in-memory cache")

# A row of autoplay video previews competes with the video actually selected
# by the user. Default them to OFF on car screens; opt-in can be restored in
# NAJM player settings, but low-memory devices continue to disable them.
needle='''        return MainUIData.instance(context).getCardPreviewType();
    }'''
s=once(s,needle,'''        boolean allowMovingPreviews = context.getSharedPreferences(
                "najm_tube_player_preferences", Context.MODE_PRIVATE)
                .getBoolean("moving_previews", false);
        if (!allowMovingPreviews) {
            return MainUIData.CARD_PREVIEW_DISABLED;
        }
        return MainUIData.instance(context).getCardPreviewType();
    }''',"auto-preview fast mode default")
cards.write_text(s)

act=JAVA/"ui/playback/PlaybackActivity.java"
s=act.read_text()
old='''                          "بدء الفيديو السريع: إيقاف (اضغط للتشغيل)"
                  };'''
new='''                          "بدء الفيديو السريع: إيقاف (اضغط للتشغيل)",
                      getSharedPreferences("najm_tube_player_preferences", MODE_PRIVATE)
                          .getBoolean("moving_previews", false) ?
                          "معاينات فيديو متحركة: تشغيل (قد تؤخر التطبيق)" :
                          "معاينات فيديو متحركة: إيقاف (الأسرع)"
                  };'''
s=once(s,old,new,"fast mode preview setting label")
old='''                          } else {
                              mNajmShowSmallProgress = !mNajmShowSmallProgress;'''
new='''                          } else if (which == 3) {
                              android.content.SharedPreferences prefs =
                                  getSharedPreferences("najm_tube_player_preferences", MODE_PRIVATE);
                              prefs.edit().putBoolean("moving_previews",
                                  !prefs.getBoolean("moving_previews", false)).apply();
                              new android.app.AlertDialog.Builder(this)
                                  .setMessage("تغيير معاينات الفيديو يطبّق عند إعادة فتح نجم تيوب. إيقاف المعاينات يجعل التصفح أخف.")
                                  .setPositiveButton("موافق", (d,w) -> showNajmQuickSettings())
                                  .show();
                          } else {
                              mNajmShowSmallProgress = !mNajmShowSmallProgress;'''
s=once(s,old,new,"moving video previews toggle")
act.write_text(s)

print("V2.6: Glide still-image memory cache on Android 5.1+, previews opt-in with UI toggle.")
