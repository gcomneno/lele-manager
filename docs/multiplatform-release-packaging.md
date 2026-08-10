# Multiplatform release packaging

> Status: implementation contract
> Pilot project: LeLe Manager

## Goal

A stable LeLe Manager release must be usable by a non-technical person without
installing Python, Node.js, npm, development tools, or project dependencies.

The normal user flow is:

1. download the package for the operating system;
2. extract or open it;
3. launch LeLe Manager;
4. wait for the browser to open automatically;
5. use the web GUI.

## Supported platforms

Release packaging is organized by operating system and architecture.

Canonical artifact naming:

- `LeLe-Manager-vX.Y.Z-Linux-<arch>.tar.gz`
- `LeLe-Manager-vX.Y.Z-macOS-<arch>.zip`
- `LeLe-Manager-vX.Y.Z-Windows-<arch>.zip`

The architecture suffix keeps the contract extensible without changing the
release naming scheme.

## User contract

The packaged application must:

- include the Python runtime and all required Python dependencies;
- include the compiled Svelte GUI;
- require no Python, pip, Node.js, npm, or virtual environment on the target
  computer;
- provide one obvious launcher;
- start the local LeLe Manager backend automatically;
- wait until the local service is ready;
- open the default browser on the LeLe Manager GUI automatically;
- keep user data outside the application installation directory;
- preserve user data across application upgrades;
- show a useful error message if startup fails.

### Linux user-local installation

The Linux archive deliberately remains portable and versioned for download.
In addition, its archive root ships an executable `install.sh`. Running it
explicitly (never as a side effect of starting the application) installs the
one-dir PyInstaller bundle at
`${XDG_DATA_HOME:-~/.local/share}/lele-manager/app` and creates the stable
`~/.local/bin/lele-manager` symlink. `LELE_MANAGER_INSTALL_BIN_DIR` is a
narrow, documented absolute-path override for the launcher destination.

The installed `app/` directory is version-independent and is swapped only
after a complete staged copy has been validated. The surrounding
`lele-manager` data directory is intentionally preserved because the runtime
already uses it for persistent application data. Reinstalling or installing a
new release therefore keeps the launcher path and user data stable. This
contract does not register a `.desktop` file, icons, or any other desktop
resource.

## Persistent user data

Runtime data must not be stored inside the unpacked release directory.

LeLe Manager uses `platformdirs` to resolve an operating-system-appropriate
user data directory.

The packaged launcher must create the required directories on first startup,
including a default Markdown Vault when one does not already exist.

Environment variables explicitly supplied by an advanced user may continue to
override normal defaults where the existing application contract allows it.

## Launcher

A product-level launcher will be responsible for:

1. resolving persistent user directories;
2. preparing first-run directories when necessary;
3. configuring LeLe Manager runtime paths;
4. starting the FastAPI application;
5. waiting for the local health endpoint;
6. opening `/app/` in the default browser;
7. keeping the local server alive until the application is closed.

The launcher must be implemented in application code rather than duplicating
business logic in separate shell, Batch, or PowerShell implementations.

OS-specific files may provide only the thin entry point required to invoke the
packaged launcher.

## Packaging strategy

The distributable application must be self-contained.

Packaging must be produced natively for each target platform in CI rather than
cross-building platform executables from another operating system.

The existing Python wheel and source distribution remain supported technical
artifacts. They are not the primary installation path for non-technical users.

## GitHub Actions

Stable release automation must build packages on native runners for:

- Linux;
- macOS;
- Windows.

The workflow must verify each packaged application before publishing it as a
GitHub Release asset.

A release must not publish an artifact merely because packaging completed:
the packaged executable must pass a startup/smoke verification first.

The native release job therefore verifies the same published-style archive that
would be uploaded to GitHub. CI extracts that archive into an isolated temporary
directory, starts the packaged executable with isolated runtime paths, waits for
the loopback health endpoint, and checks the packaged GUI, license, About and
runtime Settings surfaces before upload. The verification also confirms that
persistent runtime paths resolve outside the extracted release directory.

## User documentation

Each release package must include a short first-run guide appropriate to the
target operating system.

The guide must explain actions in user terms, for example:

- where to click to download the package;
- how to open or extract it;
- exactly which launcher to double-click;
- what happens next;
- what to do if the browser does not open.

Documentation must not assume knowledge of terminals, Python, virtual
environments, package managers, APIs, or web servers.

## Version and tag invariants

Before a release tag is created:

- the application/package version must already equal the intended tag;
- source and packaged GUI must be synchronized;
- tests and packaging smoke checks must be green;
- all intended native release artifacts must be reproducibly buildable.

The release tag is the final release seal, not the mechanism that prepares the
release.

For example, tag `v1.10.1` requires application version `1.10.1`.

## Wider GiadaWare policy

LeLe Manager is the pilot implementation of this release contract.

Once validated here, the same user-facing release principle should be applied
to installable applications listed in the GiadaWare GitHub showcase under
`1 · SELECTED PROJECTS`, adapted only where a project's runtime architecture
requires a different native packaging mechanism.
