#!/usr/bin/env python3
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

src=Path("SmartTube/smarttubetv/src")
common=Path("SmartTube/common/src/main/java/com/liskovsoft/smartyoutubetv2/common")

class NajmFastStartV24(unittest.TestCase):
    def test_launcher_name_is_arabic_in_actual_beta_flavor(self):
        for name in ["main","stbeta","ststable"]:
            p=src/name/"res/values/strings.xml"
            content=p.read_text()
            root=ET.fromstring(content)
            for key in ["app_name","browse_title"]:
                match=[e for e in root.findall("string") if e.get("name")==key]
                self.assertEqual(len(match),1,(name,key))
                self.assertEqual(match[0].text,"نجم تيوب",(name,key))
                self.assertNotIn("SmartTube beta",match[0].text)
    def test_all_launcher_entries_reference_same_name(self):
        manifest=(src/"main/AndroidManifest.xml").read_text()
        self.assertIn('android:label="@string/app_name"',manifest)
        self.assertIn('android:icon="@mipmap/najm_tube_icon"',manifest)
        self.assertNotIn('android:icon="@mipmap/app_icon_alt"',manifest)
    def test_adaptive_fast_start_respects_user_buffer_prefs(self):
        e=(common/"exoplayer/other/ExoPlayerInitializer.java").read_text()
        self.assertIn('getBoolean("fast_start", true)',e)
        self.assertIn("getVideoBufferType() == PlayerData.BUFFER_MEDIUM",e)
        self.assertIn("bufferForPlaybackMs = 1_200",e)
        self.assertIn("bufferForPlaybackAfterRebufferMs = 5_000",e)
        self.assertIn("setBufferDurationsMs(minBufferMs, maxBufferMs, bufferForPlaybackMs, bufferForPlaybackAfterRebufferMs)",e)
    def test_in_app_settings_can_turn_off_fast_start(self):
        act=(src/"main/java/com/liskovsoft/smartyoutubetv2/tv/ui/playback/PlaybackActivity.java").read_text()
        self.assertIn("بدء الفيديو السريع",act)
        self.assertIn('putBoolean("fast_start"',act)
        self.assertIn("which==2",act)
        self.assertIn("showNajmQuickSettings()",act)
    def test_video_ready_duration_recorded_without_network_blocking(self):
        engine=(common/"exoplayer/controller/ExoPlayerController.java").read_text()
        self.assertIn("mNajmSourceStartMs",engine)
        self.assertIn("android.os.SystemClock.elapsedRealtime()",engine)
        self.assertIn("NAJM video source ready after",engine)
        self.assertNotIn("Thread.sleep(",engine)
    def test_identity_and_brand_remain_independent(self):
        gradle=Path("SmartTube/smarttubetv/build.gradle").read_text()
        self.assertIn('applicationId "org.smarttube.najmv4"',gradle)
        self.assertTrue((src/"main/res/mipmap-nodpi/najm_tube_icon.png").is_file())
        layout=(src/"main/res/layout/fragment_main.xml").read_text()
        self.assertIn("نجم تيوب",layout)

if __name__=="__main__":
    unittest.main(verbosity=2)
