# ChatGPT Skill: Peugeot 3008 Sunny testing - update neural_network_data submodule pointer

## Purpose

Update the `sunnypilot/neural_network_data` submodule pointer in:

```text
cristianku/openpilot:peugeot-3008-sunny-testing
```

so it points to the latest commit of:

```text
cristianku/neural-network-data:master
```

without cloning the whole openpilot repository locally.

This is useful because openpilot/sunnypilot is large and updating one submodule pointer does not require downloading everything.

## Exact case

Main repository:

```text
cristianku/openpilot
```

Main repository branch:

```text
peugeot-3008-sunny-testing
```

Submodule path inside the main repository:

```text
sunnypilot/neural_network_data
```

Submodule repository:

```text
cristianku/neural-network-data
```

Submodule branch:

```text
master
```

## Important Git concept

A Git submodule does **not** dynamically point to a branch.

It points to one exact commit SHA.

Inside a Git tree, a submodule is stored as:

```text
mode = 160000
type = commit
sha  = commit SHA of the submodule repository
path = submodule path inside the main repository
```

So to update this submodule pointer, create a new commit in `cristianku/openpilot` on branch `peugeot-3008-sunny-testing` where the tree entry `sunnypilot/neural_network_data` points to the new commit SHA from `cristianku/neural-network-data:master`.

## ChatGPT prompt to reuse

Copy this prompt into ChatGPT when needed:

```text
Aggiorna il submodule neural_network_data per Peugeot 3008 Sunny testing senza clonare tutto.

Repo principale: cristianku/openpilot
Branch principale: peugeot-3008-sunny-testing
Submodule path: sunnypilot/neural_network_data
Repo submodule: cristianku/neural-network-data
Branch submodule: master

Usa GitHub API/connector.

Procedura:
1. Trova il commit SHA attuale della branch cristianku/openpilot:peugeot-3008-sunny-testing.
2. Trova il commit SHA HEAD di cristianku/neural-network-data:master.
3. Crea un nuovo tree nel repo cristianku/openpilot usando come base il commit attuale della branch peugeot-3008-sunny-testing.
4. Nel tree aggiorna/aggiungi la entry del submodule con:
   - path = sunnypilot/neural_network_data
   - mode = 160000
   - type = commit
   - sha = HEAD commit di cristianku/neural-network-data:master
5. Crea un nuovo commit nel repo cristianku/openpilot con quel tree.
6. Sposta la branch peugeot-3008-sunny-testing al nuovo commit con update_ref, senza force.
7. Dammi il commit SHA finale e il comando per verificare.

Nota: il submodule deve puntare a un commit preciso, non alla branch in modo dinamico.
```

## Manual verification commands

After the update, on a local checkout:

```bash
git fetch origin
git checkout peugeot-3008-sunny-testing
git pull origin peugeot-3008-sunny-testing
git submodule status sunnypilot/neural_network_data
```

Expected result: the submodule path should show the exact new commit SHA from `cristianku/neural-network-data:master`.

## Notes

- Do not use `force=true` unless explicitly needed.
- Do not modify `.gitmodules` unless the submodule repository URL itself must change.
- Updating the submodule pointer changes the main repository, not the submodule repository.
- The new commit belongs to `cristianku/openpilot:peugeot-3008-sunny-testing`.
