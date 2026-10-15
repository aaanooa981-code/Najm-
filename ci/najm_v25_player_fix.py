#!/usr/bin/env python3
"""NAJM Tube V2.5: touch-sized central controls and useful startup diagnostics.

Patch runs after V2.4 in a clean source checkout.
No changes to video APIs, accounts, stream extraction, or media engine.
"""
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT=Path("SmartTube/smarttubetv/src/main")
JAVA=ROOT/"java/com/liskovsoft/smartyoutubetv2/tv/ui/playback"
layout=ROOT/"res/layout/fragment_playback.xml"
s=layout.read_text()
m=re.search(
    r'<LinearLayout\s+android:id="@\+id/najm_player_center".*?</LinearLayout>',
    s, flags=re.S
)
assert m, "Center controls layout not found"
for control in ("najm_player_toggle","najm_player_back10","najm_player_forward10"):
    assert m.group(0).count(control)==1,control

# Keep previous/next video in bottom bar and the three common actions in center.
replacement='''<LinearLayout android:id="@+id/najm_player_center"
              android:layout_width="wrap_content"
              android:layout_height="110dp"
              android:layout_gravity="center"
              android:layoutDirection="ltr"
              android:orientation="horizontal"
              android:gravity="center_vertical"
              android:clickable="false">
              <TextView android:id="@+id/najm_player_back10"
                  style="@style/NajmTube.V25Control"
                  android:layout_width="96dp"
                  android:text="↶ 10"
                  android:textDirection="ltr"
                  android:contentDescription="ترجيع 10 ثوانٍ" />
              <TextView android:id="@+id/najm_player_toggle"
                  style="@style/NajmTube.V25Control"
                  android:layout_width="106dp"
                  android:layout_height="106dp"
                  android:layout_marginStart="13dp"
                  android:layout_marginEnd="13dp"
                  android:text="Ⅱ" android:textSize="43sp"
                  android:background="@drawable/najm_v25_primary_button"
                  android:contentDescription="تشغيل أو إيقاف مؤقت" />
              <TextView android:id="@+id/najm_player_forward10"
                  style="@style/NajmTube.V25Control"
                  android:layout_width="96dp"
                  android:text="10 ↷"
                  android:textDirection="ltr"
                  android:contentDescription="تقديم 10 ثوانٍ" />
            </LinearLayout>'''
s=s[:m.start()]+replacement+s[m.end():]

# Startup trouble status is not a spinner; shown only after a real wait.
# Position it below the center controls so the video and its buttons stay visible.
status='''<TextView android:id="@+id/najm_player_loading_hint"
              android:layout_width="wrap_content"
              android:layout_height="wrap_content"
              android:layout_gravity="center"
              android:layout_marginTop="165dp"
              android:paddingStart="18dp" android:paddingEnd="18dp"
              android:paddingTop="7dp" android:paddingBottom="7dp"
              android:background="@drawable/najm_v25_hint_bg"
              android:textColor="#FFFFFF" android:textSize="15sp"
              android:gravity="center" android:visibility="gone"
              android:contentDescription="حالة تحميل الفيديو" />
            '''
# Status must be independent of auto-hidden transport overlay.
# Put near the root end so it remains visible while buffering.
end=s.rfind('</FrameLayout>')
assert end > 0
s=s[:end]+status+s[end:]
ET.fromstring(s)
layout.write_text(s)

(ROOT/"res/values/najm_v25_controls.xml").write_text('''<resources>
  <style name="NajmTube.V25Control" parent="@android:style/Widget.TextView">
    <item name="android:layout_height">92dp</item>
    <item name="android:gravity">center</item>
    <item name="android:textColor">#FFFFFF</item>
    <item name="android:textSize">29sp</item>
    <item name="android:textStyle">bold</item>
    <item name="android:clickable">true</item>
    <item name="android:focusable">true</item>
    <item name="android:background">@drawable/najm_v25_button</item>
  </style>
</resources>''')
(ROOT/"res/drawable/najm_v25_button.xml").write_text('''<selector xmlns:android="http://schemas.android.com/apk/res/android">
  <item android:state_pressed="true"><shape android:shape="oval">
    <solid android:color="#C5777777"/></shape></item>
  <item><shape android:shape="oval"><solid android:color="#991B1B1B"/></shape></item>
</selector>''')
(ROOT/"res/drawable/najm_v25_primary_button.xml").write_text('''<selector xmlns:android="http://schemas.android.com/apk/res/android">
  <item android:state_pressed="true"><shape android:shape="oval">
    <solid android:color="#C5B31C35"/></shape></item>
  <item><shape android:shape="oval"><solid android:color="#AA151515"/></shape></item>
</selector>''')
(ROOT/"res/drawable/najm_v25_hint_bg.xml").write_text('''<shape xmlns:android="http://schemas.android.com/apk/res/android"
  android:shape="rectangle"><solid android:color="#CE161616"/>
  <corners android:radius="16dp"/></shape>''')

