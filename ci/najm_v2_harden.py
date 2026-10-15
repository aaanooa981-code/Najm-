#!/usr/bin/env python3
"""NAJM Tube V2 focused hardening of the existing generated SmartTube UI fork.

This is intentionally idempotent in purpose (but run once per clean checkout)
and limits writes to player, home UI and search/manifest resources. It does not
alter the backend, APIs, account or history storage code.
"""
from pathlib import Path

root = Path("SmartTube/smarttubetv/src/main")
java = root / "java/com/liskovsoft/smartyoutubetv2/tv"
player = java / "ui/playback/PlaybackActivity.java"
player_fragment = java / "ui/playback/PlaybackFragment.java"
browse = java / "ui/browse/BrowseActivity.java"
search = java / "ui/search/tags/vineyard/SearchTagsFragmentBase.java"

def replace_once(source: str, old: str, new: str, label: str) -> str:
    found = source.count(old)
    if found != 1:
        raise RuntimeError(f"{label}: expected exactly one occurrence; got {found}")
    return source.replace(old, new, 1)

s = player.read_text()
# Stop periodic player UI refresh when paused/background; resume after onResume.
s = replace_once(
    s, "                  mNajmHandler.post(mNajmRefresh);\n",
    "                  // V2: refresh starts in onResume, not while activity is paused.\n",
    "stop starting refresh in onCreate",
)
s = replace_once(
    s, """        mIsBackPressed = false;
        super.onResume();""",
    """        mIsBackPressed = false;
        super.onResume();
        mNajmHandler.removeCallbacks(mNajmRefresh);
        mNajmHandler.post(mNajmRefresh);""",
    "lifecycle resume",
)
s = replace_once(
    s, """        // Run the code before the contained fragment
        super.onPause();""",
    """        // V2: don't waste CPU continuously updating hidden player UI.
        mNajmHandler.removeCallbacks(mNajmRefresh);
        mNajmHandler.removeCallbacks(mNajmDismiss);
        // Run the code before the contained fragment
        super.onPause();""",
    "lifecycle pause",
)
# Mini progress is only shown while custom main controls are hidden, preventing
# two overlapping scrubbars at the bottom.
s = replace_once(
    s,
    """if (mNajmControls != null) mNajmControls.setVisibility(View.GONE);""",
    """if (mNajmControls != null) mNajmControls.setVisibility(View.GONE);
                  if (mNajmMiniProgress != null) mNajmMiniProgress.setVisibility(View.VISIBLE);""",
    "autohide",
)
s = replace_once(
    s,
    """                  mNajmControls.setVisibility(View.VISIBLE);
                  mNajmHandler.removeCallbacks(mNajmDismiss);""",
    """                  mNajmControls.setVisibility(View.VISIBLE);
                  if (mNajmMiniProgress != null) mNajmMiniProgress.setVisibility(View.GONE);
                  mNajmHandler.removeCallbacks(mNajmDismiss);""",
    "show main controls",
)
# Settings opens upstream transport; hide mini line so SmartTube's controls
# are not visually stacked on top of our lightweight progress line.
s = replace_once(
    s,
    """                      mNajmControls.setVisibility(View.GONE);
                      if (mPlaybackFragment != null) mPlaybackFragment.showControlsOverlay(false);""",
    """                      mNajmControls.setVisibility(View.GONE);
                      if (mNajmMiniProgress != null) mNajmMiniProgress.setVisibility(View.GONE);
                      if (mPlaybackFragment != null) mPlaybackFragment.showControlsOverlay(false);""",
    "advanced player options",
)
# Avoid running UI updates every 800ms while invisible; still refresh the
# always-on red timeline at a modest frequency.
s = replace_once(
    s,
    """                      mNajmHandler.postDelayed(this, 800);""",
    """                      mNajmHandler.postDelayed(this,
                          mNajmControls != null && mNajmControls.getVisibility() == View.VISIBLE
                              ? 700L : 1500L);""",
    "refresh interval",
)
# Do not rebuild text widgets unless values genuinely changed.
s = replace_once(
    s,
    """                          mNajmTiming.setText(najmClock(position) + " / " + najmClock(duration));
                          mNajmToggle.setText(mPlaybackFragment.najmPlaying() ? "Ⅱ" : "▶");""",
    """                          String timeText = najmClock(position) + " / " + najmClock(duration);
                          if (!timeText.contentEquals(mNajmTiming.getText())) mNajmTiming.setText(timeText);
                          String toggleText = mPlaybackFragment.najmPlaying() ? "Ⅱ" : "▶";
                          if (!toggleText.contentEquals(mNajmToggle.getText())) mNajmToggle.setText(toggleText);""",
    "reduce text invalidations",
)
player.write_text(s)

# Disable reappearance of obsolete Leanback overlay from inactive old state.
f = player_fragment.read_text()
assert "setNajmExclusivePlayerControls" in f
assert "if (mNajmExclusivePlayerControls)" in f
assert ".seekSeconds(10)" in f
player_fragment.write_text(f)

# No autocomplete/tag chips: even a stale async callback should not repopulate
# them after the user began typing. Actual video results use a different adapter.
s = search.read_text()
s = replace_once(
    s,
    """    protected void attachAdapter(int index, ObjectAdapter adapter) {
        if (mResultsAdapter != null) {""",
    """    protected void attachAdapter(int index, ObjectAdapter adapter) {
        // V2: reject late autocomplete callbacks; video result rows remain intact.
        if (adapter == mSearchTagsAdapter) return;
        if (mResultsAdapter != null) {""",
    "search suggestion callback",
)
search.write_text(s)

# Rebuilding header chips on every repeated notification causes needless view
# allocation and small interface stutters on weak head units.
s = browse.read_text()
s = replace_once(
    s,
    """    private android.widget.LinearLayout mNajmChips;""",
    """    private android.widget.LinearLayout mNajmChips;
    private String mNajmLastChipsSignature;""",
    "home chips cache member",
)
s = replace_once(
    s,
    """                  java.util.List<String> names = mNajmBrowse.getHomeNavigationSections();
                  mNajmChips.removeAllViews();""",
    """                  java.util.List<String> names = mNajmBrowse.getHomeNavigationSections();
                  String signature = names.toString();
                  if (signature.equals(mNajmLastChipsSignature)) return;
                  mNajmLastChipsSignature = signature;
                  mNajmChips.removeAllViews();""",
    "home chip refresh cache",
)
browse.write_text(s)

# Smartphone / car tablet support: Leanback is desired but not mandatory.
manifest = root / "AndroidManifest.xml"
s = manifest.read_text()
s = replace_once(
    s,
    '''android:name="android.software.leanback"
        android:required="true"''',
    '''android:name="android.software.leanback"
        android:required="false"''',
    "touch-only Android devices",
)
manifest.write_text(s)

print("NAJM Tube V2 hardening applied: lifecycle, progress, UI churn, search, touch compatibility.")
