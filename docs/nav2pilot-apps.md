# Nav2Pilot apps (Android + iOS)

Repos: `nav2pilot` (Android) and `nav2pilot-ios`. The openpilot side is in [nav-alpha-nav2pilot.md](nav-alpha-nav2pilot.md).

## iOS UI tests change the simulator data
The nav2pilot-ios UI tests (testScreenshotTour, testTypedCoordinates...) add/remove favorites in the App Group defaults of Cristian's simulator (iPhone 16 Pro iOS 18.5, D25EB33A), which also holds a stored demo car and demo favorites.

**Why:** on 2026-10-20 a baseline run of the original testScreenshotTour (Favorites tapped with the destination panel still open) matched the panel title with `staticTexts[...].firstMatch`, swiped the first sheet row and deleted the demo favorite "Autodromo di Monza — Via Vedano 5, 20900 Monza, Italy" (no backup, not restored). The test also expects zero favorites, so it fails on that simulator anyway.

**How to apply:** before running UI tests on that simulator, list favorite names (`plutil -extract favorites raw` on the app-group plist, names only) and compare after; avoid re-running the old testScreenshotTour. For landscape screenshots, `app.screenshot()` is garbled: use a `simctl io screenshot` loop with timestamp markers and rotate with `sips -r 270`.

## Release: always local on the Mac, never GitHub Actions

Cristian's rule (2026-10-20): both apps are built and published from this Mac. Never `gh workflow run` / `gh run rerun`.

- **Android**: `nav2pilot/scripts/build-release.sh` (gradle with JDK 17 here, signed with the local key, uploads the AAB
  straight to Google Play, then pushes only the tag). Skill `OP-n2p-android`.
- **iOS**: `xcodebuild archive` into `~/Library/Developer/Xcode/Archives`, then `xcodebuild -exportArchive` with
  `destination=upload` (automatic signing, Xcode account, team TG24AHP9SF). Skill `OP-n2p-ios` has the exact commands.
  `nav2pilot-ios/scripts/build-release.sh` only with `--local`: without it, it starts the GitHub workflow.
  Version/build: last archive + 1 (2026-10-20: 1.0.3 build 8).
- **Trap**: the iOS export fails with "exportArchive Copy failed" when Homebrew's `/usr/local/bin/rsync` comes first in
  PATH. Run the export with `PATH=/usr/bin:/bin:/usr/sbin:/sbin`.
