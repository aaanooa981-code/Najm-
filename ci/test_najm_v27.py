#!/usr/bin/env python3
"""NAJM Tube V2.7 source smoke tests: simple mode + fixed 480p."""
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET
R=Path("SmartTube")
M=R/"smarttubetv/src/main"
C=R/"common/src/main/java/com/liskovsoft/smartyoutubetv2/common"
class FixedQualitySimpleMode(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=(C/"prefs/PlayerData.java").read_text()
  cls.dialog=(C/"utils/AppDialogUtil.java").read_text()
  cls.browse=(C/"app/presenters/BrowsePresenter.java").read_text()
  cls.layout=(M/"res/layout/fragment_playback.xml").read_text()
  cls.gradle=(R/"smarttubetv/build.gradle").read_text()
 def test_global_presets_provide_480_avc(self):
  self.assertIn('ExoFormatItem.fromVideoSpec("854,480,30,avc", true)',self.data)
  self.assertIn('return NAJM_LOCKED_480;',self.data)
  self.assertIn('mVideoFormat = NAJM_LOCKED_480;',self.data)
 def test_saved_or_temp_quality_cannot_override_480(self):
  self.assertIn('mTempVideoFormat = NAJM_LOCKED_480;',self.data)
  self.assertIn('public FormatItem getTempVideoFormat()',self.data)
  self.assertIn('public FormatItem getDefaultVideoFormat() {\n        return NAJM_LOCKED_480;',self.data)
 def test_video_preset_settings_can_only_show_480(self):
  self.assertIn('480p 30fps AVC — ثابت في نجم تيوب',self.dialog)
  self.assertIn('UiOptionItem.from("480p 30fps AVC',self.dialog)
 def test_remove_settings_sidebar_only(self):
  self.assertIn('if (false && getSidebarService().isSettingsSectionEnabled()) {',self.browse)
  self.assertIn('mSettingsGridMapping',self.browse)
 def test_gear_is_hidden_but_defined(self):
  root=ET.fromstring(self.layout)
  key="{http://schemas.android.com/apk/res/android}"
  widgets=[e for e in root.iter() if e.get(key+"id")=="@+id/najm_player_options"]
  self.assertEqual(len(widgets),1)
  self.assertEqual(widgets[0].get(key+"visibility"),"gone")
 def test_account_login_and_search_remain(self):
  home=(M/"res/layout/fragment_main.xml").read_text()
  self.assertIn("najm_account",home)
  self.assertIn("najm_search",home)
 def test_clean_test_package(self):
  self.assertIn('applicationId "org.smarttube.najmv27"',self.gradle)
if __name__=="__main__":unittest.main(verbosity=2)
