#!/usr/bin/env python3
"""V2.3 visual shell smoke tests — run after generated sources are patched."""
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path("SmartTube/smarttubetv/src/main")
PACKAGE=ROOT/"java/com/liskovsoft/smartyoutubetv2/tv"
class AndroidYouTubeStyle(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.home=(ROOT/"res/layout/fragment_main.xml").read_text()
  cls.xml=ET.fromstring(cls.home)
  cls.browse=(PACKAGE/"ui/browse/BrowseActivity.java").read_text()
  cls.player=(ROOT/"res/layout/fragment_playback.xml").read_text()
  cls.gradle=Path("SmartTube/smarttubetv/build.gradle").read_text()
 def test_navigation_rail_and_search(self):
  for n in ("najm_menu","najm_search","najm_search_icon","najm_brand_icon","najm_account",
            "najm_nav_home","najm_nav_shorts","najm_nav_subscriptions","najm_nav_library","najm_chips","main_frame"):
   self.assertEqual(self.home.count('android:id="@+id/'+n+'"'),1,n)
 def test_navigation_is_clickable_and_not_placeholder(self):
  self.assertIn("navigateNajmCategory(",self.browse)
  self.assertIn("showNavigationFromTopBar()",self.browse)
  self.assertIn("R.id.najm_nav_subscriptions",self.browse)
  self.assertIn("R.id.najm_search_icon",self.browse)
 def test_player_buttons_stay_centered_and_functional(self):
  for n in ("najm_player_center","najm_player_toggle","najm_player_back10","najm_player_forward10",
            "najm_player_next_video","najm_player_previous_video","najm_player_bottom","najm_player_seekbar"):
   self.assertEqual(self.player.count('android:id="@+id/'+n+'"'),1,n)
  self.assertIn('android:layout_gravity="center"',self.player)
  ET.fromstring(self.player)
 def test_preserve_smarttube_engine(self):
  s=(PACKAGE/"ui/playback/PlaybackFragment.java").read_text()
  for call in ("mPlayerGlue.togglePlayback()","mPlayerGlue.fastForward()","mPlayerGlue.rewind()"):
   self.assertIn(call,s)
 def test_install_alongside_previous_versions(self):
  self.assertIn('applicationId "org.smarttube.najmv3"',self.gradle)
 def test_brand_still_has_image_resource(self):
  self.assertIn("@mipmap/najm_tube_icon",self.home)
  self.assertTrue((ROOT/"res/values/najm_navrail.xml").exists())
 def test_search_supports_keyboard_action(self):
  s=(PACKAGE/"ui/mod/leanback/search/SearchSupportFragment.java").read_text()
  self.assertIn("EditorInfo.IME_ACTION_GO",s)
  self.assertIn("EditorInfo.IME_ACTION_SEARCH",s)
 def test_all_icon_accessibility(self):
  self.assertIn('android:contentDescription="الرئيسية"',self.home)
  self.assertIn('android:contentDescription="الحساب الشخصي"',self.home)
if __name__=="__main__":unittest.main(verbosity=2)
