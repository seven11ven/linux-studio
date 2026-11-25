# Publisher signing keys (Toolchains explorer)

Used by `src/toolchains/worker.py` with `gpgv` to check that downloads really come from the publisher.
Binary OpenPGP keyrings. Inspect them with: `gpg --show-keys src/toolchains/keys/<file>.gpg`.
Collected and cross-checked on 2026-11-25. If a publisher rotates keys, update the file **and** this table, after checking the new
fingerprint against the publisher's official pages.

| File | Publisher | Primary key fingerprint(s) | Where the key / fingerprint is published |
|---|---|---|---|
| `node.gpg` | Node.js release team (8 active signers) | 5BE8A3F6C8A5C01D106C0AD820B1A390B168D356, DD792F5973C6DE52C432CBDAC77ABFA00DDBF2B7, CC68F5A3106FF448322E48ED27F5E38D5B0A215F, 890C08DB8579162FEE0DF9DB8BEAB4DFCF555EF4, C82FA3AE1CBEDC6BE46B9360C43CEC45C17AB93C, 108F52B48DB57BB0CC439B2997B01419BD92F80A, 655F3B5C1FB3FA8D1A0CA6BDE4A7D232B936D2FD, A363A499291CBBC940DD62E41F10027AF002F8B0 | 1) github.com/nodejs/node README, "Release keys". 2) github.com/nodejs/release-keys (`gpg-only-active-keys/pubring.kbx`) |
| `rust.gpg` | Rust (Tag and Release Signing Key) | 108F66205EAEB0AAA8DD5E1C85AB96E6FA1BE5FE | 1) static.rust-lang.org/rust-key.gpg.ascii. 2) keybase.io/rust/pgp_keys.asc (named on forge.rust-lang.org) |
| `java.gpg` | Adoptium (Eclipse Temurin) | 3B04D753C9050D9A5D343F39843C48A565F8F04B | 1) packages.adoptium.net/artifactory/api/gpg/key/public (linked from adoptium.net/installation/linux). 2) keyserver.ubuntu.com (third-party; no second official page prints the fingerprint) |
| `cmake.gpg` | CMake / Kitware (Brad King) | CBA23971357C2E6590D9EFD3EC8FEF3A7BFB4EDA (signing subkey C6C265324BBEBDC350B513D02D2CEF1034921684) | 1) cmake.org/download, "PGP sig by 2D2CEF1034921684" (long key ID of the signing subkey). 2) keys.openpgp.org |

**Not signed by their publishers:** Go (`.asc` files exist on dl.google.com, but no official page publishes the key, so it isn't trusted) and
python-build-standalone (GitHub build attestations only). These are checked by SHA-256 only.
