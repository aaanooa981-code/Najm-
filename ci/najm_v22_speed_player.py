#!/usr/bin/env python3
"""NAJM Tube V2.2: center controls and conservative legacy-device startup tuning."""
from pathlib import Path

ROOT=Path("SmartTube/smarttubetv/src/main")
JAVA=ROOT/"java/com/liskovsoft/smartyoutubetv2/tv"
BASE=Path("SmartTube/common/src/main/java/com/liskovsoft/smartyoutubetv2/common")
layout=ROOT/"res/layout/fragment_playback.xml"

def one(s,old,new,label):
    n=s.count(old)
    if n!=1: raise AssertionError("%s: expected once; found %s"%(label,n))
    return s.replace(old,new,1)

s=layout.read_text()
import re
match=re.search(r'<LinearLayout android:layout_width="match_parent" android:layout_height="48dp"[^>]*>.*?</LinearLayout>',s,re.S)
assert match is not None, "Could not locate legacy bottom transport row"
begin,end=match.span()
oldrow=match.group(0)
for n in ("najm_player_toggle","najm_player_back10","najm_player_forward10",
          "najm_player_previous_video","najm_player_next_video","najm_player_time","najm_player_options"):
    assert oldrow.count(n)==1,n

center='''                  <LinearLayout android:id="@+id/najm_player_center"
                      android:layout_width="wrap_content" android:layout_height="82dp"
                      android:layout_gravity="center" android:gravity="center_vertical"
                      android:orientation="horizontal" android:clickable="false">
                      <TextView android:id="@+id/najm_player_previous_video"
                          style="@style/NajmTube.CenterControl"
                          android:layout_width="48dp" android:text="⏮"
                          android:contentDescription="الفيديو السابق"/>
                      <TextView android:id="@+id/najm_player_back10"
                          style="@style/NajmTube.CenterControl"
                          android:layout_width="68dp" android:text="↶10"
                          android:contentDescription="ترجيع 10 ثوان"/>
                      <TextView android:id="@+id/najm_player_toggle"
                          style="@style/NajmTube.CenterControl"
                          android:layout_width="82dp" android:text="Ⅱ"
                          android:textSize="31sp"
                          android:contentDescription="تشغيل أو إيقاف"/>
                      <TextView android:id="@+id/najm_player_forward10"
                          style="@style/NajmTube.CenterControl"
                          android:layout_width="68dp" android:text="10↷"
                          android:contentDescription="تقديم 10 ثوان"/>
                      <TextView android:id="@+id/najm_player_next_video"
                          style="@style/NajmTube.CenterControl"
                          android:layout_width="48dp" android:text="⏭"
                          android:contentDescription="الفيديو التالي"/>
                  </LinearLayout>
'''
newrow='''                  <LinearLayout android:layout_width="match_parent" android:layout_height="38dp"
                      android:orientation="horizontal" android:gravity="center_vertical">
                      <TextView android:id="@+id/najm_player_time"
                          android:layout_width="wrap_content" android:layout_height="match_parent"
                          android:gravity="center_vertical" android:text="00:00 / 00:00"
                          android:textSize="14sp" android:textColor="#FFFFFF"/>
                      <Space android:layout_width="0dp" android:layout_height="1dp"
                          android:layout_weight="1"/>
                      <TextView android:id="@+id/najm_player_options"
                          style="@style/NajmTube.PlayerControl"
                          android:layout_width="56dp" android:layout_height="44dp"
                          android:text="⚙" android:textSize="23sp"
                          android:contentDescription="إعدادات الفيديو"/>
                  </LinearLayout>
'''
s=s[:begin]+newrow+s[end:]
anchor='              <FrameLayout android:id="@+id/najm_player_controls"'
assert s.count(anchor)==1
# Put center control overlay INSIDE controls frame, but before bottom controls.
target='                  <LinearLayout android:id="@+id/najm_player_bottom"'
s=one(s,target,center+target,"add center panel")
layout.write_text(s)

