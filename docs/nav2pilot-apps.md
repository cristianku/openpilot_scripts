# Nav2Pilot apps (Android + iOS)

Repos: `nav2pilot` (Android) and `nav2pilot-ios`. The openpilot side is in [nav-alpha-nav2pilot.md](nav-alpha-nav2pilot.md).

## iOS UI tests change the simulator data
The nav2pilot-ios UI tests (testScreenshotTour, testTypedCoordinates...) add/remove favorites in the App Group defaults of Cristian's simulator (iPhone 16 Pro iOS 18.5, D25EB33A), which also holds a stored demo car and demo favorites.

**Why:** on 2026-10-20 a baseline run of the original testScreenshotTour (Favorites tapped with the destination panel still open) matched the panel title with `staticTexts[...].firstMatch`, swiped the first sheet row and deleted the demo favorite "Autodromo di Monza — Via Vedano 5, 20900 Monza, Italy" (no backup, not restored). The test also expects zero favorites, so it fails on that simulator anyway.

**How to apply:** before running UI tests on that simulator, list favorite names (`plutil -extract favorites raw` on the app-group plist, names only) and compare after; avoid re-running the old testScreenshotTour. For landscape screenshots, `app.screenshot()` is garbled: use a `simctl io screenshot` loop with timestamp markers and rotate with `sips -r 270`.
