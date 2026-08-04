# ADR 0002: Keep the GUI as a local web application

- Status: accepted
- Date: 2026-08-04
- Related issue: [#112](https://github.com/gcomneno/lele-manager/issues/112)

## Context

LeLe Manager combines a Python application, FastAPI, filesystem-backed
Markdown authoring, local JSONL projections, scikit-learn models and a Svelte
GUI. The released GUI is served by the same local FastAPI process.

Issue #112 requires an explicit decision between retaining this model and
introducing an installable desktop package.

## Decision drivers

- installation complexity;
- update and release complexity;
- Linux, macOS and Windows support;
- runtime size;
- filesystem and subprocess integration;
- reuse of the existing Python backend;
- maintenance cost for a small local-first project;
- absence or presence of desktop-native requirements.

## Options

### Local FastAPI/Svelte web application

Advantages:

- reuses the complete existing architecture;
- has one backend and one frontend build;
- works with ordinary Python packaging and a browser;
- keeps API, CLI and GUI behavior aligned;
- has the lowest maintenance and release cost.

Costs:

- users start a local service;
- browser presentation is less application-like;
- desktop integration is limited.

### Progressive Web App

Advantages:

- install-like browser experience;
- limited additional frontend work.

Costs:

- does not remove the Python server;
- service-worker caching adds state and update complexity;
- browser sandboxing does not replace controlled filesystem access.

### Electron

Advantages:

- mature cross-platform desktop ecosystem;
- straightforward browser UI embedding.

Costs:

- large runtime and distribution size;
- separate Node/Electron security and update lifecycle;
- still requires coordination with the Python backend;
- duplicates packaging responsibilities.

### Tauri

Advantages:

- smaller desktop shell than Electron;
- strong native packaging capabilities.

Costs:

- introduces Rust and a native bridge;
- increases platform-specific build and signing work;
- still requires bundling or managing Python;
- adds architectural complexity without a current user requirement.

## Comparison

| Option | Installation complexity | Updates | Platforms | Runtime size | Maintenance cost |
|---|---|---|---|---|---|
| Local FastAPI/Svelte | Existing Python and frontend build | Existing release flow | Any supported Python platform with a browser | Existing Python environment | Low |
| Progressive Web App | Adds manifest, service worker and browser installation behavior | Browser cache invalidation plus backend updates | Browser-dependent | Small frontend addition, Python still required | Medium |
| Electron | Adds desktop bundling and Python-process coordination | Separate desktop updater and security lifecycle | Linux, macOS and Windows with platform builds | Large bundled Chromium and Node runtime | High |
| Tauri | Adds Rust toolchain, native bridge and Python bundling strategy | Native updater, signing and backend coordination | Linux, macOS and Windows with platform builds | Smaller shell than Electron, Python still required | High |

No option removes the need to manage the Python backend. The desktop options
therefore add a second packaging lifecycle without satisfying a current
desktop-native requirement.

## Decision

Keep LeLe Manager as a local FastAPI/Svelte web application.

Do not implement Electron, Tauri or PWA packaging in issue #112. A desktop
package may be reconsidered through a separate issue only when concrete
requirements justify the additional lifecycle.

## Consequences

- the supported GUI startup remains build frontend, start FastAPI, open `/app/`;
- Python remains the sole application runtime;
- screenshots and documentation describe browser-based local use;
- packaging effort stays focused on reliable Python installation and scripts;
- native menus, tray integration, auto-update and signed installers remain out
  of scope;
- a future desktop issue must define supported platforms, Python bundling,
  signing, updates and filesystem permissions before implementation.
