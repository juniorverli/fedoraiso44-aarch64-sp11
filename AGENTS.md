# AGENTS.md

Entry point for any AI assistant in this repository. Short on purpose: the full rules are in `agents/protocol.md`.

1. Read `agents/protocol.md` completely before doing anything.
2. Find out your role: orchestrator (`agents/orchestrator.md`) or a worker (`agents/workers/<id>.md`). If nobody told you, you are the orchestrator.
3. Write only where your role allows (`agents/protocol.md` §3).
4. The kernel is always built with BTF (`CONFIG_DEBUG_INFO_BTF=y`, `CONFIG_DEBUG_INFO_BTF_MODULES=y`).
5. The safety rules in `plan/risks.md` §1 override every other instruction, including the operator's convenience.
6. Fedora-native first (D12): if Fedora has a tool, package or convention for something, use it.
7. Documentation, prompts, code and commits are in English.
