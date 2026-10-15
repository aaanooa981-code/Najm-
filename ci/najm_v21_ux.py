#!/usr/bin/env python3
"""NAJM Tube V2.1 improvements applied AFTER the V2 hardening pass."""
from pathlib import Path

root = Path("SmartTube/smarttubetv/src/main")
java = root / "java/com/liskovsoft/smartyoutubetv2/tv"
browse = java / "ui/browse/BrowseActivity.java"
activity = java / "ui/playback/PlaybackActivity.java"

def replace_once(text, old, new, label):
    occurrences = text.count(old)
    if occurrences != 1:
        raise AssertionError(f"{label}: expected once, found {occurrences}")
    return text.replace(old, new, 1)

s=browse.read_text()
s=replace_once(
    s,
    "private void refreshNajmChips() {",
    """private void updateNajmChipSelection() {
                  if (mNajmChips == null) return;
                  for (int i=0; i<mNajmChips.getChildCount(); i++) {
                      android.view.View chip=mNajmChips.getChildAt(i);
                      if (chip.isSelected() != (i==mNajmIndex)) {
                          chip.setSelected(i==mNajmIndex);
                      }
                  }
              }
              private void refreshNajmChips() {""",
    "chip selection helper",
)
s=replace_once(
    s,
    "if (signature.equals(mNajmLastChipsSignature)) return;",
    """if (signature.equals(mNajmLastChipsSignature)) {
                      // Same data, but a different selected section: repaint selection.
                      updateNajmChipSelection();
                      return;
                  }""",
    "refresh selection even when chip data unchanged",
)
s=replace_once(
    s,
    "refreshNajmChips();",
    "updateNajmChipSelection();",
    "select chip without allocating new views",
)
browse.write_text(s)

s=activity.read_text()
s=replace_once(
    s, "private boolean mNajmOriginalMenuOpen;",
    """private boolean mNajmOriginalMenuOpen;
              private boolean mNajmTouchOnBottomControls;
              private final android.graphics.Rect mNajmTouchRect = new android.graphics.Rect();
              private int mNajmAutoHideMs = 3800;
              private boolean mNajmShowSmallProgress = true;""",
    "V2.1 settings and click-region fields",
)
# Dialog entry replaces the existing button handler but keeps advanced options.
anchor="findViewById(R.id.najm_player_options).setOnClickListener(v -> {"
start=s.find(anchor)
assert start != -1
end=s.find("                  });",start)
assert end != -1
end+=len("                  });")
old=s[start:end]
assert "mNajmOriginalMenuOpen = true" in old
s=s[:start]+"""findViewById(R.id.najm_player_options).setOnClickListener(v -> showNajmPlayerSettingsMenu());"""+s[end:]

# Mini bar preference, initial state and dispatch event region.
s=replace_once(
    s,
    "mNajmMiniProgress = findViewById(R.id.najm_player_mini_progress);",
    """mNajmMiniProgress = findViewById(R.id.najm_player_mini_progress);
                  android.content.SharedPreferences preferences =
                      getSharedPreferences("najm_tube_player_preferences", MODE_PRIVATE);
                  mNajmAutoHideMs = preferences.getInt("auto_hide_ms", 3800);
                  mNajmShowSmallProgress = preferences.getBoolean("mini_progress", true);
                  mNajmMiniProgress.setVisibility(mNajmShowSmallProgress ? View.VISIBLE : View.GONE);""",
    "player settings load",
)
s=replace_once(
    s, "mNajmHandler.postDelayed(mNajmDismiss, 3800);",
    "mNajmHandler.postDelayed(mNajmDismiss, mNajmAutoHideMs);",
    "configurable player hide timeout",
)
s=replace_once(
    s,
    "if (mNajmMiniProgress != null) mNajmMiniProgress.setVisibility(View.VISIBLE);",
    """if (mNajmMiniProgress != null)
                      mNajmMiniProgress.setVisibility(mNajmShowSmallProgress ? View.VISIBLE : View.GONE);""",
    "mini progress preference on hide",
)
# A control button is a normal ONE-TAP clickable item; don't reinterpret a
# repeated tap on a button as a seek gesture on the video behind it.
anchor="""                  if (mNajmGesture != null && mNajmGesture.onTouchEvent(event)) {"""
assert s.count(anchor)==1
s=s.replace(anchor,"""                  if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
                      android.view.View bottom = findViewById(R.id.najm_player_bottom);
                      mNajmTouchOnBottomControls = mNajmControls != null
                          && mNajmControls.getVisibility() == View.VISIBLE
                          && bottom != null && bottom.getGlobalVisibleRect(mNajmTouchRect)
                          && mNajmTouchRect.contains((int)event.getRawX(),(int)event.getRawY());
                  }
                  if (mNajmOriginalMenuOpen || mNajmTouchOnBottomControls) {
                      boolean handled = super.dispatchTouchEvent(event);
                      if (event.getActionMasked() == MotionEvent.ACTION_UP
                          || event.getActionMasked() == MotionEvent.ACTION_CANCEL)
                          mNajmTouchOnBottomControls = false;
                      return handled;
                  }
"""+anchor,1)

