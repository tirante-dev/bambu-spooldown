# Changelog

## [0.5.2](https://github.com/tirante-dev/bambu-spooldown/compare/bambu-spooldown-v0.5.1...bambu-spooldown-v0.5.2) (2026-09-02)


### Bug Fixes

* message cleanup is best-effort, mailpit answers delete in plain text ([#29](https://github.com/tirante-dev/bambu-spooldown/issues/29)) ([8708447](https://github.com/tirante-dev/bambu-spooldown/commit/87084472119df2c11b7c1fb133ab9bdb4853b5e4))

## [0.5.1](https://github.com/tirante-dev/bambu-spooldown/compare/bambu-spooldown-v0.5.0...bambu-spooldown-v0.5.1) (2026-09-02)


### Bug Fixes

* tolerate empty 200 bodies, renewal survives non-OSError failures ([#24](https://github.com/tirante-dev/bambu-spooldown/issues/24)) ([1f4f424](https://github.com/tirante-dev/bambu-spooldown/commit/1f4f4244573f22d28d20f212ca48817dd075fe57))

## [0.5.0](https://github.com/tirante-dev/bambu-spooldown/compare/bambu-spooldown-v0.4.1...bambu-spooldown-v0.5.0) (2026-08-31)


### Features

* automatic token renewal via mailbox code login, metrics ([#22](https://github.com/tirante-dev/bambu-spooldown/issues/22)) ([792d806](https://github.com/tirante-dev/bambu-spooldown/commit/792d8060108cac6d09bc09cea6e4146a190287a8))
* nudge for token renewal, refresh is closed to email-code logins ([#20](https://github.com/tirante-dev/bambu-spooldown/issues/20)) ([6dff65d](https://github.com/tirante-dev/bambu-spooldown/commit/6dff65df81dc9b9eb4c653d390b6502cacc90bcb))

## [0.4.1](https://github.com/tirante-dev/bambu-spooldown/compare/bambu-spooldown-v0.4.0...bambu-spooldown-v0.4.1) (2026-08-31)


### Bug Fixes

* send a non-python user agent, bambu's waf 403s urllib ([#17](https://github.com/tirante-dev/bambu-spooldown/issues/17)) ([471b037](https://github.com/tirante-dev/bambu-spooldown/commit/471b037730a7ce1db9a29f2bd9e8c34b0c0b2682))

## [0.4.0](https://github.com/tirante-dev/bambu-spooldown/compare/bambu-spooldown-v0.3.0...bambu-spooldown-v0.4.0) (2026-08-31)


### Features

* auto-map third-party trays, notify via ntfy when ambiguous ([#14](https://github.com/tirante-dev/bambu-spooldown/issues/14)) ([c25a376](https://github.com/tirante-dev/bambu-spooldown/commit/c25a376262f20199d273f3e2f596b8e022926995))

## [0.3.0](https://github.com/tirante-dev/bambu-spooldown/compare/bambu-spooldown-v0.2.0...bambu-spooldown-v0.3.0) (2026-08-31)


### Features

* rotate bambu cloud tokens automatically ([#9](https://github.com/tirante-dev/bambu-spooldown/issues/9)) ([d117146](https://github.com/tirante-dev/bambu-spooldown/commit/d11714663a82f39482f3b4e6e9f3c301f987644f))

## [0.2.0](https://github.com/tirante-dev/bambu-spooldown/compare/bambu-spooldown-v0.1.0...bambu-spooldown-v0.2.0) (2026-08-31)


### Features

* helm chart, harbor releases via release-please ([ab59401](https://github.com/tirante-dev/bambu-spooldown/commit/ab59401a6c33020582c9864718f622c1d39d9f06))
* helm chart, harbor releases via release-please ([f6260c7](https://github.com/tirante-dev/bambu-spooldown/commit/f6260c7936367a1c0e2a35e7b9da950b1f5c47f1))