style=ROOT/"res/values/najm_center_controls.xml"
style.write_text('''<resources>
    <style name="NajmTube.CenterControl" parent="@android:style/Widget.TextView">
        <item name="android:layout_height">74dp</item>
        <item name="android:gravity">center</item>
        <item name="android:textColor">#FFFFFF</item>
        <item name="android:textSize">23sp</item>
        <item name="android:fontFamily">sans</item>
        <item name="android:clickable">true</item>
        <item name="android:focusable">true</item>
        <item name="android:background">@drawable/najm_center_button</item>
    </style>
</resources>
''')
(ROOT/"res/drawable/najm_center_button.xml").write_text('''<selector xmlns:android="http://schemas.android.com/apk/res/android">
  <item android:state_pressed="true">
    <shape android:shape="oval"><solid android:color="#99505050"/></shape>
  </item>
  <item>
    <shape android:shape="oval"><solid android:color="#5A141414"/></shape>
  </item>
</selector>
''')

# Prevent GestureDetector interpreting rapid presses on center controls
# as 'double-tap to seek'. These should be regular single-tap clicks.
player=JAVA/"ui/playback/PlaybackActivity.java"
p=player.read_text()
old='''android.view.View bottom = findViewById(R.id.najm_player_bottom);
                      mNajmTouchOnBottomControls = mNajmControls != null
                          && mNajmControls.getVisibility() == View.VISIBLE
                          && bottom != null && bottom.getGlobalVisibleRect(mNajmTouchRect)
                          && mNajmTouchRect.contains((int)event.getRawX(),(int)event.getRawY());'''
new='''android.view.View bottom = findViewById(R.id.najm_player_bottom);
                      android.view.View center = findViewById(R.id.najm_player_center);
                      boolean insideBottom = bottom != null
                          && bottom.getGlobalVisibleRect(mNajmTouchRect)
                          && mNajmTouchRect.contains((int)event.getRawX(),(int)event.getRawY());
                      boolean insideCenter = center != null
                          && center.getGlobalVisibleRect(mNajmTouchRect)
                          && mNajmTouchRect.contains((int)event.getRawX(),(int)event.getRawY());
                      mNajmTouchOnBottomControls = mNajmControls != null
                          && mNajmControls.getVisibility() == View.VISIBLE
                          && (insideBottom || insideCenter);'''
p=one(p,old,new,"tap region center and bottom")
player.write_text(p)

# Disable hover previews on tiny-memory devices. All video thumbnails
# are still loaded; only auto-playing card previews are disabled.
cards=JAVA/"presenter/VideoCardPresenter.java"
c=cards.read_text()
old='''    protected int getCardPreviewType(Context context) {
        return MainUIData.instance(context).getCardPreviewType();
    }'''
new='''    protected int getCardPreviewType(Context context) {
        android.app.ActivityManager am = (android.app.ActivityManager)
                context.getSystemService(Context.ACTIVITY_SERVICE);
        if (am != null && (am.isLowRamDevice() || am.getMemoryClass() <= 128)) {
            // Avoid second concurrent player/decoder while opening a real video.
            return MainUIData.CARD_PREVIEW_DISABLED;
        }
        return MainUIData.instance(context).getCardPreviewType();
    }'''
c=one(c,old,new,"disable video previews on low-memory screens")
c=one(c,".apply(ViewUtil.glideOptions())\n                // improve image compression",
         ".apply(ViewUtil.glideOptions())\n                .dontAnimate()\n                // improve image compression",
         "avoid thumbnail transitions")
cards.write_text(c)

# Respect saved quality settings, but default to H.264 720p on old head units.
pref=BASE/"prefs/PlayerData.java"
q=pref.read_text()
q=one(q,'''            } else if (VERSION.SDK_INT <= 23 && DeviceHelpers.isVP9ResolutionSupported(1080)) {
                formatItem = FormatItem.VIDEO_FHD_VP9_60;''',
        '''            } else if (VERSION.SDK_INT <= 27) {
                // Legacy car displays: AVC 720p starts and decodes more predictably
                // than FHD 60fps VP9. User-selected stored formats are untouched.
                formatItem = FormatItem.VIDEO_HD_AVC_30;''',
        "legacy video format fallback")
pref.write_text(q)

# Reduce only initial wait slightly; keep safety against rebuffering.
init=BASE/"exoplayer/other/ExoPlayerInitializer.java"
e=init.read_text()
e=one(e,"int bufferForPlaybackMs = 2_500;",
       "int bufferForPlaybackMs = 1_800; // NAJM: moderate fast-start; preserve 5s rebuffer",
       "first frame buffering threshold")
init.write_text(e)

print("NAJM Tube V2.2: central controls, low-memory card optimization, legacy AVC defaults, moderate fast-start.")
