#!/usr/bin/env python3
"""NAJM Tube V2.7 - make SmartTube video quality permanently 480p AVC 30fps.

Always prefer 480p video on every item, new session and application restart.
This respects video availability; underlying SmartTube still chooses the closest
playable track if a stream lacks 480p AVC. No streaming engine substitutions.
"""
from pathlib import Path

root=Path("SmartTube")
common=root/"common/src/main/java/com/liskovsoft/smartyoutubetv2/common"
prefs=common/"prefs/PlayerData.java"
dialogs=common/"utils/AppDialogUtil.java"
gradle=root/"smarttubetv/build.gradle"

s=prefs.read_text()
def one(text,old,new,label):
    n=text.count(old)
    if n!=1: raise AssertionError(f"{label}: expected exactly one anchor, got {n}")
    return text.replace(old,new,1)

s=one(s,
      'private static final String VIDEO_PLAYER_DATA = "video_player_data";',
      '''private static final String VIDEO_PLAYER_DATA = "video_player_data";
    // User-chosen NAJM Tube default: persists across profiles, sessions and videos.
    // Keep the preset flag so SmartTube's normal video-preset selector recognizes it.
    public static final FormatItem NAJM_LOCKED_480 =
            ExoFormatItem.fromVideoSpec("854,480,30,avc", true);''',
      "locked 480 quality declaration")

s=one(s,'''            case FormatItem.TYPE_VIDEO:
                format = mVideoFormat;
                break;''',
      '''            case FormatItem.TYPE_VIDEO:
                format = NAJM_LOCKED_480;
                break;''',
      "global video quality")
s=one(s,'''            case FormatItem.TYPE_VIDEO:
                mVideoFormat = format;
                break;''',
      '''            case FormatItem.TYPE_VIDEO:
                // Reject new video-specific or Auto changes in this locked build.
                mVideoFormat = NAJM_LOCKED_480;
                break;''',
      "persist 480 on quality change")
s=one(s,'''        mVideoFormat = Helpers.firstNonNull(ExoFormatItem.from(Helpers.parseStr(split, 9)), getDefaultVideoFormat());''',
      '''        // Even when an earlier SmartTube preference stored Auto or 720/1080,
        // restore the requested global 480p AVC preference.
        mVideoFormat = NAJM_LOCKED_480;''',
      "fixed on app restart")

s=one(s,'''    public void setTempVideoFormat(FormatItem format) {
        mTempVideoFormat = format;
    }

    public FormatItem getTempVideoFormat() {
        return mTempVideoFormat;
    }''',
      '''    public void setTempVideoFormat(FormatItem format) {
        mTempVideoFormat = NAJM_LOCKED_480;
    }

    public FormatItem getTempVideoFormat() {
        return NAJM_LOCKED_480;
    }''',
      "prevent temporary per-video overrides")

# Replace the standard device detection defaults. Our 480p preset is the
# desired default even on fast/new Android hardware.
begin=s.index("    public FormatItem getDefaultVideoFormat() {")
brace=s.index("{",begin)
depth=0
end=None
for i in range(brace,len(s)):
    if s[i]=="{": depth+=1
    elif s[i]=="}":
        depth-=1
        if depth==0:
            end=i+1
            break
assert end is not None
s=s[:begin]+'''    public FormatItem getDefaultVideoFormat() {
        return NAJM_LOCKED_480;
    }'''+s[end:]
prefs.write_text(s)

# Present one global profile in SmartTube's own Video Presets settings.
# Avoid a misleading Auto/Disabled entry when this particular build locks 480.
d=dialogs.read_text()
start=d.index("    private static List<OptionItem> fromPresets(Context context, VideoPreset[] presets, Runnable onFormatSelected) {")
brace=d.index("{",start)
depth=0
end=None
for i in range(brace,len(d)):
    if d[i]=="{":depth+=1
    elif d[i]=="}":
        depth-=1
        if depth==0:
            end=i+1
            break
assert end is not None
new='''    private static List<OptionItem> fromPresets(Context context, VideoPreset[] presets, Runnable onFormatSelected) {
        List<OptionItem> items = new ArrayList<>();
        PlayerData playerData = PlayerData.instance(context);
        // This app variant intentionally offers one persistent global quality.
        items.add(UiOptionItem.from("480p 30fps AVC — ثابت في نجم تيوب",
                option -> setFormat(PlayerData.NAJM_LOCKED_480, playerData, onFormatSelected),
                true));
        return items;
    }'''
d=d[:start]+new+d[end:]
dialogs.write_text(d)

# New package so older V2.6 and its existing data remain untouched.
g=gradle.read_text()
g=one(g,'applicationId "org.smarttube.najmv26"',
       'applicationId "org.smarttube.najmv27"',"separate signed APK test install")
gradle.write_text(g)
print("V2.7: fixed global 480p AVC 30fps preference, persists, only one preset displayed.")
