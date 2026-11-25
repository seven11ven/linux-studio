# Build summary: Linux-Studio-debian-amd64-0.1.0~dev1

- **Type:** dev build
- **Package:** `linux-studio_0.1.0~dev1-2_amd64.deb` (448M, installed size 2041 MB)
- **SHA-256:** `07c37cc494e82f5857573f2290c7cfb45640a5a6f6ebd14ebfb706a99a3a4bb0`
- **Built:** 2026-11-25T18:55Z from git commit `59f28ea` (with uncommitted changes)
- **Editor:** Code - OSS 1.148.0, run 45640173838, sha256 `faa5cee2ad2cd9f8…`
- **Runtime:** Linux Studio runtime: Debian trixie, built 2026-11-25T18:31Z
- **Depends:** bubblewrap, python3, python3-gi, gir1.2-gtk-4.0, apparmor

> **Superseded by revision 3. Don't install.** Packaging is correct (all folders 0755), but its AppArmor profile gives an unrestricted
> bwrap copy the user-namespace permission, which any local program could use to get around Ubuntu's restriction (security review, Medium-High).
> Revision 3 uses Ubuntu's restricted design instead. Kept because the guidelines don't allow deleting builds without the PM's permission.