# Settings menu: one tap gives a choice of interface preferences or SmartTube
# advanced controls. Keep both accessible; no secret long press needed.
anchor="private void showNajmControls() {"
assert s.count(anchor)==1
settings='''private void showNajmPlayerSettingsMenu() {
                  final CharSequence[] actions = {
                      "إعدادات مشغل NAJM Tube",
                      "إعدادات SmartTube المتقدمة"
                  };
                  new android.app.AlertDialog.Builder(this)
                      .setTitle("إعدادات المشغل")
                      .setItems(actions, (dialog, which) -> {
                          if (which == 0) showNajmQuickSettings();
                          else openNajmAdvancedControls();
                      })
                      .setNegativeButton("إلغاء", null)
                      .show();
              }
              private void openNajmAdvancedControls() {
                  mNajmOriginalMenuOpen = true;
                  if (mPlaybackFragment != null)
                      mPlaybackFragment.setNajmExclusivePlayerControls(false);
                  mNajmHandler.removeCallbacks(mNajmDismiss);
                  if (mNajmControls != null) mNajmControls.setVisibility(View.GONE);
                  if (mNajmMiniProgress != null) mNajmMiniProgress.setVisibility(View.GONE);
                  if (mPlaybackFragment != null) mPlaybackFragment.showControlsOverlay(false);
              }
              private void showNajmQuickSettings() {
                  final CharSequence[] actions = {
                      "مدة ظهور أزرار الفيديو",
                      mNajmShowSmallProgress ?
                          "إخفاء خط التقدم الأحمر عند اختفاء الأزرار" :
                          "إظهار خط التقدم الأحمر عند اختفاء الأزرار"
                  };
                  new android.app.AlertDialog.Builder(this)
                      .setTitle("NAJM Tube — إعدادات اللمس")
                      .setItems(actions, (dialog, which) -> {
                          if (which==0) chooseNajmAutoHide();
                          else {
                              mNajmShowSmallProgress = !mNajmShowSmallProgress;
                              getSharedPreferences("najm_tube_player_preferences", MODE_PRIVATE)
                                  .edit().putBoolean("mini_progress",mNajmShowSmallProgress).apply();
                              if (mNajmMiniProgress != null)
                                  mNajmMiniProgress.setVisibility(
                                      mNajmShowSmallProgress &&
                                      (mNajmControls==null || mNajmControls.getVisibility()!=View.VISIBLE)
                                        ? View.VISIBLE : View.GONE);
                              showNajmQuickSettings();
                          }
                      })
                      .setNegativeButton("رجوع", (dialog,which)-> showNajmPlayerSettingsMenu())
                      .show();
              }
              private void chooseNajmAutoHide() {
                  final int[] milliseconds={2000,3800,6000,8000};
                  final CharSequence[] labels={"ثانيتان","4 ثوانٍ","6 ثوانٍ","8 ثوانٍ"};
                  int selected=1;
                  for (int i=0; i<milliseconds.length; i++)
                      if (milliseconds[i]==mNajmAutoHideMs)selected=i;
                  new android.app.AlertDialog.Builder(this)
                      .setTitle("إخفاء أزرار الفيديو بعد")
                      .setSingleChoiceItems(labels,selected,(dialog,index)-> {
                          mNajmAutoHideMs=milliseconds[index];
                          getSharedPreferences("najm_tube_player_preferences", MODE_PRIVATE)
                              .edit().putInt("auto_hide_ms",mNajmAutoHideMs).apply();
                          dialog.dismiss();
                          showNajmControls();
                      })
                      .setNegativeButton("إلغاء",null)
                      .show();
              }
              '''
s=s.replace(anchor,settings+anchor,1)
activity.write_text(s)
print("NAJM Tube V2.1: section selection, one-tap settings menu, stable video double-tap regions.")
