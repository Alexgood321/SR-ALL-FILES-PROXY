# Repository Safety and Architecture Rules

These rules apply to Codex and any automated coding agent working with this repository.

## 1. Safe push rule

Before every push to `main`:

1. Run `git fetch origin main`.
2. Check whether `origin/main` advanced since the work started.
3. If it advanced, do not overwrite it and do not force push.
4. Rebase or merge safely, then inspect the resulting diff again.
5. Re-run the relevant validation.
6. Push normally.

If a push is rejected as non-fast-forward:

- never use `git push --force` or `git push --force-with-lease`;
- fetch `origin/main` again;
- reconcile the local branch with the remote branch;
- verify that parallel changes are still present;
- validate again;
- retry with a normal push.

## 2. Production delivery invariants

Do not rename, remove, or replace the stable production delivery asset names or their `releases/latest/download/...` structure unless the user explicitly requests a migration.

Stable production assets include:

- `remote.conf`
- `Unified-Routing-System-DNS.sgmodule`
- `Ads-Privacy-Block.sgmodule`
- `Youtube-Config.sgmodule`
- `RU-TLD-RU-Non-RU-DIRECT-System-DNS.sgmodule` while it remains published as a legacy/standalone asset

Existing devices may already reference these stable URLs. Prefer changing release contents while keeping stable asset names and URLs unchanged.

The GitHub Actions publication workflow is read-only with respect to repository contents. It must never commit, push, rewrite repository files, or manufacture timestamp commits. Release publication and delivery verification are separate from repository mutation.

## 3. Current architecture boundaries

### `config/remote.conf`

Owns the global/base Shadowrocket configuration, including the default DNS path, `GEOIP,RU,DIRECT`, `FINAL,PROXY`, TUN/network parameters, and the stable config update URL.

Do not move service-specific routing or ad/privacy blocking into `remote.conf` without an explicit architectural decision.

### `modules/Unified-Routing-System-DNS.sgmodule`

This is the primary routing/DNS module.

It owns:

- service-specific `DIRECT` / `PROXY` routing;
- IP/CIDR routing used by those services;
- selective System DNS mappings in `[Host]`;
- RU TLD and selected RU non-RU routing already integrated into Unified.

It must not contain active advertising/privacy `REJECT`, `REJECT-200`, `REJECT-DICT`, `REJECT-ARRAY`, `REJECT-TINYGIF`, or `REJECT-VIDEO` rules. Those belong in `Ads-Privacy-Block.sgmodule`.

Do not reintroduce the old monolithic `DIRECT / PROXY / REJECT` architecture into Unified without an explicit user decision.

### `modules/Ads-Privacy-Block.sgmodule`

This is the optional ad/privacy blocking layer.

It owns advertising, analytics, tracker, and privacy-related REJECT rules. New ad/tracker blocking rules should normally be added here, not to Unified.

When used together in Shadowrocket, Ads + Privacy Block must be placed above Unified so its REJECT policies are evaluated before broader `PROXY` / `DIRECT` routing.

Treat broad rules such as global keywords or wide root-domain blocks as higher-risk changes. Document their expected scope and regression risk before enabling or expanding them.

### `modules/RU-TLD-RU-Non-RU-DIRECT-System-DNS.sgmodule`

This is a legacy/standalone alternative. Its routing/System DNS policy is already integrated into Unified.

Do not instruct users to enable it in parallel with Unified. Parallel use can create duplicate/overlapping rules and change first-match behavior.

### YouTube files

`modules/Youtube-Config.sgmodule` and `modules/youtube.response.js` remain a separate specialized YouTube layer.

Do not silently merge YouTube Rewrite/Script/MITM functionality into Unified or Ads + Privacy. Do not add YouTube to the Shadowrocket Setup Wizard unless the user explicitly changes that product decision.

## 4. First-match and module priority

Shadowrocket rule order matters. More specific rules should remain above broader rules within the same logical block when first-match affects behavior.

When changing module boundaries or rule order, inspect for overlaps with broader DOMAIN-SUFFIX, DOMAIN-KEYWORD, CIDR, PROXY, DIRECT, and REJECT rules. Do not assume source-text order alone proves runtime behavior across all Shadowrocket rule classes.

## 5. Audit trail requirements

For any change to Unified `[Rule]` or `[Host]` that can affect routing or DNS, update the module's internal audit trail with:

- date;
- affected service/domain/network;
- what changed;
- why it changed;
- expected impact/risk area;
- evidence source, such as official documentation, maintained rule-set, or runtime/PacketTunnel evidence.

For any material change to `Ads-Privacy-Block.sgmodule`, update that module's audit trail with the same level of detail, especially for broad or potentially application-breaking rules.

Preserve useful historical entries. Do not rewrite history merely to make the current file look cleaner.

## 6. Validation discipline

Never broaden a PASS beyond the exact layer that was checked.

Examples:

- validator PASS = static/syntax/implemented semantic checks only;
- release reconciliation PASS = published assets match the selected stable `main` delivery files;
- successful download = delivery path works and bytes match;
- none of the above = Shadowrocket runtime/device E2E PASS.

Runtime/device behavior must be stated as unverified until it is actually tested on the relevant device/client path.

When a change can affect DNS, first-match routing, module priority, deep links, or application behavior, explicitly separate:

- confirmed facts;
- inference;
- unverified areas;
- hypotheses.

## 7. Documentation consistency

When architecture changes, update the relevant documentation in the same work where practical:

- `README.md` for user-facing repository architecture and stable import links;
- module header/description and internal comments when module responsibility changes;
- `AGENTS.md` when an architectural invariant for future automation changes.

Do not leave README or agent instructions claiming that Unified contains REJECT/ad blocking after those rules have been moved to the optional Ads module.
