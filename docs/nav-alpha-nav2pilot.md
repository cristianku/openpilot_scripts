# nav-alpha per Nav2Pilot

Le app Nav2Pilot (Android `nav2pilot`, iOS `nav2pilot-ios`) mandano al comma la destinazione con i waypoint e il
token Mapbox dell'utente. Il Nav Alpha di comma (PR commaai/openpilot#39066) e' gia' nel master di commaai e di
sunnypilot, ma conosce solo `setNavDestination(latitude, longitude)` e usa il proxy `/v1/nav` di comma, che rifiuta
il JWT dell'utente. Per questo teniamo due branch `nav-alpha`:

| fork | clone locale | parte da | branch |
|---|---|---|---|
| `cristianku/sunnypilot` | `CRISTIANKU/sunnypilot-nav-alpha` | `sunnypilot/sunnypilot:master` (remote `upstream`) | `nav-alpha` |
| `cristianku/openpilot` | `CRISTIANKU/openpilot-nav-alpha` | `commaai/openpilot:master` (remote `commaai`) | `nav-alpha` |

Regola: ogni branch e' **master + un solo commit** con le nostre modifiche. Il codice nuovo vive in file nuovi; i
file upstream si toccano il minimo indispensabile. Le modifiche sono salvate come patch in
`OP-apply-nav-alpha/patches/` e la skill `OP-apply-nav-alpha` le riapplica su un master fresco.

## Cosa aggiungiamo

### Le due RPC (athena, e su sunny anche sunnylink: stesso dispatcher)

```text
setNavRoute(latitude, longitude, waypoints=None)
  waypoints: [{"latitude": .., "longitude": .., "via": false}, ...]   in ordine di guida, max 20
  -> scrive il param NavDestination: {"latitude", "longitude", "waypoints": [...]}

setMapboxToken(token)
  token pubblico "pk...."; "" lo cancella (navd torna al proxy di comma)
  -> param MapboxToken (PERSISTENT | DONT_LOG); non riscrive se e' uguale
```

`NavDestination` resta valido per il navd di comma: legge solo `latitude`/`longitude` e ignora `waypoints`.

- stop (`"via": false`) = waypoint Mapbox: una leg per stop, l'arrivo viene annunciato
- via (`"via": true`) = punto silenzioso che forma il percorso (cosi' si segue l'alternativa scelta sul telefono)

### Il navd con waypoint e token

`Nav2PilotRouteEngine` (comma) / `RouteEngineSP` (sunny) **eredita** `RouteEngine` dal navd upstream:

- senza waypoint e senza token salvato si comporta esattamente come upstream (chiama `super()`)
- `select_mapbox_token()`: prima di ogni richiesta usa il `MapboxToken` del telefono e va diretto su
  `api.mapbox.com`; senza token tiene la scelta upstream (variabile `MAPBOX_TOKEN`, altrimenti proxy comma)
- `recompute_route()`: come upstream ma ricalcola anche quando cambiano i waypoint
- `drop_passed_waypoints()`: un waypoint a meno di 50 m e' superato e viene tolto anche dal param
- `calculate_route()`: **copia** di quella upstream con in piu' i waypoint nella richiesta
  (`waypoints=` con gli indici di leg, una `bearings` per coordinata) e `leg_steps()` che unisce le leg
  togliendo gli "arrive" intermedi
- `clear_route()`: upstream + azzera i waypoint

Attenzione: se upstream cambia `calculate_route`, `recompute_route` o `clear_route` in
`openpilot/selfdrive/navigation/navd.py`, la patch puo' applicarsi pulita ma il nostro override resta vecchio.
`OP-apply-nav-alpha status` elenca i commit upstream su quel file: vanno letti e riportati nel nostro codice.

## File, per fork

### comma (`openpilot/selfdrive/navigation/nav2pilot/`)

| file | cosa |
|---|---|
| `__init__.py` | vuoto |
| `athena.py` | `setNavRoute`, `setMapboxToken` sul dispatcher di athena |
| `mapbox.py` | `MAPBOX_TOKEN_PARAM`, `MAPBOX_HOST`, validazione token `pk.` (niente numpy: lo importa athenad) |
| `waypoints.py` | parse/validazione waypoint, lettura/scrittura nel param (niente numpy) |
| `navd.py` | `Nav2PilotRouteEngine` + `main()` |
| `tests/test_navd_waypoints.py`, `tests/test_navd_mapbox.py` | test |

Tocchi upstream (3 righe):

```text
openpilot/system/athena/athenad.py         + import openpilot.selfdrive.navigation.nav2pilot.athena  # noqa: F401
openpilot/system/manager/process_config.py   navd -> "openpilot.selfdrive.navigation.nav2pilot.navd"
openpilot/common/params_keys.h             + {"MapboxToken", {PERSISTENT | DONT_LOG, STRING}},
```

