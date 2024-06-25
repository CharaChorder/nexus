![nexus logo](ui/images/icon.svg)

# nexus

CharaChorder's logging and analysis desktop app, supporting Linux, Windows, and macOS.

## User Installation

1. Download the appropriate executable for your OS:

   | OS                                                                                | Executable                                                                                |
   |-----------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------|
   | Windows (Installer)                                                               | [nexus.msi](https://github.com/CharaChorder/nexus/releases/latest/download/nexus.msi)     |
   | Windows (Portable GUI-only)                                                       | [nexusw.exe](https://github.com/CharaChorder/nexus/releases/latest/download/nexusw.exe)   |
   | Windows (Portable with CLI)                                                       | [nexus.exe](https://github.com/CharaChorder/nexus/releases/latest/download/nexus.exe)     |
   | Linux                                                                             | [nexus](https://github.com/CharaChorder/nexus/releases/latest/download/nexus)             |
   | macOS (Currently CLI-only ([#7](https://github.com/CharaChorder/nexus/issues/7))) | [nexus-macos](https://github.com/CharaChorder/nexus/releases/latest/download/nexus-macos) |

2.
   - **For the MSI**, run the installer. If Windows Defender/Smart Screen asks, choose `More info`, then `Run Anyway`. The MSI
     will install `nexusw.exe` to `%LOCALAPPDATA%\Programs\nexus\nexus.exe`, and add Desktop and
     Start Menu shortcuts. (If you don't like this, sorry; consider contributing a PR to
     implement [#114](https://github.com/CharaChorder/nexus/issues/114)). You can now launch nexus from the Start Menu
     like any other program.

   - **For the portable versions**, save the executable to a folder of your choice. On MacOS and Linux, you may need to
     run `chmod +x nexus{,-macos}` from the directory you saved it in to make it executable.

## Usage

### GUI

1. Launch the program. This may take a while depending on your platform, as the executable must first self-extract.
2. Click `Start Logging` to start logging everything you type, `Refresh` to update the table, and `Stop Logging` to stop
   logging. Starting and stopping may take a while depending on your platform.
3. nexus comes with a tray icon, which you can click on to hide and reopen the window.

### CLI

```
./nexus # Unix
.\nexus.exe # Windows
```

Use the `-h` flag to access CLI options.

## Data location

Your data will be stored platform-dependently in:
- `%APPDATA%\CharaChorder\nexus\` on Windows
- `~/Library/CharaChorder/nexus/` on MacOS
- `$XDG_DATA_HOME/nexus/` on *nix

## Development

### Setup

1. Get Python >=3.11 (using [pyenv](https://github.com/pyenv/pyenv) recommended)
2. Clone and build
    ```sh
    git clone https://github.com/CharaChorder/nexus
    cd nexus/
    python dist.py -nd
    ```

With the `-n` and `-d` flags, `dist.py` automatically detects your OS, sets up a virtualenv in the root directory of the
repo (if not provided one via args), installs requirements, converts UI files to Python, sets up git hooks, and installs
the nexus module locally.

To develop, you can now run it from within the virtualenv (activate it first) using the `python -m nexus <args>`
command.

### Package

```sh
python dist.py
```

Running `dist.py` without any args detects your OS, sets up a virtualenv, installs reqs, converts UI files, and
generates a platform-dependent executable in the `dist/` directory.

## Platform-specific quirks

### Windows

- You may have to allowlist downloaded executables in Windows Defender.
- Running the source code with Microsoft-store-installed Python will cause a shadow copy of `%APPDATA%` (where the DB
  defaults to) to be used. The full exe from Python should be installed instead.
  Read [this](https://docs.python.org/3/using/windows.html#redirection-of-local-data-registry-and-temporary-paths) for
  more details.

### Linux

- Because nexus depends on the python libraries `keyboard` and `mouse`, which do not depend on X and instead hook
  directly onto input device files, you need to add the user you run nexus as to the `input` and `tty` groups and
  make `/dev/uinput` read-writable. This can be done with the following commands:
  ```sh
  sudo usermod -a -G input $(whoami)
  sudo usermod -a -G tty $(whoami)
  sudo chgrp input /dev/uinput
  sudo chmod g+rw /dev/uinput
  ```
  Upon re-login/reboot after running these commands, you should be able to run nexus without root privileges.

## Contributing

Please create PRs and issues, we welcome all contributions. See issues tagged with `Help Wanted` for where you can best
help.

By creating issues, PRs, or any other contributions to this repo, you hereby agree to
our [Contribution License Agreement](Contributing.md). In short,

- The entirety of all of your contributions are your own work,
- Your employer is okay with your contributions if you make them at work,
- You grant (and are legally allowed to grant) CharaChorder all rights to your contributions,
- and will notify us if any of these change.

This summary is for information purposes only, and you are agreeing to the full text in our [CLA](Contributing.md).

## Privacy policy/Data collection

No data is collected from you when you use nexus. Unless you somehow send us data manually (e.g. by creating an issue on
GitHub), anything that you type that may be logged by nexus stays on your computer. You can verify this for yourself by
reading the source code. We will update this section if this changes.

## Security

### Using nexus

Parts of nexus (Freqlog) **log keystrokes**. This is necessary for that module to analyze the words you use the most.
You should ban any sensitive information (passwords, credit card numbers, etc.) or stop logging before typing them.
CharaChorder will not be held responsible for any data loss or theft, or any security breaches. You use nexus at your
own risk.

### Reporting security issues/vulnerabilities

If you find a security issue, please reach out to a CC Rep on Discord or through our support email (support at
charachorder dot com). We will work with you to resolve the issue. Please do not create a GitHub issue for security
issues.
