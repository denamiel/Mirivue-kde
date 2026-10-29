#!/usr/bin/env bash
set -euo pipefail

source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
python=/usr/bin/python3
if [[ ! -x "$python" ]]; then
  python=python3
fi
"$python" -c 'import PySide6.QtWidgets' || {
  printf '%s\n' 'PySide6 est nécessaire pour valider les interactions graphiques.' >&2
  exit 1
}
# A disposable session bus exercises the real asynchronous desktop path and
# prevents tests from contacting the user's running Mirivue windows.
command -v dbus-run-session >/dev/null || {
  printf '%s\n' 'dbus-run-session est nécessaire pour isoler la validation.' >&2
  exit 1
}
cd -- "$source_dir"
isolated="$(mktemp -d "${TMPDIR:-/tmp}/mirivue-tests-XXXXXXXX")"
trap 'rm -rf -- "$isolated"' EXIT
# Keep compiler/test evidence outside the temporary installation directory.
log_root="${MIRIVUE_VALIDATION_LOG_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/mirivue-kde/validation}"
mkdir -p -- "$log_root"
log_dir="$(mktemp -d "$log_root/RC194-XXXXXXXX")"
preserve_validation_logs() {
  local result=$?
  trap - EXIT
  for filename in build.log tests.log; do
    if [[ -f "$isolated/$filename" ]]; then
      cp -- "$isolated/$filename" "$log_dir/$filename" || true
    fi
  done
  printf '%s\n' "$result" > "$log_dir/exit-status.txt"
  printf 'Journaux complets conservés : %s\n' "$log_dir"
  rm -rf -- "$isolated"
  exit "$result"
}
trap preserve_validation_logs EXIT
mkdir -p "$isolated/config" "$isolated/data" "$isolated/state" "$isolated/cache"
printf '%s\n' 'Compilation des vues de Dolphin, du modèle Qt, des assistants KIO et du contrôle des fils d’Ariane…'
if ! cmake -S "$source_dir/native" -B "$isolated/native" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DMIRIVUE_NAVIGATOR_TESTS=ON > "$isolated/build.log" 2>&1 \
    || ! cmake --build "$isolated/native" 2>&1 | tee -a "$isolated/build.log"; then
  cat "$isolated/build.log" >&2
  printf '%s\n' 'ÉCHEC — le moteur de vues KDE n’a pas pu être compilé.' >&2
  exit 1
fi
printf '%s\n' 'Validation des tests Python et des interactions Qt en cours…'
test_status=0
XDG_CONFIG_HOME="$isolated/config" XDG_DATA_HOME="$isolated/data" \
XDG_STATE_HOME="$isolated/state" XDG_CACHE_HOME="$isolated/cache" \
MIRIVUE_TEST_PRESENTATION_LIBRARY="$isolated/native/libmirivue-item-presentation.so" \
MIRIVUE_TEST_DOLPHIN_LIBRARY="$isolated/native/libmirivue-dolphin-view.so" \
MIRIVUE_TEST_NAVIGATOR_EXECUTABLE="$isolated/native/mirivue-navigator-check" \
MIRIVUE_TEST_KIO_LIST_EXECUTABLE="$isolated/native/mirivue-kio-list" \
MIRIVUE_TEST_PLACES_LIBRARY="$isolated/native/libmirivue-kio-places-widget.so" \
MIRIVUE_TEST_OPEN_WITH_REFERENCE="$isolated/native/libmirivue-open-with-reference.so" \
QT_QPA_PLATFORM=offscreen dbus-run-session -- timeout --signal=TERM --kill-after=5s 600s \
  "$python" -m unittest discover -s tests -v > "$isolated/tests.log" 2>&1 &
test_pid=$!
(
  while kill -0 "$test_pid" 2>/dev/null; do
    sleep 10
    kill -0 "$test_pid" 2>/dev/null || break
    current_test="$(sed -n '/^test_.* \.\.\./p' "$isolated/tests.log" | tail -n 1)"
    printf 'Validation en cours — %s\n' "${current_test:-initialisation des tests}"
  done
) &
watchdog_pid=$!
wait "$test_pid" || test_status=$?
kill "$watchdog_pid" 2>/dev/null || true
wait "$watchdog_pid" 2>/dev/null || true
if (( test_status != 0 )); then
  if (( test_status == 124 )); then
    printf '%s\n' 'ÉCHEC — validation interrompue après 600 s ; dernier test lancé :' >&2
    tail -n 8 "$isolated/tests.log" >&2
  fi
  # Do not summarise away TimeoutExpired, native stderr or D-Bus diagnostics.
  cat "$isolated/tests.log" >&2
  exit 1
fi
# test_gui_smoke invokes --ui-contract with isolated settings. Running it a
# second time here used to repeat the same KF6 startup and could hang twice.
printf '%s\n' 'RÉUSSI — tests et interactions Qt de la RC194.'
