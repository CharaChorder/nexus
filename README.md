![nexus logo](ui/images/icon.svg)

# nexus

CharaChorder's all-in-one desktop app, supporting Linux, Windows, and macOS.

## Build

1. Get Python >=3.11 (using [pyenv](https://github.com/pyenv/pyenv) recommended on Linux/macOS, Microsoft store has 3.11 for Windows)
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
Use the `-h` flag to access CLI options

## Platform-specific quirks

### Wayland

- You need to have XWayland enabled, and allow X11 apps to read keystrokes in all apps (on KDE this is in `Settings > Applications > Legacy X11 App Support`).
- Move the `com.charachorder.nexus.desktop` file into either your `~/.local/share/applications/` or `/usr/share/applications/` directory, and edit the path to point to the nexus icon.

## Contributing

Please create PRs and issues, we welcome all contributions. See issues tagged with `Help Wanted` for where you can best help.

By creating issues, PRs, or any other contributions to this repo, you hereby agree to our [Contribution License Agreement](Contributing.md). In short,
- The entirety of all of your contributions are your own work,
- Your employer is okay with your contributions if you make them at work,
- You grant (and are legally allowed to grant) CharaChorder all rights to your contributions,
- and will notify us if any of these change.

This summary is for information purposes only, and you are agreeing to the full text in our [CLA](Contributing.md).

## Privacy policy/Data collection

No data is collected from you when you use nexus. Unless you somehow send us data manually (e.g. by creating an issue on GitHub), anything that you type that may be logged by nexus stays on your computer. You can verify this for yourself by reading the source code. We will update this section if this changes.

## Security

### Using nexus

Parts of nexus (Freqlog) **log keystrokes**. This is necessary for that module to analyze the words you use the most. You should ban any sensitive information (passwords, credit card numbers, etc.) or stop logging before typing them. CharaChorder will not be held responsible for any data loss or theft, or any security breaches. You use nexus at your own risk.

### Reporting security issues/vulnerabilities

If you find a security issue, please reach out to a CC Rep on Discord or through our support email (support at charachorder dot com). We will work with you to resolve the issue. Please do not create a GitHub issue for security issues.
