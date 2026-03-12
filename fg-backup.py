#!/usr/bin/env python3
"""
Summary and usage
Usage:
  fg-backup --fghost fghost  --fguser fguser [--fgpass fgpassword] --desthost dest-host --destuser duser 
    [--destpass dpass] --destpath destpath --key encryption-key --trim keep_count

If either of the passwords is not provided, they will be prompted for on the CLI.
Note that if the FLow Gateway host has SSH keys set-up up with the destination host such that
A password is not required, then the "destpass" argument will not be used. I.e. the value is
irrelevant. This would be the suggested way to use the script to avoid the need for embedding passwords
in script or config files.

Note also that the script can auto-trim the backups in the destination folder to the most recent X
backups using the --trim option but this will only work if the script runs on the destination host so has
local access to the destination folder. By default trimming will be disabled (or keep_count == 0)
"""

import argparse
import getpass
import json
import requests
import sys
import os
import shutil
import base64
import time
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# -----------------------------------------------------------------------------

def fail (mesg):
    print ("Failed:", mesg)
    sys.exit(1)

def pretty_print_req(method, url, headers, data = None):
    req = requests.Request(method, url, headers=headers, data=data)
    prepared = req.prepare()
    #pretty_print_req(prepared)
    print('{}\n{}\r\n{}\r\n\r\n{}'.format(
        '-----------START-----------',
        req.method + ' ' + req.url,
        '\r\n'.join('{}: {}'.format(k, v) for k, v in req.headers.items()),
        req.body,
    ))
    sess = requests.Session()
    r = sess.send(prepared, verify=False)
    print (r)
    return r
    
# -----------------------------------------------------------------------------
# As the methods used on AR and Portal do not work with Profiler/Gateway appliances, we need to use
# something else. We could use OAUTH access codes from the appliance GUI (OAUTH page) but this will
# eventually expire and adds maintenance overhead.
# Or, we use BASIC authentication to create an OAUTH token but this results in a Location header
# which has to be parsed to extract a token.
# Or we just stick with BASIC auth.
#
def create_basic_auth (username, password):
    
    credentials = username + ":" + password
    basic_auth = base64.b64encode(credentials.encode('utf-8'))
    basic_auth_header =  {'Authorization' : 'Basic %s' % basic_auth.decode('utf-8') }

    return basic_auth_header
    
def appliance_rest_call_verbose (action, appliance, basic_auth_hdr, api, payload = None, data = None, additional_headers = None):

    url = "https://" + appliance + api 

    headers = basic_auth_hdr
    if additional_headers != None:
        headers.update (additional_headers)

# -----

##### REST API INTEGRATION #####
#
# Run REST APIs to appliance and return result
# Assumes 'payload' is JSON formatted
#
def appliance_rest_call (action, appliance, basic_auth_hdr, api, payload = None, data = None, additional_headers = None):

    url = "https://" + appliance + api 

    headers = basic_auth_hdr
    if additional_headers != None:
        headers.update (additional_headers)
        
    if (action == "GET"):
        r = requests.get (url, headers=headers, verify=False)

    elif (action == "POST"):
        if payload != None:
            r = requests.post (url, headers=headers, json=payload, verify=False)
        else:
            r = requests.post (url, headers=headers, data=data, verify=False)
    elif (action == "PUT"):
        r = requests.put (url, headers=headers, data=json.dumps (payload), verify=False)
    elif (action == "DELETE"):
        r = requests.delete (url, headers=headers, verify=False)

    if (r.status_code not in [200, 201, 202, 204]):
        print ("Status code was %s" % r.status_code)
        print ("Error: %s" % r.content)
        result = None
    else:
        if (("Content-Type" in r.headers.keys ()) and ("application/json" in r.headers ["Content-Type"])):
            result = json.loads (r.content) 
        elif (("Content-Type" in r.headers.keys ()) and ("application/x-gzip" in r.headers ["Content-Type"])):
            result = r.content
        else:
            result = r.text

    return result 

# -----