### sunny (`openpilot/sunnypilot/navd/`)

Stessi file di comma (con header sunnypilot, modulo `openpilot.sunnypilot.navd`, classe `RouteEngineSP`), piu':

| file | cosa |
|---|---|
| `destination.py` | parse/format di "lat, lon" per l'inserimento destinazione sul device |
| `tests/test_nav_alpha.py` | test di integrazione sunnypilot (Api, UI, process_config, sunnylink, destinazione) |
| `selfdrive/ui/sunnypilot/mici/widgets/nav_destination.py` | bottone "nav destination" nelle impostazioni developer |

`helpers.py` in quella cartella e' di sunnypilot upstream, non nostro.

Tocchi upstream:

```text
openpilot/system/athena/athenad.py          + import openpilot.sunnypilot.navd.athena  # noqa: F401
openpilot/system/manager/process_config.py    navd -> "openpilot.sunnypilot.navd.navd"
openpilot/common/params_keys.h              + MapboxToken (solo questa: NavigationEnabled e NavDestination
                                              sono gia' nel master)
openpilot/common/api/__init__.py            + __all__ e property dongle_id: tiles.py di comma usa
                                              api.dongle_id, l'Api di sunnypilot non ce l'ha
openpilot/selfdrive/ui/mici/onroad/torque_bar.py   min(1.0, rect.width / 476): la TorqueBar mici e' condivisa
                                              con la UI tici di sunnypilot (scale=3), senza min() si allarga
openpilot/selfdrive/ui/mici/layouts/settings/developer.py   + NavDestinationButton() dopo il toggle navigation
```

Le due versioni del pacchetto devono restare uguali: `OP-apply-nav-alpha sunny sync-check` le confronta
(differenze ammesse: solo le righe su sunnylink).

## Riallineare al master (skill `OP-apply-nav-alpha`)

```bash
S=/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/OP-apply-nav-alpha/scripts/apply_nav_alpha.sh
$S sunny status      # cosa e' cambiato upstream, la patch si applica?
$S sunny apply       # backup nav-alpha-prev, nav-alpha = master + patch, controlli, commit locale
$S sunny push        # solo con l'ok di Cristian (--force-with-lease)
```

Uguale con `comma`. Dopo il push la sorgente e' pronta per `OP-setup-psa-torque(-testing) <variante> nav-alpha`.

### Se ci sono conflitti

Si tiene **sempre** il codice nuovo di upstream e si rimettono sopra solo le nostre righe:

- `athenad.py`: la riga `import ...athena  # noqa: F401` dopo gli import di `system.athena.rpc`
- `process_config.py`: nella riga `PythonProcess("navd", ...)` di upstream si cambia solo il modulo (se upstream
  aggiunge argomenti, es. `enabled=`, si tengono)
- `params_keys.h`: solo `MapboxToken`, in ordine alfabetico; se upstream la aggiunge, la nostra va tolta
- `api/__init__.py` (sunny): se sunnypilot aggiunge `dongle_id` da solo, la nostra property va tolta
- `torque_bar.py` (sunny): se upstream cambia la formula dello span, riapplicare il `min(1.0, ...)`
- `developer.py` (sunny): `NavDestinationButton()` subito dopo `self._navigation_toggle`

Poi `git add` dei file e `$S <variante> commit`. Se il codice nostro e' cambiato: `$S <variante> save-patch`,
stessa modifica sull'altra variante, `sync-check`.

### Se upstream cambia `navd.py`

Leggere i commit indicati da `status` e riportare la modifica in `calculate_route` (e negli altri override) del
nostro `navd.py`, in entrambi i fork; poi `save-patch` per tutti e due e `sync-check`.

### Se upstream integra waypoint o token

Se comma/sunnypilot aggiungono un loro modo di passare waypoint o token Mapbox, la patch va ridotta (o tolta) e le
app adattate: non tenere due meccanismi.

## Storia

- 2026-10-12 comma merge di Nav Alpha (#39066). 2026-10-17 port su sunnypilot `feature/nav-alpha` (9 commit).
- 2026-10-18 `cristianku/openpilot:nav-alpha` da commaai master + `nav2pilot/`.
- 2026-10-18 sunnypilot master integra Nav Alpha di comma (sync #2059); il 2026-10-20 `nav-alpha` di sunny
  viene allineato con un merge (`837ba52c1a`), il vecchio `feature/nav-alpha` resta indietro.
- 2026-10-20 patch salvate in `OP-apply-nav-alpha/patches/` (base: sunny `922513f312`, comma `2ab952d5eb`).
  Tolti due residui dei vecchi branch: in sunny `NavigationEnabled`/`NavDestination` comparivano due volte in
  `params_keys.h` dopo il merge; in comma il commit `2e98c8aed` spostava `msgq_repo` rispetto a master.
