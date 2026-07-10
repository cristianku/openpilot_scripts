# ChatGPT Skill: Peugeot 3008 Sunny testing - update submodule pointers

## Purpose

Update both submodule pointers in:

- `cristianku/openpilot:psa-torque-sunny-testing`

Target pointers:

- `sunnypilot/neural_network_data` -> latest commit of `cristianku/neural-network-data:master`
- `opendbc_repo` -> latest commit of `cristianku/opendbc:psa-torque-sunny-testing`

Do this without cloning the whole openpilot repository locally.

This is useful because openpilot/sunnypilot is large and updating submodule pointers does not require downloading the full repository.

## Exact case

Main repository:

- Repo: `cristianku/openpilot`
- Branch: `psa-torque-sunny-testing`

Submodule pointer 1:

- Path: `sunnypilot/neural_network_data`
- Repo: `cristianku/neural-network-data`
- Branch: `master`

Submodule pointer 2:

- Path: `opendbc_repo`
- Repo: `cristianku/opendbc`
- Branch: `psa-torque-sunny-testing`

## Important Git concept

A Git submodule does not dynamically point to a branch. It points to one exact commit SHA.

Inside a Git tree, a submodule is stored as:

- mode: `160000`
- type: `commit`
- sha: commit SHA of the submodule repository
- path: submodule path inside the main repository

So to update these submodule pointers, create a new commit in `cristianku/openpilot` on branch `psa-torque-sunny-testing` where:

- `sunnypilot/neural_network_data` points to HEAD of `cristianku/neural-network-data:master`
- `opendbc_repo` points to HEAD of `cristianku/opendbc:psa-torque-sunny-testing`

## ChatGPT prompt to reuse

Copy this prompt into ChatGPT when needed:

```text
Aggiorna i submodule pointers per Peugeot 3008 Sunny testing senza clonare tutto.

Repo principale: cristianku/openpilot
Branch principale: psa-torque-sunny-testing

Submodule 1:
- path: sunnypilot/neural_network_data
- repo: cristianku/neural-network-data
- branch: master

Submodule 2:
- path: opendbc_repo
- repo: cristianku/opendbc
- branch: psa-torque-sunny-testing

Usa GitHub API/connector.

Procedura:
1. Trova il commit SHA attuale della branch cristianku/openpilot:psa-torque-sunny-testing.
2. Trova il commit SHA HEAD di cristianku/neural-network-data:master.
3. Trova il commit SHA HEAD di cristianku/opendbc:psa-torque-sunny-testing.
4. Crea un nuovo tree nel repo cristianku/openpilot usando come base il commit attuale della branch psa-torque-sunny-testing.
5. Nel tree aggiorna/aggiungi entrambe le entry dei submodule:

   Entry 1:
   - path = sunnypilot/neural_network_data
   - mode = 160000
   - type = commit
   - sha = HEAD commit di cristianku/neural-network-data:master

   Entry 2:
   - path = opendbc_repo
   - mode = 160000
   - type = commit
   - sha = HEAD commit di cristianku/opendbc:psa-torque-sunny-testing

6. Crea un nuovo commit nel repo cristianku/openpilot con quel tree.
7. Sposta la branch psa-torque-sunny-testing al nuovo commit con update_ref, senza force.
8. Dammi il commit SHA finale e i comandi per verificare.

Nota: i submodule devono puntare a commit precisi, non alle branch in modo dinamico.
```

## Manual verification commands

After the update, on a local checkout:

```bash
git fetch origin
git checkout psa-torque-sunny-testing
git pull origin psa-torque-sunny-testing

git submodule status sunnypilot/neural_network_data
git submodule status opendbc_repo
```

Expected result:

- `sunnypilot/neural_network_data` should show the HEAD commit SHA from `cristianku/neural-network-data:master`.
- `opendbc_repo` should show the HEAD commit SHA from `cristianku/opendbc:psa-torque-sunny-testing`.

## Optional precise verification without local checkout

You can also verify through GitHub API by reading the tree entry from the resulting commit/tree:

- `sunnypilot/neural_network_data` -> mode `160000`, type `commit`, sha = neural-network-data HEAD
- `opendbc_repo` -> mode `160000`, type `commit`, sha = opendbc HEAD

## Notes

- Do not use `force=true` unless explicitly needed.
- Do not modify `.gitmodules` unless the submodule repository URL itself must change.
- Updating submodule pointers changes the main repository, not the submodule repositories.
- The new commit belongs to `cristianku/openpilot:psa-torque-sunny-testing`.
- If only one of the two pointers is outdated, still create a single main-repo commit only if at least one tree entry actually changes.
