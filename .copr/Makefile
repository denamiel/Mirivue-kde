# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
.PHONY: srpm
srpm:
	dnf -y install git rpm-build
	bash packaging/fedora/Preparer-Sources.sh
	mkdir -p "$(outdir)"
	rpmbuild -bs --define "_sourcedir $(CURDIR)/packaging/fedora" --define "_srcrpmdir $(outdir)" packaging/fedora/mirivue-kde.spec
