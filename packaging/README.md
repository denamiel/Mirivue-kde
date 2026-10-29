# Paquet local CachyOS / Arch Linux (RC181)

`Construire-paquet-CachyOS.sh` utilise `makepkg` pour compiler les assistants
KIO/KF6 depuis `native` et créer un paquet local. Il ne l'installe pas et ne
demande aucun privilège administrateur. Les sources ne contiennent pas de
binaires natifs précompilés.

Installer une fois les outils de construction, si nécessaire :

```bash
sudo pacman -S --needed base-devel cmake ninja extra-cmake-modules
```

Depuis le dossier extrait :

```bash
./Valider-RC181.sh
./Construire-paquet-CachyOS.sh
sudo pacman -U ./mirivue-kde-1.0.0rc193-1-x86_64.pkg.tar.zst
./Verifier-installation-RC181.sh
```

`A-verifier-RC181.md` contient les essais manuels avant publication stable.
