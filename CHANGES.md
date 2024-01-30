# Changes

Update history for **geprotondl**.


## v0.1

- initial release

## v0.2

- fix: geprotondl.py: first run of app would fail, if no cache folder exist
- fix: geprotondl.py: upstream database of GE-Proton on Github changed internal content_type for assets
- fix: geprotondl-fzf.sh: refresh .summary files for entries, which do not have a downloadable content yet, otherwise the cache file would not change and the upload on server would not be detected anymore
