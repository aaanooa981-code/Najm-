#!/usr/bin/env python3
"""NAJM Tube V2.1 static regression tests after source transformation."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT=Path("SmartTube/smarttubetv/src/main")
JAVA=ROOT/"java/com/liskovsoft/smartyoutubetv2/tv"

class V21UXAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.browse=(JAVA/"ui/browse/BrowseActivity.java").read_text()
        cls.player=(JAVA/"ui/playback/PlaybackActivity.java").read_text()
        cls.fragment=(JAVA/"ui/playback/PlaybackFragment.java").read_text()
        cls.layout=(ROOT/"res/layout/fragment_playback.xml").read_text()
    def test_selection_updates_even_when_rows_unchanged(self):
        self.assertIn("if (signature.equals(mNajmLastChipsSignature)) {",self.browse)
        self.assertIn("updateNajmChipSelection();",self.browse)
        self.assertIn("chip.setSelected(i==mNajmIndex)",self.browse)
    def test_chip_click_keeps_touch_selection(self):
        self.assertIn("mNajmBrowse.navigateFromTopBar(idx);",self.browse)
        self.assertIn("mNajmIndex=idx;",self.browse)
        self.assertIn("updateNajmChipSelection();",self.browse)
    def test_one_tap_settings_menu_instead_of_undiscoverable_long_press(self):
        self.assertIn("R.id.najm_player_options).setOnClickListener(v -> showNajmPlayerSettingsMenu());",self.player)
        self.assertIn("showNajmQuickSettings()",self.player)
        self.assertIn("openNajmAdvancedControls()",self.player)
        self.assertIn("setNajmExclusivePlayerControls(false)",self.player)
    def test_user_preferences_are_persistent(self):
        self.assertIn('getSharedPreferences("najm_tube_player_preferences", MODE_PRIVATE)',self.player)
        self.assertIn('putInt("auto_hide_ms"',self.player)
        self.assertIn('putBoolean("mini_progress"',self.player)
        self.assertIn('mNajmAutoHideMs',self.player)
    def test_player_buttons_do_not_trigger_video_gestures(self):
        self.assertIn("mNajmTouchOnBottomControls",self.player)
        self.assertIn("R.id.najm_player_bottom",self.player)
        self.assertIn("mNajmGesture.onTouchEvent(event)",self.player)
        self.assertIn("super.dispatchTouchEvent(event)",self.player)
    def test_smarttube_player_engine_remains(self):
        self.assertIn("mPlayerGlue.togglePlayback()",self.fragment)
        self.assertIn("mPlayerGlue.fastForward()",self.fragment)
        self.assertIn("mPlayerGlue.rewind()",self.fragment)
        self.assertIn(".seekSeconds(10)",self.fragment)
    def test_accessibility_labels_and_progress_remain(self):
        ET.fromstring(self.layout)
        for name in ("najm_player_bottom","najm_player_options",
                     "najm_player_seekbar","najm_player_mini_progress"):
            self.assertEqual(self.layout.count('android:id="@+id/'+name+'"'),1)

if __name__ == "__main__":
    unittest.main(verbosity=2)
