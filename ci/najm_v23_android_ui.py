#!/usr/bin/env python3
"""NAJM Tube V2.3 — Android YouTube-like tablet-landscape user interface.

Preserves SmartTube's existing media retrieval, accounts, saved playlists and
playback engine. Only replaces the visual shell and relocates our transport
buttons. Functional controls always delegate to pre-existing SmartTube actions.
"""
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT=Path("SmartTube/smarttubetv/src/main")
JAVA=ROOT/"java/com/liskovsoft/smartyoutubetv2/tv"

home=ROOT/"res/layout/fragment_main.xml"
home.write_text("""<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent" android:layout_height="match_parent"
    android:orientation="vertical" android:layoutDirection="ltr"
    android:background="#0F0F0F">
  <!-- Compact YouTube Android tablet toolbar. -->
  <LinearLayout android:layout_width="match_parent" android:layout_height="62dp"
      android:orientation="horizontal" android:gravity="center_vertical"
      android:paddingStart="10dp" android:paddingEnd="16dp">
    <TextView android:id="@+id/najm_menu"
        android:layout_width="45dp" android:layout_height="48dp"
        android:gravity="center" android:text="☰" android:textColor="#FFFFFF"
        android:textSize="23sp" android:clickable="true" android:focusable="true"
        android:contentDescription="فتح القائمة"/>
    <ImageView android:id="@+id/najm_brand_icon"
        android:layout_width="43dp" android:layout_height="43dp"
        android:src="@mipmap/najm_tube_icon" android:scaleType="fitCenter"
        android:contentDescription="نجم تيوب"/>
    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:layout_marginStart="6dp" android:layout_marginEnd="24dp"
        android:text="نجم تيوب" android:textColor="#FFFFFF"
        android:textStyle="bold" android:textSize="21sp"/>
    <TextView android:id="@+id/najm_search"
        android:layout_width="0dp" android:layout_weight="1"
        android:layout_height="42dp" android:maxWidth="690dp"
        android:background="@drawable/najm_search_bg"
        android:paddingStart="16dp" android:paddingEnd="16dp"
        android:gravity="center_vertical|right" android:layoutDirection="rtl"
        android:text="بحث" android:textSize="16sp" android:textColor="#BABABA"
        android:clickable="true" android:focusable="true"
        android:contentDescription="البحث في الفيديوهات"/>
    <TextView android:id="@+id/najm_search_icon"
        android:layout_width="48dp" android:layout_height="42dp"
        android:layout_marginStart="1dp" android:background="@drawable/najm_search_action_bg"
        android:text="⌕" android:textSize="24sp" android:gravity="center"
        android:textColor="#FFFFFF" android:clickable="true" android:focusable="true"
        android:contentDescription="فتح البحث"/>
    <Space android:layout_width="0dp" android:layout_weight="1"
        android:layout_height="1dp"/>
    <TextView android:id="@+id/najm_account"
        android:layout_width="46dp" android:layout_height="46dp"
        android:background="@drawable/najm_profile_bg"
        android:gravity="center" android:text="●"
        android:textColor="#FFFFFF" android:textSize="24sp"
        android:clickable="true" android:focusable="true"
        android:contentDescription="الحساب الشخصي"/>
  </LinearLayout>
  <!-- Official-app inspired vertical shortcuts for landscape tablets. -->
  <LinearLayout android:layout_width="match_parent" android:layout_height="0dp"
      android:layout_weight="1" android:orientation="horizontal">
    <LinearLayout android:id="@+id/najm_navigation_rail"
        android:layout_width="88dp" android:layout_height="match_parent"
        android:orientation="vertical" android:paddingTop="8dp"
        android:background="#0F0F0F">
      <TextView android:id="@+id/najm_nav_home"
          style="@style/NajmTube.NavRailItem" android:text="⌂\nالرئيسية"
          android:contentDescription="الرئيسية"/>
      <TextView android:id="@+id/najm_nav_shorts"
          style="@style/NajmTube.NavRailItem" android:text="▷\nShorts"
          android:contentDescription="المقاطع القصيرة"/>
      <TextView android:id="@+id/najm_nav_subscriptions"
          style="@style/NajmTube.NavRailItem" android:text="▣\nالاشتراكات"
          android:contentDescription="الاشتراكات"/>
      <TextView android:id="@+id/najm_nav_library"
          style="@style/NajmTube.NavRailItem" android:text="▤\nأنت"
          android:contentDescription="المكتبة والحساب"/>
    </LinearLayout>
    <LinearLayout android:layout_width="0dp" android:layout_weight="1"
        android:layout_height="match_parent" android:orientation="vertical">
      <HorizontalScrollView android:layout_width="match_parent"
          android:layout_height="54dp" android:scrollbars="none"
          android:fillViewport="false">
        <LinearLayout android:id="@+id/najm_chips"
            android:layout_width="wrap_content" android:layout_height="match_parent"
            android:orientation="horizontal" android:gravity="center_vertical"
            android:paddingStart="10dp" android:paddingEnd="10dp"/>
      </HorizontalScrollView>
      <fragment android:id="@+id/main_frame"
          android:name="com.liskovsoft.smartyoutubetv2.tv.ui.browse.BrowseFragment"
          android:layout_width="match_parent" android:layout_height="0dp"
          android:layout_weight="1"/>
    </LinearLayout>
  </LinearLayout>
</LinearLayout>
""")
(ROOT/"res/drawable/najm_search_action_bg.xml").write_text(
    '<shape xmlns:android="http://schemas.android.com/apk/res/android" '
    'android:shape="rectangle"><solid android:color="#252525"/>'
    '<corners android:topRightRadius="24dp" android:bottomRightRadius="24dp"/>'
    '<stroke android:width="1dp" android:color="#3F3F3F"/></shape>')
