#!/usr/bin/env python3
"""NAJM Tube V2.7 simple mode: hide all settings entry points.

Keep settings services and databases available internally so playback,
sign-in, history and storage don't break. The 480p lock is applied separately.
"""
from pathlib import Path
import xml.etree.ElementTree as ET

root=Path("SmartTube")
main=root/"smarttubetv/src/main"
common=root/"common/src/main/java/com/liskovsoft/smartyoutubetv2/common"
browse=common/"app/presenters/BrowsePresenter.java"
s=browse.read_text()
old="if (getSidebarService().isSettingsSectionEnabled()) {"
assert s.count(old)==1, "BrowsePresenter settings sidebar changed"
s=s.replace(old,'''if (false && getSidebarService().isSettingsSectionEnabled()) {
            // NAJM simple mode: the settings section is intentionally hidden.
            // Keep internal settings services to preserve account and player data.''',1)
browse.write_text(s)

# Preserve buttons and click wiring, but hide the visible settings control so
# Java code that calls findViewById() won't fail with a NullPointerException.
layout=main/"res/layout/fragment_playback.xml"
xml=layout.read_text()
import re
pattern=r'(<TextView\s+android:id="@\+id/najm_player_options"\s[\s\S]*?)(/>)'
m=re.search(pattern,xml)
assert m and xml.count('android:id="@+id/najm_player_options"')==1, "Options widget not found"
widget=m.group(0)
assert 'android:visibility=' not in widget, "Settings widget already hidden"
xml=xml[:m.start()]+widget.replace('/>','android:visibility="gone" />',1)+xml[m.end():]
ET.fromstring(xml)
layout.write_text(xml)

# Simplify the account home only by retaining its sign-in button: no change
# to playback internals, profile preferences, APIs, or saved subscriptions.
print("NAJM V2.7 simple mode: Settings sidebar + playback gear hidden. Playback/profile engine retained.")
