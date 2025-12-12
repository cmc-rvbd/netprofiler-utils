#!/bin/bash
#
# Usage:
#    report.sh username password netprofiler-host rows report-spec output-file [format]
#
# Note that the "report-spec" file should be a JSON file specifying the report details (template,
# start/end times, etc) and the "limit" value must be set at least as high as the "rows" argument value 
#
# E.g. to get a report with 12000 lines first edit the JSON file to have a "limit" value of at least 12000
# and set the start and end times accordingly and then run the command:
#
#    report.sh admin adminpwd 10.100.20.1 12000 my-report.jsn output.txt xml
#
# The specified report template must contain a "summary" table or a "flow_list" table and only one of either
# and not both. As it stands, the script looks for either and uses the first one it finds.
# Ideally, all of the contents of the JSON file would be specified on the command line arguments and the
# JSON file generated on the fly.
#
# The possibilities for the realm, groupby and columns fields in the JSON file can be found via the REST API
#   - /api/profiler/1.16/reporting/group_bys
#   - /api/profiler/1.16/reporting/realms
#   - /api/profiler/1.16/reporting/columns
#   - /api/profiler/1.16/reporting/centricities
#
# The traffic expression is the same as you'd use in the Advanced Traffic report (same syntax).
#
# Note the script captures the output at each stage in files called "stageN.txt" for debug purposes only.
#
# Copyright (c) Riverbed Technology, 2023.

USER="$1"
PASSWD="$2"
NPHOST="$3"	# the IP address or hostname of the NetProfiler
ROWS="$4"	# should be a number no higher than the "limit" value in the JSON file
JSON="$5"	# specifies the path to the report spec JSON file
OPFILE="$6"	# the destination file for the report text - should not already exist!
FMT="$7"    # the output format: csv, pdf, xml, json - default is json

#----------------------------------------------------------------------------------------------

fail () {
	echo "$0: fail: $@" 1>&2
	exit 1
}

warn () {
    echo "$0: warning: $@" 1>&2
}

#----------------------------------------------------------------------------------------------
# Input validation
#
[ -z "${OPFILE}" ] && fail "no destination file specified"
[ -f "${OPFILE}" ] && fail "output file ($OPFILE) already exists - delete and rerun or use a different destination file"

[ -z "${FMT}" ] && FMT="json"
case "${FMT}" in
    pdf|PDF) FMT=pdf ;;
    csv|CSV) FMT=csv ;;
    xml|XML) FMT=xml ;;
    json|jsn|JSN|JS0N) FMT=json ;;
    *) fail "invalid format type: ${FMT}" ;;
esac

if [ "${ROWS}" -gt 10000 ]
then
    if [ "${FMT}" = "pdf" -o "${FMT}" = "csv" ]
    then
        warn "Reports in PDF or CSV format will be truncated at 10000 rows"
    fi
fi

if [ -r "${JSON}" ]
then
    #  we have a JSON file...
    COLS=`cat "${JSON}" | 
        python3 -c 'import json,sys;obj=json.load(sys.stdin);print(obj["criteria"]["query"]["columns"])' | 
        sed 's/[[ ]//g' | sed 's/]//' | sed 's/,/%2C/g'`
    if [ -n "${COLS}" ]
    then
        COLS="columns=${COLS}&"
    else
        fail "No 'columns' field found in the JSON file: ${JSON}"
    fi
else
    fail "JSON file not specified or not readable: ${JSON}"
fi

#----------------------------------------------------------------------------------------------
# Start the report generation and grab the report ID from the response
#
REPORT_ID=`curl -sS --insecure -H "Content-Type: application/json" -X POST --data "@${JSON}" -u "${USER}:${PASSWD}" https://"${NPHOST}"/api/profiler/1.16/reporting/reports | tee step1.txt |
	awk '{print $3}' | awk -F\" '{print $2}' | tr -d '\n'`

[ $? -ne 0 -o -z "$REPORT_ID" ] && fail "Report invocation failed"

echo "Report id: $REPORT_ID" 

#----------------------------------------------------------------------------------------------
# Get the report status and keep getting the report status until the progress is at 100%
#
REPORT_STAT=`curl -sS --insecure -H "Content-Type: text/xml X-Requested-With: XMLHttpRequest" -X GET -u "${USER}":"${PASSWD}" https://"${NPHOST}"/api/profiler/1.16/reporting/reports/$REPORT_ID |  tee step2.txt |
	awk '{print $5}' | awk -F\" '{print $2}'`

while [ "$REPORT_STAT" -ne 100 ]
do
	REPORT_STAT=`curl -sS --insecure -H "Content-Type: text/xml X-Requested-With: XMLHttpRequest" -X GET -u "${USER}":"${PASSWD}" https://"${NPHOST}"/api/profiler/1.16/reporting/reports/$REPORT_ID |  tee step2.txt |
		grep "$REPORT_ID" | awk '{print $5}' | awk -F\" '{print $2}'`
	echo "$REPORT_STAT% complete"
done

echo "Report done - saving to $OPFILE"

#----------------------------------------------------------------------------------------------
# Now the report has completed we need to extract the data in two steps:
#  1. Get a list of the report components (queries) and for the required component, extract the query ID
#  2. For the specified component/query, pull the data and output to the standard-output
#
# The report should really be deleted when done with...
#
QUERY_ID=`curl -sS --insecure -H "Accept: text/xml X-Requested-With: XMLHttpRequest" -X GET -u "${USER}":"${PASSWD}" https://"${NPHOST}"/api/profiler/1.16/reporting/reports/$REPORT_ID/queries | tee step3.txt |
	grep actual_log | egrep 'type="(summary|flow_list)"' | head -1 | awk '{print $8}' | awk -F\" '{print $2}' | tr -d '\n'`

case "${FMT}"
in
    xml|json)
        curl -sS --insecure -H "Accept: text/xml X-Requested-With: XMLHttpRequest" -X GET -u "${USER}":"${PASSWD}" \
            https://"${NPHOST}/api/profiler/1.16/reporting/reports/$REPORT_ID/queries/$QUERY_ID.${FMT}?${COLS}limit=${ROWS}" > "${OPFILE}"
        ;;
    pdf|csv)
        curl -sS --insecure -H "Accept: text/xml X-Requested-With: XMLHttpRequest" -X GET -u "${USER}":"${PASSWD}" \
            https://"${NPHOST}/api/profiler/1.16/reporting/reports/$REPORT_ID/view.${FMT}" > "${OPFILE}"
        ;;
esac


# Delete the report now we are have collected the data
# Setting the environment variable "REST_REPORT_KEEP" to a non-null value will cause the deletion to be skipped
#
[ -z "${REST_REPORT_KEEP}" ] &&
    curl --insecure -H "Accept: text/xml X-Requested-With: XMLHttpRequest" -X DELETE -u "${USER}":"${PASSWD}" \
        https://"${NPHOST}/api/profiler/1.16/reporting/reports/${REPORT_ID}"
