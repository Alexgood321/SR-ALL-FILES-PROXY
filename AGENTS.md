# Repository Git Safety

These rules apply to Codex and any automated coding agent working with this repository.

## Safe push rule

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

The GitHub Actions publication workflow is read-only with respect to repository contents. It must never commit, push, rewrite delivery files, or manufacture timestamp commits.
