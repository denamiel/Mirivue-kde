#!/usr/bin/env bash
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if (( EUID == 0 )); then
  printf '%s\n' 'Lancez ce script avec votre compte utilisateur, sans sudo.' >&2
  exit 1
fi
command -v makepkg >/dev/null || { echo 'Installez base-devel pour obtenir makepkg.' >&2; exit 1; }
build_dir="$(mktemp -d "${TMPDIR:-/tmp}/mirivue-package-XXXXXXXX")"
trap 'rm -rf -- "$build_dir"' EXIT
version="$(python - "$source_dir/mirivue/__init__.py" <<'PY'
import ast, pathlib, re, sys
module = ast.parse(pathlib.Path(sys.argv[1]).read_text())
version = next(ast.literal_eval(n.value) for n in module.body
               if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__version__" for t in n.targets))
if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-(?:alpha|beta|rc)\.[0-9]+)?", version):
    raise SystemExit("Version non prise en charge : " + version)
print(version.replace("-", "").replace("beta.", "beta").replace("alpha.", "alpha").replace("rc.", "rc"))
PY
)"
archive="$build_dir/mirivue-source.tar.gz"
tar -C "$source_dir" --exclude='./.git' --exclude='./.github' \
  --exclude='./build' --exclude='./src' --exclude='./pkg' \
  --exclude='*.pkg.tar.*' --exclude='*.zip' --exclude='__pycache__' --exclude='*.pyc' \
  --transform='s,^\.,mirivue-source,' -czf "$archive" .
checksum="$(sha256sum "$archive" | cut -d' ' -f1)"
sed -e "s/@SOURCE_SHA256@/$checksum/" -e "s/@PKGVER@/$version/" \
  "$source_dir/packaging/PKGBUILD.template" > "$build_dir/PKGBUILD"
makepkg_options=(--clean --force --syncdeps)
if [[ "${CI:-}" == true ]]; then
  makepkg_options+=(--noconfirm)
fi
(cd "$build_dir" && makepkg "${makepkg_options[@]}")
mapfile -t packages < <(cd "$build_dir" && makepkg --packagelist)
for package in "${packages[@]}"; do
  test -f "$package"
  cp -- "$package" "$source_dir/"
  printf 'Paquet créé : %s/%s\n' "$source_dir" "$(basename -- "$package")"
done
