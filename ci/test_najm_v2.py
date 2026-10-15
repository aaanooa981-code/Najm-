#!/usr/bin/env python3
"""NAJM Tube V2 source audit gates. Run AFTER applying source patches, BEFORE APK build."""
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path("SmartTube/smarttubetv/src/main")
JAVA = ROOT / "java/com/liskovsoft/smartyoutubetv2/tv"

def read(path):
    return path.read_text(encoding="utf-8")

class V2Audit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.player = read(JAVA / "ui/playback/PlaybackActivity.java")
        cls.fragment = read(JAVA / "ui/playback/PlaybackFragment.java")
        cls.browse = read(JAVA / "ui/browse/BrowseActivity.java")
        cls.search = read(JAVA / "ui/search/tags/vineyard/SearchTagsFragmentBase.java")
        cls.search_fragment = read(JAVA / "ui/search/tags/SearchTagsFragment.java")
        cls.touch = read(JAVA / "ui/common/LeanbackActivity.java")
        cls.search_base = read(JAVA / "ui/mod/leanback/search/SearchSupportFragment.java")
        cls.layout = read(ROOT / "res/layout/fragment_playback.xml")
        cls.root = ET.fromstring(cls.layout)
        cls.andro = "{http://schemas.android.com/apk/res/android}"

    def test_no_center_floating_player(self):
        self.assertNotIn('android:layout_gravity="center"', self.layout)
        self.assertIn('android:id="@+id/najm_player_bottom"', self.layout)
        self.assertIn('android:layout_gravity="bottom"', self.layout)

    def test_all_player_buttons_exist_once(self):
        names = ("najm_player_toggle", "najm_player_back10", "najm_player_forward10",
                 "najm_player_previous_video", "najm_player_next_video",
                 "najm_player_options", "najm_player_time", "najm_player_seekbar",
                 "najm_player_mini_progress")
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(self.layout.count('android:id="@+id/'+name+'"'), 1)

    def test_player_controls_link_upstream(self):
        for name in ("najmTogglePlayback", "najmSeekTen", "skipToNext()", "skipToPrevious()"):
            self.assertIn(name, self.player)
        self.assertIn("mPlayerGlue.togglePlayback()", self.fragment)
        self.assertIn("mPlayerGlue.fastForward()", self.fragment)
        self.assertIn("mPlayerGlue.rewind()", self.fragment)
        self.assertIn(".seekSeconds(10)", self.fragment)
        self.assertIn("mNajmGesture.onTouchEvent(event)", self.player)

    def test_hide_duplicates_and_allow_settings(self):
        self.assertIn("mNajmExclusivePlayerControls", self.fragment)
        self.assertIn("mNajmOriginalMenuOpen", self.player)
        self.assertIn("setNajmExclusivePlayerControls(false)", self.player)
        self.assertIn("setNajmExclusivePlayerControls(true)", self.player)
        self.assertIn("if (mNajmMiniProgress != null) mNajmMiniProgress.setVisibility(View.GONE)",self.player)
        self.assertIn("if (mNajmMiniProgress != null) mNajmMiniProgress.setVisibility(View.VISIBLE)",self.player)

    def test_player_refresh_lifecycle(self):
        self.assertIn("mNajmHandler.removeCallbacks(mNajmRefresh);",self.player)
        self.assertIn("mNajmHandler.post(mNajmRefresh);",self.player)
        self.assertIn("? 700L : 1500L",self.player)
        self.assertIn("if (!timeText.contentEquals",self.player)

    def test_one_tap_and_keyboard_search(self):
        self.assertIn("setFocusableInTouchMode(false)",read(JAVA/"presenter/VideoCardPresenter.java"))
        self.assertIn("target.performClick()",self.touch)
        self.assertIn("private final Rect mNajmHitRect = new Rect();",self.touch)
        self.assertIn("Rect rect = mNajmHitRect;",self.touch)
        self.assertIn("EditorInfo.IME_ACTION_GO",self.search_base)
        self.assertIn("IME_ACTION_SEARCH",self.search_base)
        self.assertIn("mNajmFocusSubmittedResults",self.search_fragment)

    def test_search_suggestions_discarded(self):
        self.assertIn("if (adapter == mSearchTagsAdapter) return;",self.search)
        self.assertIn("clearTags();",self.search)

    def test_ui_chips_cached(self):
        self.assertIn("mNajmLastChipsSignature",self.browse)
        self.assertIn("signature.equals(mNajmLastChipsSignature)",self.browse)

    def test_identity_installation_compatibility(self):
        manifest=read(ROOT/"AndroidManifest.xml")
        self.assertIn('android:name="android.software.leanback"',manifest)
        self.assertIn('android:required="false"',manifest)
        self.assertIn('android:icon="@mipmap/najm_tube_icon"',manifest)
        self.assertIn('NAJM Tube',read(ROOT/"res/values/strings.xml"))
        gradle=read(Path("SmartTube/smarttubetv/build.gradle"))
        self.assertIn('applicationId "org.smarttube.najm"',gradle)

    def test_ui_xml_is_valid_and_layout_is_not_replaced_by_placeholder(self):
        self.assertTrue(self.root.tag.endswith("FrameLayout"))
        self.assertIn("playback_controls_fragment", self.layout)
        self.assertIn("najm_player_controls", self.layout)
        self.assertIn("najm_player_mini_progress", self.layout)
        self.assertNotIn("youtube_overlay_stub", self.layout)

if __name__ == "__main__":
    unittest.main(verbosity=2)
