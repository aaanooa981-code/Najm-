#!/usr/bin/env python3
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

root=Path("SmartTube/smarttubetv/src/main")
java=root/"java/com/liskovsoft/smartyoutubetv2/tv/ui/playback"
ns="{http://schemas.android.com/apk/res/android}"

class V25Player(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.xml=(root/"res/layout/fragment_playback.xml").read_text()
  cls.root=ET.fromstring(cls.xml)
  cls.act=(java/"PlaybackActivity.java").read_text()
  cls.fragment=(java/"PlaybackFragment.java").read_text()
 def test_center_buttons_large_and_no_duplicate(self):
  row=next(e for e in clswalk(self.root) if e.attrib.get(ns+"id")=="@+id/najm_player_center")
  self.assertEqual(row.attrib[ns+"layout_gravity"],"center")
  for k in ("najm_player_toggle","najm_player_back10","najm_player_forward10"):
   matching=[e for e in row.iter() if e.attrib.get(ns+"id")=="@+id/"+k]
   self.assertEqual(len(matching),1,k)
   self.assertIn("@style/NajmTube.V25Control",matching[0].attrib.get("style",""))
  self.assertEqual(self.xml.count('android:id="@+id/najm_player_previous_video"'),1)
  self.assertEqual(self.xml.count('android:id="@+id/najm_player_next_video"'),1)
 def test_status_is_independent_of_autohide(self):
  root_children=[e.attrib.get(ns+"id","") for e in self.root]
  self.assertIn("@+id/najm_player_loading_hint",root_children)
  self.assertIn("updateNajmFirstFrameHint();",self.act)
  self.assertIn("mNajmLoadingHint.setVisibility(View.GONE);",self.act)
 def test_buffering_is_diagnostic_not_unbounded_retry(self):
  self.assertIn("wait >= 7000L",self.act)
  self.assertIn("wait >= 16000L",self.act)
  self.assertIn("com.google.android.exoplayer2.Player.STATE_READY",self.fragment)
  self.assertNotIn("postDelayed(() -> retry",self.act)
 def test_old_smarttube_actions_preserved(self):
  for x in ("najmSeekTen(true)","najmSeekTen(false)","mNajmGesture.onTouchEvent","showNajmPlayerSettingsMenu"):
   self.assertIn(x,self.act)
  for x in ("mPlayerGlue.fastForward()","mPlayerGlue.rewind()","mPlayerGlue.togglePlayback()"):
   self.assertIn(x,self.fragment)
 def test_brand_and_layout_resources(self):
  for x in ("najm_v25_controls.xml","najm_v25_button.xml",
            "najm_v25_primary_button.xml","najm_v25_hint_bg.xml"):
   self.assertTrue(list((root/"res").rglob(x)),x)
  self.assertIn("najm_tube_icon", (root/"AndroidManifest.xml").read_text())
def clswalk(root):
 return root.iter()
if __name__=="__main__":unittest.main(verbosity=2)
