# Nexus

CharaChorder's all-in-one desktop app, supporting Linux, Windows, and MacOS.

## Build
1. Get Python >=3.11 (using [pyenv](https://github.com/pyenv/pyenv) recommended on Linux/MacOS, Microsoft store has 3.11 for Windows)
2. Clone and build
```sh
git clone https://github.com/CharaChorder/nexus
cd nexus/
python dist.py -nd
```
With the `-n` and `-d` flags, `dist.py` automatically detects your OS, sets up a virtualenv in the root directory of the repo (if not provided one via args), installs requirements, converts UI files to Python, sets up git hooks, and installs the nexus module locally.

To develop, you can now run it from within the virtualenv (activate it first) using the `python -m nexus <args>` command.

## Installation
```sh
python dist.py
```
Running `dist.py` without any args detects your OS, sets up a virtualenv, installs reqs, converts UI files, and generates a platform-dependent executable in the `dist/` directory.

Note: the CI-generated binaries (in releases) don't work at the moment (see [#6 CI doesn't work](https://github.com/CharaChorder/nexus/issues/6)).

## Usage
```
cd dist/ # if following the steps above
./nexus # Unix
.\nexus.exe # Windows
```
Use the `-h` to access CLI options.

## Platform-specific quirks
### Wayland
You need to have XWayland enabled, and allow X11 apps to read keystrokes in all apps (on KDE this is in `Settings > Applications > Legacy X11 App Support`).

## Contributing

Please create PRs and issues, we welcome all contributions. See issues tagged with `Help Wanted` for where you can best help.

By creating issues, PRs, or any other contributions to this repo, you hereby agree to our [Contribution License Agreement](Contributing.md). In short,
- The entirety of all of your contributions are your own work,
- Your employer is okay with your contributions if you make them at work,
- You grant (and are legally allowed to grant) CharaChorder all rights to your contributions,
- and will notify us if any of these change.

This summary is for information purposes only, and you are agreeing to the full text in our [CLA](Contributing.md).
