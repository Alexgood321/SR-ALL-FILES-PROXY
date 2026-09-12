# Repository Safety and Architecture Rules

These rules apply to Codex and any automated coding agent working with this repository.

## Project purpose

This repository is an actively maintained Shadowrocket production configuration, not a static collection of copied rule lists.

The project continuously studies and maintains real-world routing, DNS, filtering, and service reachability behavior across different networks and devices. Work normally includes discovering service infrastructure, validating ownership and relevance, comparing it with current production policy, making narrowly scoped changes when justified, publishing them through stable delivery URLs, and then checking actual device/runtime behavior from PacketTunnel logs.

The repository also contains derived INCY routing artifacts generated from the canonical Shadowrocket policy. Those artifacts are a separate compatibility/native-policy layer. Their repository-level static validation must never be confused with Sub-Store delivery or INCY device/runtime E2E validation.

Core operating model:

1. Observe real behavior and monitor infrastructure changes.
2. Verify domains, IPs, CIDRs, ASNs, CDN/API/reachability endpoints and ownership using appropriate evidence.
3. Compare findings with current `DIRECT / PROXY / REJECT` and DNS policy.
4. Prefer minimal, service-specific rules over broad speculative masks.
5. Change production only when there is a clear routing/DNS reason and understood blast radius.
6. Validate static configuration and release delivery separately.
7. Validate actual Shadowrocket/device behavior separately through runtime evidence when needed.
8. Preserve a clear distinction between confirmed facts, inference, unverified areas, and hypotheses.

The goal is predictable and maintainable network behavior, not maximum rule count. A new source, newly discovered endpoint, or rule-set entry is a discovery signal, not automatically a reason to add a rule.

DNS is treated as part of the routing architecture. `remote.conf` owns the global DNS baseline; Unified can selectively assign System DNS through `[Host]`. Runtime retry/fallback behavior may be documented when observed, but a single PacketTunnel event must not be promoted into a universal Shadowrocket guarantee.

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

The dedicated INCY generated-artifact sync workflow is the narrow exception to that read-only rule: it may regenerate and commit only the derived INCY artifacts that its generator owns. It must not mutate canonical Shadowrocket sources, generators, tests, documentation, or unrelated repository files.

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
- INCY generator/tests/Xray validation PASS = repository-level native policy generation is internally valid only;
- none of the above = Shadowrocket or INCY runtime/device E2E PASS.

Runtime/device behavior must be stated as unverified until it is actually tested on the relevant device/client path.

When a change can affect DNS, first-match routing, module priority, deep links, generated INCY policy, or application behavior, explicitly separate:

- confirmed facts;
- inference;
- unverified areas;
- hypotheses.

## 7. Documentation consistency

When architecture changes, update the relevant documentation in the same work where practical:

- `README.md` for user-facing repository architecture and stable import links;
- module header/description and internal comments when module responsibility changes;
- `AGENTS.md` when an architectural invariant for future automation changes;
- INCY conversion reports through their generators, never by hand.

Do not leave README or agent instructions claiming that Unified contains REJECT/ad blocking after those rules have been moved to the optional Ads module.

Human-readable generated INCY reports under `incy/` should be written in Russian. Keep exact technical identifiers, protocol names, JSON field names, Xray/INCY terms, and machine-readable status codes unchanged when translation would break precision or tooling.

## 8. GitHub Pages / Shadowrocket deep links

`docs/redirect.html` is the repository's first-party HTTPS bridge for Shadowrocket deep links. GitHub Pages must publish it from `main:/docs`.

User-facing install buttons in `README.md` should use only:

`https://alexgood321.github.io/SR-ALL-FILES-PROXY/redirect.html`

Do not reintroduce LOWERTOP or other third-party redirect services unless the user explicitly decides to migrate away from the first-party redirect.

The redirect must remain closed, not generic:

- accept only supported `shadowrocket://` deep-link forms used by this project;
- accept only the stable production assets of `Alexgood321/SR-ALL-FILES-PROXY`;
- reject arbitrary external destinations and unsupported schemes;
- do not turn it into a general-purpose open redirect;
- do not add analytics, third-party scripts, or unrelated network dependencies without an explicit decision.

Changes to `docs/redirect.html`, its allowed asset list, GitHub Pages source, or README deep-link URLs are user-facing delivery changes. Verify the Pages URL and at least one representative deep link separately from release-asset validation. A working GitHub Pages redirect does not by itself prove that Shadowrocket accepted/imported the target on a device.

## 9. INCY derived routing architecture

INCY support is currently split into a repository/static-policy layer and a later Sub-Store delivery/runtime layer. Do not collapse those layers into one PASS state.

