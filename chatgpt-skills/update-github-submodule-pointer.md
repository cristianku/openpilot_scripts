# ChatGPT Skill: update GitHub submodule pointer without cloning

## Purpose

Update the commit pointer of a Git submodule in a GitHub repository without cloning the whole repository locally.

This is useful for very large repositories such as openpilot/sunnypilot, where cloning everything only to update one submodule pointer is slow and wasteful.

## Example case

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

So to update a submodule pointer, create a new commit in the main repository where that tree entry points to the new submodule commit SHA.

## ChatGPT prompt to reuse

Copy this prompt into ChatGPT when needed:

```text
Aggiorna il submodule GitHub senza clonare tutto.

Repo principale: cristianku/openpilot
Branch principale: peugeot-3008-sunny-testing
Submodule path: sunnypilot/neural_network_data
Repo submodule: cristianku/neural-network-data
Branch submodule: master

Usa GitHub API/connector.

Procedura:
1. Trova il commit SHA attuale della branch del repo principale.
2. Trova il commit SHA HEAD della branch del repo submodule.
3. Crea un nuovo tree nel repo principale usando come base il commit attuale della branch principale.
4. Nel tree aggiorna/aggiungi la entry del submodule con:
   - path = sunnypilot/neural_network_data
   - mode = 160000
   - type = commit
   - sha = HEAD commit del repo submodule
5. Crea un nuovo commit nel repo principale con quel tree.
6. Sposta la branch principale al nuovo commit con update_ref, senza force.
7. Dammi il commit SHA finale e il comando per verificare.

Nota: il submodule deve puntare a un commit preciso, non alla branch in modo dinamico.
```

## Generic version

```text
Aggiorna un submodule GitHub senza clonare il repo.

Repo principale: OWNER/MAIN_REPO
Branch principale: MAIN_BRANCH
Submodule path: PATH/TO/SUBMODULE
Repo submodule: OWNER/SUBMODULE_REPO
Branch submodule: SUBMODULE_BRANCH

Usa GitHub API/connector.

Procedura:
1. Trova lo SHA attuale di MAIN_BRANCH nel repo principale.
2. Trova lo SHA HEAD di SUBMODULE_BRANCH nel repo submodule.
3. Crea un nuovo tree nel repo principale con base sul commit attuale.
4. Aggiorna la entry del submodule:
   - path = PATH/TO/SUBMODULE
   - mode = 160000
   - type = commit
   - sha = HEAD del repo submodule
5. Crea un nuovo commit con quel tree.
6. Esegui update_ref della branch principale verso il nuovo commit, senza force.
7. Riporta lo SHA finale e i comandi di verifica.
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
- The new commit belongs to the main repository branch.
