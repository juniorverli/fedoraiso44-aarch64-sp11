# bluetooth worker

**Owns:** `hardware/bluetooth/` (write). Everything else is read-only.
**Phase:** 2. **Kernel worktree:** no.

## Start

1. Read `hardware/bluetooth/README.md`, `component.toml` and the dossiers in `depends_on`.
2. Work the dossier's open questions in order (`agents/protocol.md` §9).
3. Fill the Role column of the dossier's Windows table for every package you open.

## Mission

Bluetooth working with the right NVM and a stable address.

## Specific leads

- `sources/linux/drivers/bluetooth/btqca.c`: NVM file naming for WCN7850 and the board ID lookup.
- `qcbluetooth8380.inf`: which `hmtnv20.*` file Windows selects for this board.

## Deliver

Firmware request, `test-plan.md` (`bluetoothctl show`, pairing), dossier updated.