### Canonical inputs

The canonical routing inputs for INCY generation are:

- `config/remote.conf`
- `modules/Unified-Routing-System-DNS.sgmodule`
- `modules/Ads-Privacy-Block.sgmodule`

YouTube Rewrite/Script/MITM files are not INCY routing sources and must not be pulled into the INCY generators unless the architecture is explicitly changed.

### Generators

`scripts/generate_incy_routing.py` and `scripts/generate_incy_xray_policy.py` are the source of truth for derived INCY files.

Generated artifacts must not be edited manually. Change the generator and tests, regenerate, then verify the resulting diff.

The current generated files are:

- `incy/incy-routing.json` — legacy/compatibility/diagnostic routing-profile representation;
- `incy/conversion-report.md` — human-readable report for the legacy/compatibility conversion;
- `incy/xray-policy.json` — credential-free native Xray `dns` + `routing` policy intended for later embedding into INCY Full Xray server configs;
- `incy/xray-conversion-report.md` — human-readable report for the native Xray conversion.

`incy/xray-policy.json` must remain credential-free. UUIDs, passwords, private/public keys, short IDs, server credentials, or other subscription secrets must never be written into this repository artifact.

### Full Xray policy boundaries

The native Xray artifact contains routing/DNS policy only. It does not by itself provide:

- VLESS/Trojan/VMess server credential conversion into proxy outbounds;
- Sub-Store fetch/cache/LKG/fail-safe behavior;
- INCY client detection or HTTP subscription headers;
- autorouting delivery headers;
- proof that no separate Routing Profile appears in the INCY UI;
- iOS/Android/Desktop runtime parity;
- HAPP or Shadowrocket regression proof.

Those belong to the later Sub-Store/Alpha delivery stage and require their own E2E evidence.

### Semantic mapping rules

Do not claim 1:1 parity where the clients expose different semantics.

In particular:

- Shadowrocket `tun-excluded-routes` excludes a network from TUN; INCY `DirectIp` or Xray `direct/freedom` only routes traffic DIRECT inside the client. This must be classified as `SEMANTIC ADAPTATION` / semantic gap, never `CONFIRMED STATIC MAPPING` or full TUN parity.
- Shadowrocket `no-resolve` has no identical native Xray/standard INCY routing modifier under the current conversion. Preserve the CIDR routing target but keep the semantic gap explicit.
- selective `[Host] ... = server:system` is not equivalent to static `DnsHosts`. The native Xray policy may adapt selective System DNS through Xray DNS domain routing, but runtime DNS parity remains unverified until INCY E2E.
- `USER-AGENT` must not be approximated as a safe 1:1 Xray rule for general HTTPS/application traffic; keep it `NOT PORTED / REQUIRES E2E` unless independently solved.
- `PROCESS-NAME` may be native in Xray on some desktop platforms but remains `PLATFORM_DEPENDENT` for INCY Android/iOS until tested.
- logical or protocol-qualified Shadowrocket rules may be ported only when the generator preserves their actual selector semantics. Never flatten them merely to increase conversion coverage.

### CI and generated sync

`.github/workflows/validate-incy-routing.yml` validates the repository/static conversion layer. Relevant checks include generator consistency, tests, write-scope protection, and native Xray config validation with Xray-core.

`.github/workflows/sync-incy-routing.yml` regenerates and publishes derived INCY artifacts after relevant `main` changes. Its repository write scope must remain limited to generated `incy/` outputs.

If a generator changes in a pull request, PR validation must regenerate the derived artifacts before comparing/validating them; otherwise the CI can incorrectly fail simply because checked-in generated files still reflect the previous generator.

A successful sync commit only proves that the generated repository artifacts were refreshed successfully. It does not prove Sub-Store delivery, HTTP headers, INCY import, INCY runtime DNS/routing behavior, or client E2E.

## 10. INCY change workflow

For changes affecting INCY conversion:

1. Identify whether the change belongs to canonical Shadowrocket policy, conversion logic, or later Sub-Store delivery.
2. Do not modify canonical Shadowrocket behavior merely to make INCY conversion easier.
3. Update the relevant generator instead of hand-editing generated `incy/` files.
4. Add or update focused regression tests for the semantic behavior being changed.
5. Regenerate both affected JSON/report artifacts.
6. Verify that generator write scope touches only expected generated files.
7. Run the INCY conversion tests and Xray-core config validation.
8. Review the generated reports for unsupported rules, semantic gaps, duplicates, and coverage changes.
9. Keep repository-static PASS separate from future Sub-Store/INCY E2E status.
10. After merge, verify that the generated sync workflow refreshed `main` and that the resulting generated files match the new generator behavior.