(ROOT/"res/drawable/najm_profile_bg.xml").write_text(
    '<shape xmlns:android="http://schemas.android.com/apk/res/android" '
    'android:shape="oval"><solid android:color="#39476D"/></shape>')
(ROOT/"res/values/najm_navrail.xml").write_text("""<resources>
  <style name="NajmTube.NavRailItem" parent="@android:style/Widget.TextView">
    <item name="android:layout_width">match_parent</item>
    <item name="android:layout_height">79dp</item>
    <item name="android:gravity">center</item>
    <item name="android:textColor">#E6E6E6</item>
    <item name="android:textSize">12sp</item>
    <item name="android:clickable">true</item>
    <item name="android:focusable">true</item>
    <item name="android:background">?android:attr/selectableItemBackground</item>
  </style>
</resources>""")

browse=JAVA/"ui/browse/BrowseActivity.java"
s=browse.read_text()
needle='''findViewById(R.id.najm_search).setOnClickListener(v ->'''
assert s.count(needle)==1, "search listener must already exist"
s=s.replace(needle,'''findViewById(R.id.najm_search_icon).setOnClickListener(v ->
                      com.liskovsoft.smartyoutubetv2.common.app.presenters.SearchPresenter.instance(this).startSearch(null));
                  findViewById(R.id.najm_search).setOnClickListener(v ->''',1)
needle='''mNajmBrowse.setOnSectionsChangedListener(() -> runOnUiThread(this::refreshNajmChips));'''
assert s.count(needle)==1
s=s.replace(needle,'''findViewById(R.id.najm_nav_home).setOnClickListener(v ->
                      navigateNajmCategory("الرئيسية", "Home", "Recommended"));
                  findViewById(R.id.najm_nav_shorts).setOnClickListener(v ->
                      navigateNajmCategory("Shorts", "المقاطع القصيرة"));
                  findViewById(R.id.najm_nav_subscriptions).setOnClickListener(v ->
                      navigateNajmCategory("Subscriptions", "الاشتراكات"));
                  findViewById(R.id.najm_nav_library).setOnClickListener(v ->
                      com.liskovsoft.smartyoutubetv2.common.app.presenters.dialogs.AccountSelectionPresenter.instance(this).nextAccountOrDialog());
                  mNajmBrowse.setOnSectionsChangedListener(() -> runOnUiThread(this::refreshNajmChips));''',1)
needle='''private void updateNajmChipSelection() {'''
assert s.count(needle)==1
s=s.replace(needle,'''private void navigateNajmCategory(String... terms) {
                  if (mNajmBrowse == null) return;
                  java.util.List<String> names = mNajmBrowse.getHomeNavigationSections();
                  for (int i=0;i<names.size();i++) {
                      String name=names.get(i).toLowerCase(java.util.Locale.ROOT);
                      for (String term : terms) {
                          if (name.contains(term.toLowerCase(java.util.Locale.ROOT))) {
                              mNajmIndex=i;
                              mNajmBrowse.navigateFromTopBar(i);
                              updateNajmChipSelection();
                              return;
                          }
                      }
                  }
                  // Avoid a dead navigation button when a section is not configured.
                  mNajmBrowse.showNavigationFromTopBar();
              }
              private void updateNajmChipSelection() {''',1)
# match generated chip text with shorter, more compact Android mobile presentation
s=s.replace('chip.setTextSize(15);','chip.setTextSize(14);',1)
s=s.replace('chip.setPadding(24,0,24,0);','chip.setPadding(20,0,20,0);',1)
s=s.replace('new android.widget.LinearLayout.LayoutParams(-2,48)','new android.widget.LinearLayout.LayoutParams(-2,37)',1)
browse.write_text(s)

# YouTube-like player: main three controls in center, previous/next as small
# accessible actions alongside progress at the bottom. All existing handlers
# and identifiers are preserved.
player_xml=ROOT/"res/layout/fragment_playback.xml"
p=player_xml.read_text()
for control in ("najm_player_previous_video","najm_player_next_video"):
    pattern=r'<TextView\s+android:id="@\+id/'+control+r'"[\s\S]*?/>'
    hits=list(re.finditer(pattern,p))
    assert len(hits)==1,(control,len(hits))
    match=hits[0]
    original=match.group(0)
    p=p[:match.start()]+p[match.end():]
    # Resize these skip-to-video buttons for lower control strip
    replacement=re.sub(r'android:layout_width="48dp"', 'android:layout_width="46dp"',original)
    replacement=re.sub(r'android:layout_height="[^"]+"','android:layout_height="43dp"',replacement)
    marker='<TextView android:id="@+id/najm_player_options"'
    assert p.count(marker)==1
    p=p.replace(marker,replacement+'\n                      '+marker,1)
assert p.count('android:id="@+id/najm_player_center"')==1
assert p.count('android:id="@+id/najm_player_previous_video"')==1
assert p.count('android:id="@+id/najm_player_next_video"')==1
ET.fromstring(p)
player_xml.write_text(p)
# Package is unique, so old debug-signed forks (and golden-branded fork) are left
# installed without any signature collision.
gradle=Path("SmartTube/smarttubetv/build.gradle")
g=gradle.read_text()
assert g.count('applicationId "org.smarttube.najm"')==1
gradle.write_text(g.replace('applicationId "org.smarttube.najm"',
                            'applicationId "org.smarttube.najmv3"',1))
print("NAJM Tube V2.3: Android tablet-inspired home/search/rail, usable navigation and centered player.")
