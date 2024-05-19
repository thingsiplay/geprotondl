# Changes

Update history for **geprotondl**.

## Next

- fix: geprotondl.py: script now compatible with and should require at least
  Python v3.12, as the internally how Paths are handled changed

## v0.3

- change: geprotondl-fzf.sh: now searches a list of commands to find `geprotondl`
  main script
- removed: geprotondl-up.py: completely wiped and deleted this script from
  the project, as it was confusing, which also eliminates the need for a symlink
  to "geprotondl.py"
- removed: check.sh: completely wiped and deleted this developer script
  from the project, as builtin checker tools in IDE and editor are enough

## v0.2

- fix: geprotondl.py: first run of app would fail, if no cache folder exist
- fix: geprotondl.py: upstream database of GE-Proton on Github changed
  internal content_type for assets
- fix: geprotondl-fzf.sh: refresh .summary files for entries, which do not
  have a downloadable content yet, otherwise the cache file would not change and
  the upload on server would not be detected anymore

## v0.1

- initial release