# API read-only status: no stream or account engine writes.
fragment=JAVA/"PlaybackFragment.java"
f=fragment.read_text()
anchor='    public long najmDuration() {'
assert f.count(anchor)==1
extra='''    public boolean najmPlayerReady() {
        return mPlayer != null
            && mPlayer.getPlaybackState() == com.google.android.exoplayer2.Player.STATE_READY;
    }
    public boolean najmHasSelectedVideo() {
        return getVideo() != null;
    }
'''
f=f.replace(anchor,extra+anchor,1)
fragment.write_text(f)

activity=JAVA/"PlaybackActivity.java"
a=activity.read_text()
anchor='private boolean mNajmOriginalMenuOpen;'
assert a.count(anchor)==1
a=a.replace(anchor,anchor+'''
    private android.widget.TextView mNajmLoadingHint;
    private long mNajmFirstFrameWaitStarted;
    private boolean mNajmReportedSlowVideo;
''',1)

anchor='mNajmControls = findViewById(R.id.najm_player_controls);'
assert a.count(anchor)==1
a=a.replace(anchor,anchor+'''
                  mNajmLoadingHint=findViewById(R.id.najm_player_loading_hint);''',1)

# Existing runnable updates whenever visible or on mini-progress wake-up.
# Do not invent retries that may loop indefinitely on an unsupported stream.
anchor='mNajmToggle.setText(toggleText);'
assert a.count(anchor)==1
a=a.replace(anchor,anchor+'\n                          updateNajmFirstFrameHint();',1)

anchor='private void showNajmControls() {'
assert a.count(anchor)==1
new='''private void updateNajmFirstFrameHint() {
                  if (mNajmLoadingHint == null || mPlaybackFragment == null) return;
                  if (!mPlaybackFragment.najmHasSelectedVideo()
                      || mPlaybackFragment.najmPlayerReady()) {
                      mNajmFirstFrameWaitStarted = 0L;
                      mNajmReportedSlowVideo = false;
                      mNajmLoadingHint.setVisibility(View.GONE);
                      return;
                  }
                  long now=android.os.SystemClock.elapsedRealtime();
                  if (mNajmFirstFrameWaitStarted == 0L) {
                      mNajmFirstFrameWaitStarted=now;
                      mNajmLoadingHint.setVisibility(View.GONE);
                      return;
                  }
                  long wait=now-mNajmFirstFrameWaitStarted;
                  if (wait >= 7000L && !mNajmReportedSlowVideo) {
                      android.util.Log.w("NAJM_TUBE", "Video not ready after "+wait+
                        "ms; device/network/decoder investigation needed");
                      mNajmReportedSlowVideo=true;
                  }
                  if (wait >= 16000L) {
                      mNajmLoadingHint.setText(
                        "تأخر تشغيل الفيديو — افحص الإنترنت أو جرّب جودة 480p من إعدادات SmartTube");
                      mNajmLoadingHint.setVisibility(View.VISIBLE);
                  } else if (wait >= 7000L) {
                      mNajmLoadingHint.setText("جارٍ تجهيز الفيديو...");
                      mNajmLoadingHint.setVisibility(View.VISIBLE);
                  }
              }
              '''
a=a.replace(anchor,new+anchor,1)

# On video switch, status can never stay stale; reset on player action when
# previous/next clicked (loading detector still auto-resets on READY).
for name in ("najm_player_previous_video", "najm_player_next_video"):
    assert "R.id."+name in a
activity.write_text(a)
print("NAJM Tube V2.5: larger central transport + delayed first-frame status (no forced retry).")
