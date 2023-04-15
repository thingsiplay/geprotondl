#!/bin/env bash

# The path or command name to the geprotondl script.
# cmd_geprotondl="geprotondl.py"
default_geprotondl_cmd="geprotondl.py"

# Note: Try to give enough space between option name and description, so it can
# be aligned in the same manner as the main applications help output.
print_usage() {
    echo \
'usage: geprotondl-fzf [-h] [-g CMD] [-C DIR] [-f]

Frontend script to geprotondl by utilizing fzf. Select an entry will run
geprotondl to either install or remove, depending on the current installation
state of the selected version. Summary files are generated in cache folder, so
it can load previews faster next time.

options:
  -h                   print this help and exit
  -g                   path or name of the geprotondl command
  -C                   cache folder to save .summary files into           
  -f                   rebuild all cached .summary files

Long options such as --help or --cache are not supported by this script.

All commandline arguments are forwarded to geprotondl.'
}

# The bash internal function `getopts` does not handle long option names
# starting with double dash. Do not process further if any user argument starts
# with "--".
for argument in "${@}"
do
    if [[ ${argument} =~ --.* ]]
    then
        printf "Long option names starting with double dash \"--\" are not "
        echo "supported by this script: \"${argument}\""
        exit 1
    fi
done

opt_geprotondl_cmd=""
opt_cache_dir=""
opt_force=0

# Note, any given long option like --help will also trigger the short version
# -h in this script, or --cache can be confused to be -c. Therefore any short
# option here should match the long one from the original geprotondl program.
# Generally speaking long options should be avoided with this shell script.
while getopts ':hg:C:f' OPTION; do
    case "$OPTION" in
        h)
            print_usage
            exit 0
            ;;
        g)
            opt_geprotondl_cmd="${OPTARG}"
            ;;
        C)
            opt_cache_dir="${OPTARG}"
            ;;
        f)
            opt_force=1
            ;;
        ?)
            continue
            ;;
    esac
done

if [ "${opt_geprotondl_cmd}" == "" ]
then
    geprotondl_cmd="${default_geprotondl_cmd}"
else
    geprotondl_cmd="${opt_geprotondl_cmd}"
fi

# Intermediate variable to hold in case the command cannot be found, so that
# the failed command can be displayed.
lookup_geprotondl_cmd="$(command -v "${geprotondl_cmd}")"

if [ "${lookup_geprotondl_cmd}" == "" ]
then
    echo "Command does not exist: \"${geprotondl_cmd}\""
    exit 1
else
    geprotondl_cmd="${lookup_geprotondl_cmd}"
fi

if [ "${opt_cache_dir}" == "" ]
then
    # Default cache folder if no option is given.
    export cache_dir="$("${geprotondl_cmd}" -cb)"
    # Alternatively comment the above line out and uncomment the below one to
    # set the path directly. Without running the above command this should work
    # much faster. Don't forget to edit the user name.
    #export cache_dir="/home/USER/.cache/geprotondl"
else
    export cache_dir="${opt_cache_dir}"
fi

if [ ! -d "${cache_dir}" ]
then
    echo "Cache folder does not exist: \"${cache_dir}\""
    exit 1
fi

create_summary () {
    local file="${cache_dir}/${1}.summary"
    if [ "${opt_force}" == 1 ] || ! [ -f "${file}" ]
    then
        # Don't use human readable, as otherwise the dates would be converted
        # to relative days and not accurate anymore.
        "${geprotondl_cmd}" --summary --quiet --tag "${1}" \
            > "${file}" \
            || return &
    fi
}

cat_summary () {
    local file="${cache_dir}/${1}.summary"
    cat "${file}"
}

export -f cat_summary

for tag in $("${geprotondl_cmd}" --releases --quiet --brief \
            | grep -oE "GE-Proton[^ ]+")
do
    create_summary "${tag}" > /dev/null &
done

tag_cmd='$(echo {} | grep -oE "GE-Proton[^ ]+")'
selection=$("${geprotondl_cmd}" --releases --quiet \
        | fzf --no-sort --exact --no-extended \
            --layout=reverse-list \
            --preview-label="${0##*/}" \
            --preview-window="down:60%,wrap" \
            --preview="cat_summary ${tag_cmd}")

if [ "${selection}" == "" ]
then
    exit
else
    if [[ "${selection}" =~ \[x\] ]]
    then
        option="--remove"
    else
        option="--install"
    fi
    tag_name=$(echo "${selection}" | grep -oE 'GE-Proton[^ ]+')
    "${geprotondl_cmd}" ${option} --tag "${tag_name}" "${@}"
fi
