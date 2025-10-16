# Copyright 2024 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DESCRIPTION="OpenPGP to sign Brave Browser's Github releases"
HOMEPAGE="https://brave.com/signing-keys#checksums-release-channel"
SRC_URI="https://brave-browser-downloads.s3.brave.com/keys/github-checksums-release.asc -> ${P}.asc"
S="${WORKDIR}"

LICENSE="public-domain"
SLOT="0"
KEYWORDS="amd64"

src_install() {
	local files=( ${A} )
	insinto /usr/share/openpgp-keys
	newins - brave-browser.asc < <(cat "${files[@]/#/${DISTDIR}/}")
}
