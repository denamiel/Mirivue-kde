#!/usr/bin/env bash
set -euo pipefail

source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
output_dir="$source_dir"
build_dir="$(mktemp -d "${TMPDIR:-/tmp}/mirivue-package-XXXXXXXX")"
trap 'rm -rf -- "$build_dir"' EXIT

if ! command -v makepkg >/dev/null 2>&1; then
  printf '%s\n' 'makepkg est absent. Installez le groupe base-devel puis recommencez.' >&2
  exit 1
fi
for command in cmake ninja; do
  if ! command -v "$command" >/dev/null 2>&1; then
    printf 'Outil de construction absent : %s. Installez cmake, ninja et extra-cmake-modules puis recommencez.\n' "$command" >&2
    exit 1
  fi
done

archive="$build_dir/Mirivue-1.0.0-RC194-KDE.tar.gz"
tar -C "$source_dir/.." \
  --exclude='Mirivue-1.0.0-RC194-KDE/tests' \
  --exclude='*.pkg.tar.*' --exclude='*.zip' \
  --exclude='*/__pycache__' --exclude='*.pyc' \
  -czf "$archive" Mirivue-1.0.0-RC194-KDE
checksum="$(sha256sum "$archive" | cut -d' ' -f1)"
sed "s/@SOURCE_SHA256@/$checksum/" "$source_dir/packaging/PKGBUILD.template" > "$build_dir/PKGBUILD"
(cd "$build_dir" && makepkg --clean --force)
package="$(find "$build_dir" -maxdepth 1 -name 'mirivue-kde-*.pkg.tar.*' -print -quit)"
if [[ -z "$package" ]]; then
  printf '%s\n' 'Le paquet n’a pas été produit.' >&2
  exit 1
fi
cp -f -- "$package" "$output_dir/"
printf 'Paquet créé : %s/%s\n' "$output_dir" "$(basename -- "$package")"
