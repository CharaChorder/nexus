# Nexus

CharaChorder's all-in-one desktop app, supporting Linux, Windows, and MacOS.

## Build
1. Get Python 3.11 (using [pyenv](https://github.com/pyenv/pyenv) recommended)
2. Clone and build
```
git clone https://github.com/CharaChorder/nexus
cd nexus/
python dist.py
```
Note: the CI-generated binaries (in releases) don't work at the moment (see [#6 CI doesn't work](https://github.com/CharaChorder/nexus/issues/6)).
`dist.py` sets up a virtualenv in the root directory of the repo, and generates a platform-dependent executable in the `dist/` directory.

## Usage
```
cd dist/ # if following the steps above
./nexus # Unix
.\nexus.exe # Windows
```
Use the `-h` to access CLI options.

## Contributing

Please create PRs and issues, we welcome all contributions. See issues tagged with `Help Wanted` for where you can best help.

By creating issues, PRs, or any other contributions to this repo, you hereby agree to our [Contribution License Agreement](Contributing.md). In short,
- The entirety of all of your contributions are your own work,
- Your employer is okay with your contributions if you make them at work,
- You grant (and are legally allowed to grant) CharaChorder all rights to your contributions,
- and will notify us if any of these change.

This summary is for information purposes only, and you are agreeing to the full text in our [CLA](Contributing.md).
