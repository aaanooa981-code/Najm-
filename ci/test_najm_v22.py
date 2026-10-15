#!/usr/bin/env python3
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

R=Path("SmartTube/smarttubetv/src/main")
B=Path("SmartTube/common/src/main/java/com/liskovsoft/smartyoutubetv2/common")
J=R/"java/com/liskovsoft/smartyoutubetv2/tv"

class PlayerAndStartup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout=(R/"res/layout/fragment_playback.xml").read_text()
        cls.activity=(J/"ui/playback/PlaybackActivity.java").read_text()
        cls.cards=(J/"presenter/VideoCardPresenter.java").read_text()
        cls.player=(B/"prefs/PlayerData.java").read_text()
        cls.initializer=(B/"exoplayer/other/ExoPlayerInitializer.java").read_text()
    def test_center_has_five_actions(self):
        doc=ET.fromstring(self.layout)
        ids=["najm_player_previous_video","najm_player_back10","najm_player_toggle",
             "najm_player_forward10","najm_player_next_video"]
        for id_ in ids:self.assertEqual(self.layout.count('android:id="@+id/'+id_+'"'),1)
        self.assertIn('android:id="@+id/najm_player_center"',self.layout)
        self.assertIn('android:layout_gravity="center"',self.layout)
        self.assertNotIn("najm_player_dock", self.layout)
    def test_bottom_has_progress_and_settings(self):
        for s in ("najm_player_seekbar","najm_player_mini_progress",
                  "najm_player_time","najm_player_options","najm_player_bottom"):
            self.assertEqual(self.layout.count('android:id="@+id/'+s+'"'),1)
    def test_double_tap_skips_video_not_controls(self):
        self.assertIn("insideCenter",self.activity)
        self.assertIn("insideBottom || insideCenter",self.activity)
        self.assertIn("mNajmGesture.onTouchEvent(event)",self.activity)
        self.assertIn("najmSeekTen(true)",self.activity)
        self.assertIn("najmSeekTen(false)",self.activity)
    def test_low_memory_video_previews_disabled(self):
        self.assertIn("am.isLowRamDevice()",self.cards)
        self.assertIn("am.getMemoryClass() <= 128",self.cards)
        self.assertIn("MainUIData.CARD_PREVIEW_DISABLED",self.cards)
        self.assertIn(".dontAnimate()",self.cards)
    def test_legacy_quality_default_only(self):
        self.assertIn("VERSION.SDK_INT <= 27",self.player)
        self.assertIn("FormatItem.VIDEO_HD_AVC_30",self.player)
        self.assertIn("mVideoFormat = Helpers.firstNonNull",self.player)
    def test_startup_buffer_and_rebuffer(self):
        self.assertIn("int bufferForPlaybackMs = 1_800;",self.initializer)
        self.assertIn("int bufferForPlaybackAfterRebufferMs = 5_000;",self.initializer)
    def test_player_identity_and_existing_search(self):
        assert "org.smarttube.najm" in Path("SmartTube/smarttubetv/build.gradle").read_text()
        assert "EditorInfo.IME_ACTION_GO" in (J/"ui/mod/leanback/search/SearchSupportFragment.java").read_text()
        assert "mNajmExclusivePlayerControls" in (J/"ui/playback/PlaybackFragment.java").read_text()
if __name__=="__main__":unittest.main(verbosity=2)
