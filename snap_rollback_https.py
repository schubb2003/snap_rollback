#! /usr/bin/python
import argparse
import datetime
import time
import sys
import requests
import base64
import json

parser = argparse.ArgumentParser()
parser.add_argument('-srcmv', type=str,
                    required=True,
                    metavar='mvip',
                    help='MVIP name or IP')
parser.add_argument('-srcun', type=str,
                    required=True,
                    metavar='username',
                    help='username to connect with')
parser.add_argument('-srcpw', type=str,
                    required=True,
                    metavar='password',
                    help='password for user')
parser.add_argument('-dstmv', type=str,
                    required=True,
                    metavar='mvip',
                    help='MVIP name or IP')
parser.add_argument('-dstun', type=str,
                    required=True,
                    metavar='username',
                    help='username to connect with')
parser.add_argument('-dstpw', type=str,
                    required=True,
                    metavar='password',
                    help='password for user')
parser.add_argument('-rt', type=str,
                    required=True,
                    metavar='ret_time',
                    help='retention time for snapshot, HH:mm:ss')
parser.add_argument('-va', nargs='+',
                    type=int,
                    required=True,
                    metavar='source_vol_array',
                    help='Enter the volumes to be a group with no spaces')
args = parser.parse_args()

source_mvip = args.srcmv
source_user = args.srcun
source_password = args.srcpw
dest_mvip = args.dstmv
dest_user = args.dstun
dest_password = args.dstpw
ret_time = args.rt
source_vol_array = args.va

dest_vol_array = []
snap_uuid_dict = {}

# start_time is used for debugging run times,
#   it is not required for operations
start_time = datetime.datetime.now()
snap_time = datetime.datetime.now().strftime('%b-%d-%G_%H-%M-%S')
gs_time = "gs-%s" % snap_time
rollback_name = gs_time + "-rollback"
vol_list = list(source_vol_array)
murl = "/json-rpc/9.0/"
confirm_true = 'true'
confirm_false = 'false'

# connect to source, create group snap from volume array
# verify that each volume in the array is reporting that the
#    snapshot from its volume is present on the destination

def srcPost(source_mvip, murl, source_user, source_password, jsonData):
    #REST URL
    url=("https://" + source_mvip + ":443" + murl)
    #Build user auth
    src_auth = (source_user +":"+ source_password)
    src_encodeKey = base64.b64encode(src_auth.encode('utf-8'))
    src_basicAuth = bytes.decode(src_encodeKey)
    print("-------------------------------------")
    #Set REST parameters
    headers = {
        'content-type': "application/json",
        'authorization': "Basic " + src_basicAuth
        }
    try:
        payload = (jsonData)
        ##For areas without proper certs, uncomment the line blow and comment out three lines down
        ##this line - response = requests.request("POST", url, data=payload, headers=headers)
        src_response = requests.request("POST", url, data=payload, headers=headers, verify=False)
        ##For production with proper certs uncomment the line below and comment out the line above
        #response = requests.request("POST", url, data=payload, headers=headers)
        jsonResponse=json.loads(response.text)
        #print("Response in try: " + src_response.text)
    except:
        sys.exit("Unable to connect to host: " + source_mvip + "\n\tWarning in except" + src_response.text)

    #Check to see if we got a valid jsonResponse
    if 'result' not in jsonResponse:
        sys.exit("Invalid response received.\n\tResponse validity: " + src_response.text)
    else:
        return jsonResponse['result']

def destPost(dest_mvip, murl, dest_user, dest_password, dest_jsonData):
    #REST URL
    url=("https://" + dest_mvip + ":443" + murl)
    #Build user auth
    dest_auth = (dest_user +":"+ dest_password)
    dest_encodeKey = base64.b64encode(dest_auth.encode('utf-8'))
    dest_basicAuth = bytes.decode(dest_encodeKey)
    print("-------------------------------------")
    #Set REST parameters
    headers = {
        'content-type': "application/json",
        'authorization': "Basic " + dest_basicAuth
        }
    try:
        payload = (dest_jsonData)
        ##For areas without proper certs, uncomment the line blow and comment out three lines down
        ##this line - response = requests.request("POST", url, data=payload, headers=headers)
        dest_response = requests.request("POST", url, data=payload, headers=headers, verify=False)
        ##For production with proper certs uncomment the line below and comment out the line above
        #response = requests.request("POST", url, data=payload, headers=headers)
        jsonResponse=json.loads(dest_response.text)
        #print("Response in try: " + dest_response.text)
    except:
        sys.exit("Unable to connect to host: " + dest_mvip + "\n\tWarning in except" + dest_response.text)

    #Check to see if we got a valid jsonResponse
    if 'result' not in jsonResponse:
        sys.exit("Invalid response received.\n\tResponse validity: " + dest_response.text)
    else:
        return jsonResponse['result']

