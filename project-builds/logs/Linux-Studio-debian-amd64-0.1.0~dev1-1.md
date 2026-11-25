# Build summary: Linux-Studio-debian-amd64-0.1.0~dev1

- **Type:** dev build
- **Package:** `linux-studio_0.1.0~dev1-1_amd64.deb` (448M, installed size 2041 MB)
- **SHA-256:** `f68f19f0f038eebbf23abdf26f36a2f4eb6eb1bb2d00e2d6515b9cfc63ed3af6`
- **Built:** 2026-11-25T18:50Z from git commit `59f28ea` (with uncommitted changes)
- **Editor:** Code - OSS 1.148.0, run 45640173838, sha256 `faa5cee2ad2cd9f8…`
- **Runtime:** Linux Studio runtime: Debian trixie, built 2026-11-25T18:31Z
- **Depends:** bubblewrap, python3, python3-gi, gir1.2-gtk-4.0, apparmor

> **⚠ Revision 1 is defective. Do not install it.** Several folders were packaged with permissions 0754 (`drwxr-xr--`), so ordinary
> users can't open `/opt/linux-studio/share` (the launcher). Found while inspecting the package. The build script now sets 0755 on all folders.
> The fixed package is **revision 2** (`linux-studio_0.1.0~dev1-2_amd64.deb`, summary below). Revision 1 is kept because the guidelines don't allow deleting builds without the PM's permission.
