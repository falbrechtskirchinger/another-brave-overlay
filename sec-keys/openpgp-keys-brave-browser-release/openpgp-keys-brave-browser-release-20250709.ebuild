# Copyright 2024 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

SEC_KEYS_VALIDPGPKEYS=(
	"B840107020F8BED83CF7696DEDC0814C91A8144D:brave-checksums-release:manual"
	"7FE68A2E3754FA350A45F0AB68E5C22615F0E249:brave-checksums-release:manual"
	"10A714FCA3C829A605E686A5C479D18E038EAF42:brave-checksums-release:manual"
)

inherit sec-keys

DESCRIPTION="OpenPGP to sign Brave Browser's Github releases"
HOMEPAGE="https://brave.com/signing-keys/#checksums-release-channel"
SRC_URI="https://brave-browser-downloads.s3.brave.com/keys/github-checksums-release.asc -> ${P}.asc"
S="${WORKDIR}"

LICENSE="public-domain"
SLOT="0"
KEYWORDS="amd64"