def main():
    jsonData=json.dumps({"method": "CreateGroupSnapshot","params": {"enableRemoteReplication": 'true', "volumes": source_vol_array, "retention": ret_time, "name": gs_time }, "id": 1})
    response=srcPost(source_mvip, murl, source_user, source_password, jsonData)
    details=response['groupSnapshot']
    gs_id=(details['groupSnapshotID'])

    # Build a dictionary of snapshot UUID to ensure we have the snaps later
    for member in details['members']:
        snap_uuid_dict[member["snapshotUUID"]]=member["volumeID"]

    # set remote_status to start while loop
    remote_status = ["Unknown"]
    # Loop waits for the snapshot to be replicated before proceeding
    while "Unknown" in remote_status or "NotPresent" in remote_status or "Syncing" in remote_status or "None" in remote_status:
        remote_status = []
        print("**********\nSleeping 60 seconds to wait for snap to replicate\n**********")
        time.sleep(60)
        jsonData=json.dumps({"method": "ListGroupSnapshots","params": {"groupSnapshotID": gs_id }, "id": 1})
        response=srcPost(source_mvip, murl, source_user, source_password, jsonData)
        snap_state_details=response['groupSnapshots']
        for snap in snap_state_details:
            for member in snap['members']:
                remote_status.append(member['remoteStatus'])
        # prints our status instead of having to guess what it is
        print("##########\nremote status is: {}\n##########".format(remote_status))

    # Get the remove volume pair IDs for matching vol info later on 
    jsonData=json.dumps({"method": "ListVolumes","params": {"volumeIDs": source_vol_array }, "id": 1})
    response=srcPost(source_mvip, murl, source_user, source_password, jsonData)
    remote_vol_details=response['volumes']
    for vol in remote_vol_details:
        for remote in vol['volumePairs']:
            dest_vol_array.append(remote['remoteVolumeID'])

    print("##################################################"
          "\n###########Switching to replication###############"
          "\n##################################################")

    dest_snap_array = []
    rollback_vol_array = []
    # print("Destination volume IDs are: {}".format(dest_vol_array))

    # Get destination volume information for processing
    dest_jsonData=json.dumps({"method": "ListVolumes","params": {"volumeIDs": dest_vol_array }, "id": 1})
    dest_response=destPost(dest_mvip, murl, dest_user, dest_password, dest_jsonData)
    dest_vol_details=dest_response['volumes']
    # Loop through volumes to determine if they are in a state to replicate
    for vol in dest_vol_details:
        if vol['access'] != 'replicationTarget':
            sys.exit("Destination volumes are not in a replication state")
        else:
            for pair in vol['volumePairs']:
                current = (pair['remoteReplication']['snapshotReplication'])
                # Ensure volume is idle and ready to rollback
                while current['state'] != "Idle":
                    status_array=[]
                    dest_jsonData=json.dumps({"method": "ListVolumes","params": {"volumeIDs": dest_vol_array }, "id": 1})
                    dest_response=destPost(dest_mvip, murl, dest_user, dest_password, dest_jsonData)
                    dest_vol_details=dest_response['volumes']
                    status_array.append(item)
                    time.sleep(60)
                # List snaps to do the rollback if they match vol/snap vol ID and snapshot UUIDs
                dest_jsonData=json.dumps({"method": "ListSnapshots","params": {"volumeID": vol['volumeID']}, "id": 1})
                dest_response=destPost(dest_mvip, murl, dest_user, dest_password, dest_jsonData)
                dest_snap_details=dest_response['snapshots']
                for snap in dest_snap_details:
                    # This section just prints the snap info for comparison
                    # print("**********\n**********\n" 
                          # "Snap dictionary contains: {}"
                          # "\n**********\n**********".format(snap_uuid_dict))
                    # print("**********\nSnapshot UUID is: {}"
                          # "\n**********\nSnapshot volume ID is {}"
                          # "\n**********\n**********\nVolume ID in loop is {}"
                          # "\n**********".format(snap['snapshotUUID'],
                                                # snap['volumeID'],
                                                # vol['volumeID']))
                    # Remove previous rollback snapshots if they exist
                    if "-rollback" in snap['name']:
                        dest_jsonData=json.dumps({"method": "DeleteSnapshot","params": {"snapshotID": snap['snapshotID'] }, "id": 1})
                        dest_response=destPost(dest_mvip, murl, dest_user, dest_password, dest_jsonData)
                        #dest_snap_details=dest_response['snapshot']
                    # Compare vol/snap vol, then snapshot UUID to ensure we are doing the work on the right volume
                    #   with the right snapshot
                    elif snap['snapshotUUID'] in snap_uuid_dict.keys() and snap['volumeID'] == vol['volumeID']:
                        dest_jsonData=json.dumps({"method": "ModifyVolume","params": {"volumeID": snap['volumeID'],"access": "readWrite" }, "id": 1})
                        dest_response=destPost(dest_mvip, murl, dest_user, dest_password, dest_jsonData)
                        mod_vol_details=dest_response['volume']
                        # If the volume is in a readWrite state, fail out
                        if mod_vol_details['access'] != 'readWrite':
                            sys.exit("Volume in incorrect state, not readWrite.  \nState is {}".format(mod_vol_details['access']))
                        # If the volume is not readWrite, change it to readWrite and rollback
                        # This may seem to contradict the above section, but it does not.  We want the volume to be replicationTarget
                        #   as it means it is replicating.  However we need to change it to readWrite to roll the snapshot back
                        else:   
                            dest_jsonData=json.dumps({"method": "RollbackToSnapshot","params": {"volumeID": snap['volumeID'],"snapshotID": snap['snapshotID'], "saveCurrentState": confirm_true,"name": rollback_name }, "id": 1})
                            dest_response=destPost(dest_mvip, murl, dest_user, dest_password, dest_jsonData)
                            rollback_details=dest_response['snapshot']
                            # Fail the script if the rollback failed for some reason
                            if rollback_details['status'] != 'done':
                                sys.exit("Error in rollback")
                            print("*********\nRollback complete on: {}\n**********".format(vol['name']))
                        # Reset vol to replicationTarget so replication can continue
                        dest_jsonData=json.dumps({"method": "ModifyVolume","params": {"volumeID": snap['volumeID'],"access": "replicationTarget" }, "id": 1})
                        dest_response=destPost(dest_mvip, murl, dest_user, dest_password, dest_jsonData)
                        mod_vol_details=dest_response['volume']
                    # If snap UUID not found in dictionary, restart loop with next snap
                    elif snap['snapshotUUID'] not in snap_uuid_dict.keys():
                        continue
                    else:
                        sys.exit("Unhandled exception")
                        
if __name__ == "__main__":
    main()
