# CI: the easter extension integration suite

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs the unit tests
and this repo's sqllogictest suite (`test/sql/*.test`) against the easter VGI
worker through the **real DuckDB `vgi` extension** on every push / PR — across
**Linux, macOS, and Windows** — and is reused by
[`publish.yml`](../.github/workflows/publish.yml) so nothing reaches PyPI
without a green extension run on all three.

Both jobs run as an OS matrix. The integration job selects the matching
`haybarn_unittest-*` asset per platform (`linux-amd64`, `osx-arm64`,
`windows-amd64`); on Windows the bash steps run under Git Bash and the worker
LOCATION is the native path to the `.venv/Scripts/vgi-easter.exe` launcher.

## How it works (no C++ build)

Rather than building the vgi DuckDB extension from source, CI drives a
**prebuilt** standalone `haybarn-unittest` (the DuckDB/Haybarn sqllogictest
runner, published in Haybarn's releases) and installs the **signed** vgi
extension from the Haybarn community channel:

1. **Install the worker** — `uv pip install .` into a venv. The `vgi-easter`
   console-script (with its venv shebang) is a self-contained stdio worker the
   extension can spawn.
2. **Download the runner** — `haybarn_unittest-linux-amd64.zip` from the pinned
   Haybarn release.
3. **Preprocess** — the standalone runner links none of the extensions the
   tests gate on, so [`preprocess-require.awk`](preprocess-require.awk) rewrites
   each `require <ext>` into an explicit signed `INSTALL <ext> FROM
   {community,core}; LOAD <ext>;`. `require-env` and everything else pass
   through untouched.
4. **Run** — [`run-integration.sh`](run-integration.sh) stages the preprocessed
   tree, points `VGI_EASTER_WORKER` at the installed `vgi-easter` command, warms
   the extension cache once, then runs the suite in a single `unittest`
   invocation. The CI log streams the runner's native report; any failed
   assertion exits non-zero and fails the job.

## Run it locally

```bash
uv venv .venv --python 3.13 && uv pip install --python .venv .
gh release download haybarn-v1.5.3-rc10 --repo Query-farm-haybarn/haybarn \
  --pattern 'haybarn_unittest-osx-arm64.zip' --output /tmp/hb.zip --clobber
unzip -o /tmp/hb.zip -d /tmp/hb
HAYBARN_UNITTEST=/tmp/hb/haybarn-unittest \
VGI_EASTER_WORKER="$PWD/.venv/bin/vgi-easter" \
  ci/run-integration.sh
```

(Swap the asset pattern for your platform: `haybarn_unittest-linux-amd64.zip`
on CI.)

## Version pin (and its coupling)

`HAYBARN_RELEASE` in [`ci.yml`](../.github/workflows/ci.yml) pins the Haybarn
release supplying `haybarn-unittest`; it must be ABI-compatible with the
community-published `vgi` extension. The vgi extension is pulled live from the
community channel (`INSTALL vgi FROM community`), which always serves the
currently published build — so CI verifies the worker against what users can
actually install today. Bump the pin deliberately and re-run the suite.
