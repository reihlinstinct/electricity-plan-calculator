#!/bin/sh
# Fail if anything resembling real customer data lands in the repo.
# Real IEC exports carry 12-digit contract numbers and meter ids like "NN-NNNNNNNN".
# Synthetic whitelist: contract 000000000000, meter 00-00000001 (sample + fixtures).
set -e
BAD=0

# Rule 1: no real CSV exports (gitignore also blocks these; this is defense in depth)
CSV_FILES=$(find . -name '*.csv' -not -path './.git/*' -not -path './.venv/*' \
  -not -path './data/sample_consumption.csv' -not -path './tests/fixtures/*')
if [ -n "$CSV_FILES" ]; then
  echo "PRIVACY SCAN FAILURE: unexpected CSV files:"; echo "$CSV_FILES"
  BAD=1
fi

# Rule 2: contract numbers and meter ids, minus the synthetic whitelist
scan() {
  if grep -rInE "$1" --exclude-dir=.git --exclude-dir=.venv --exclude-dir=__pycache__ \
       --exclude-dir=node_modules --exclude=privacy_scan.sh . \
       | grep -v -e '000000000000' -e '00-00000001' ; then
    echo "PRIVACY SCAN FAILURE: pattern '$1' matched"
    BAD=1
  fi
}
scan '(^|[^0-9a-fA-F])[0-9]{12}([^0-9a-fA-F]|$)' # contract numbers (hex SHAs excluded)
scan '(^|[^0-9a-fA-F])[0-9]{2}-[0-9]{8}([^0-9a-fA-F]|$)' # meter code-number pairs (hex excluded)
exit $BAD
