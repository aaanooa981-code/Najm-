#!/usr/bin/env python3
"""V2.6 performance safety and regression tests, before Gradle APK build."""
import unittest
from pathlib import Path

R=Path("SmartTube")
MAIN=R/"smarttubetv/src/main"
JAVA=MAIN/"java/com/liskovsoft/smartyoutubetv2/tv"

class V26Speed(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.card=(JAVA/"presenter/VideoCardPresenter.java").read_text()
  cls.player=(JAVA/"ui/playback/PlaybackActivity.java").read_text()
  cls.grad=(R/"smarttubetv/build.gradle").read_text()
  cls.init=(R/"common/src/main/java/com/liskovsoft/smartyoutubetv2/common/exoplayer/other/ExoPlayerInitializer.java").read_text()
 def test_static_primary_and_fallback_images_reuse_memory(self):
  self.assertEqual(self.card.count(".skipMemoryCache(VERSION.SDK_INT <= 21)"),2)
  self.assertIn(".dontAnimate()",self.card)
  self.assertIn(".diskCacheStrategy(VERSION.SDK_INT > 21 ? DiskCacheStrategy.ALL : DiskCacheStrategy.NONE)",self.card)
 def test_low_ram_video_previews_remain_off(self):
  self.assertIn("am.isLowRamDevice()",self.card)
  self.assertIn("am.getMemoryClass() <= 128",self.card)
  self.assertIn("MainUIData.CARD_PREVIEW_DISABLED",self.card)
 def test_video_preview_can_be_opted_into_but_defaults_off(self):
  self.assertIn('.getBoolean("moving_previews", false)',self.card)
  self.assertIn('.putBoolean("moving_previews",',self.player)
  self.assertIn("which == 3",self.player)
  self.assertIn("إيقاف المعاينات",self.player)
 def test_no_stream_engine_or_account_modification(self):
  self.assertIn("ExoPlayerInitializer", self.init)
  self.assertIn('getBoolean("fast_start", true)',self.init)
 def test_new_debug_apk_cannot_replace_existing_without_warning(self):
  self.assertIn('applicationId "org.smarttube.najmv26"',self.grad)
 def test_brand_and_working_search_still_present(self):
  self.assertIn('android:icon="@mipmap/najm_tube_icon"',(MAIN/"AndroidManifest.xml").read_text())
  self.assertIn("EditorInfo.IME_ACTION_GO",(JAVA/"ui/mod/leanback/search/SearchSupportFragment.java").read_text())

if __name__=="__main__": unittest.main(verbosity=2)
