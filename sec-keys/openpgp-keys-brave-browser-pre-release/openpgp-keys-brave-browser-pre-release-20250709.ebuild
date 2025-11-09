# Copyright 2024 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

SEC_KEYS_VALIDPGPKEYS=(
	"2739F6DFC3077EA8A193A2B23DCB1DA4732251B4:brave-checksums-pre-release:manual"
	"2EBA6748F546553AA5660F6CC4208DE1DAB3C9DB:brave-checksums-pre-release:manual"
	"D4833E8186E382E445A3E1782462ADFD3E24FB85:brave-checksums-pre-release:manual"
)

inherit sec-keys

DESCRIPTION="OpenPGP to sign Brave Browser's Github Beta/Nightly releases"
HOMEPAGE="https://brave.com/signing-keys/#checksums-beta-channel"
SRC_URI="https://brave-browser-downloads.s3.brave.com/keys/github-checksums-pre-release.asc -> ${P}.asc"
S="${WORKDIR}"

LICENSE="public-domain"
SLOT="0"
KEYWORDS="amd64"