# Start the backup
"""
  We can check the status with the API and would see status like this:
  {
    "last_successful": {
      "host": "10.180.85.102", 
      "message": "", 
      "path": "/home/ultra/system-backups/us-fg2", 
      "subdir": "/home/ultra/system-backups/us-fg2/20260227_1546", 
      "timeStamp": 1772207186, 
      "username": "ultra"
    }, 
    "running": {
      "host": "10.180.85.102", 
      "message": "", 
      "path": "/home/ultra/system-backups/us-fg2", 
      "status": "COMPLETED", (or "EXECUTING" or "ERROR")

      "timeStamp": 1772207186, 
      "username": "ultra"
    }
  }
"""
#
def fg_backup (fghost, basic_auth_hdr, desthost, dpath, duser, dpass, key):
    backup_api = '/api/mgmt.gateway_backup/1.0/backup'
    
    # check if a backup is running
    result = appliance_rest_call ('GET', fghost, basic_auth_hdr, backup_api)
    if result == None:
        fail ("failed to get current backup status")
    running = result[0]['running']
    if running['status'] == 'Executing':
        return 'Backup is already Running'
        
    # start the backup
    backup_spec = { "hostname" : desthost, "username" : duser, "password" : dpass, "path" : dpath, "security_pwd" : key }
    result = appliance_rest_call ('POST', fghost, basic_auth_hdr, backup_api, payload = backup_spec)
    if result == None:
        print(result)
        fail ("failed to start new backup")

    # while backup is running...
    completed = 0
    while completed == 0:
        time.sleep(10)
        result = appliance_rest_call ('GET', fghost, basic_auth_hdr, backup_api)
        if result == None:
            fail ("failed to get current backup status")
        running = result[0]['running']
        if running['status'] == 'COMPLETED':
            completed = 1
        elif running['status'] == 'ERROR':
            return "New backup Failed"
        print('Backup still running')
    return "Backup succeeded"

# -----
# MAIN
#
def main ():
    
    # -----------------------------------------------------------------------------
    # Parse the arguments
    #
    parser = argparse.ArgumentParser (description="Automated backup of a Flow gateway appliance")
    parser.add_argument('--fghost', help='the Flow Gateway host')
    parser.add_argument('--fguser')
    parser.add_argument('--fgpass')
    parser.add_argument('--desthost')
    parser.add_argument('--destuser')
    parser.add_argument('--destpass')
    parser.add_argument('--destpath')
    parser.add_argument('--key', help="the encryption key to be used for encrypting the backup data")
    parser.add_argument('--trim', help="tells the script to trim the stored backups to the most recent N files")
    args = parser.parse_args ()
    
    # 
    keep_count = 0
    if args.fghost == None:
        print ("Please specify a hostname or IP{ address for the Flow Gateway appliance using --fghost")
        return
    if args.desthost == None:
        print ("Please specify a hostname for the destination host (backup target) using --desthost")
        return
    if args.fguser == None:
        print ("Please specify a username for the Flow Gateway appliance using --fguser")
        return
    if args.destuser == None:
        print ("Please specify a username for the backup server using --destuser")
        return
    if args.destpath == None:
        print ("Please specify the path to the destination directory on the backup server")
        return
    if args.key == None:
        print ("Please specify the encryption key to be used for the backup data")
        return
    if args.trim != None:
        keep_count = int(args.trim)
    if args.fgpass == None:
        print ("Please provide the password for the Flow Gateway appliance for user %s" % args.fguser)
        fgpass = getpass.getpass ()
    else:
        fgpass = args.fgpass
    if args.destpass == None:
        print ("Please provide the password for the backup server for account %s" % args.destuser)
        destpass = getpass.getpass ()
    else:
        destpass = args.destpass
    # done

    basic_auth_hdr = create_basic_auth (args.fguser, fgpass)
    if basic_auth_hdr == None:
        fail("Failed to create a BASIC auth header using the given credentials")
    
    # Check that we can connect to the target appliance
    #
    result = appliance_rest_call ('GET', args.fghost, basic_auth_hdr, '/api/cascade.aaa/1.0/keepalive')
    if result == None:
        fail('FG host not accessible or auth data not correct')
    # print('FG Host successfully connected to')
    
    status = fg_backup (args.fghost, basic_auth_hdr, args.desthost, args.destpath, args.destuser, destpass, args.key)
    print (status)
    
    # We will now remove all but the three most recent backups but this assumes the script is running
    # on the destination host...
    #
    if keep_count > 0:
        print('Trimming backup folder to the most recent', keep_count, 'backups')
        for filename in sorted(os.listdir(args.destpath))[:-keep_count]:
            filename_relPath = os.path.join(args.destpath,filename)
            print('deleting ' + filename_relPath)
            shutil.rmtree(filename_relPath)
    
if __name__ == "__main__":
    main ()
# done
