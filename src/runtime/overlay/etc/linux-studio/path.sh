# Linux Studio: PATH additions for every shell inside the sandbox. Loaded by /etc/linux-studio/bashrc (interactive
# shells) and /etc/profile.d/linux-studio.sh (login shells, including non-interactive "bash -lc").
# The editor's terminal starts a login shell and Debian's /etc/profile resets PATH, so this puts back what Linux Studio
# adds: its own xdg-open (links open in a tab inside Linux Studio) and the toolchains chosen with "Use this version".
# Only folders that are missing are added, and never an empty entry (which would mean "the current folder", D6-6).
__ls_path_add() { case ":${PATH:-}:" in *":$1:"*) ;; *) PATH="$1${PATH:+:$PATH}" ;; esac; }
for __ls_d in /toolchains/*/current/bin; do [ -d "$__ls_d" ] && __ls_path_add "$__ls_d"; done
[ -d /run/linux-studio/bin ] && __ls_path_add /run/linux-studio/bin
export PATH
[ -d /toolchains/java/current ] && export JAVA_HOME=/toolchains/java/current
unset __ls_d; unset -f __ls_path_add
