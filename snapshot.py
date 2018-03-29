#! /usr/bin/python
import argparse
import datetime
import time
import sys
from solidfire.factory import ElementFactory

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
remote_status = []
# start_time is used for debugging run times,
#   it is not required for operations
start_time = datetime.datetime.now()
snap_time = datetime.datetime.now().strftime('%b-%d-%G_%H-%M-%S')
gs_time = "gs-%s" % snap_time

# connect to source, create group snap from volume array
# verify that each volume in the array is reporting that the
#    snapshot from its volume is present on the destination

sfe_source = ElementFactory.create(source_mvip,
                                   source_user,
                                   source_password,
                                   print_ascii_art=False)
group_snap = sfe_source.create_group_snapshot(source_vol_array,
                                 enable_remote_replication=True,
                                 retention=ret_time,
                                 name=gs_time)

for snap in group_snap.members:
    snap_uuid_dict[snap.volume_id]=snap.snapshot_uuid

gs_id = group_snap.group_snapshot_id

# snap_check = sfe_source.list_group_snapshots(group_snapshot_id=gs_id)
# for snap in snap_check.group_snapshots:
    # for s in snap.members:
        # remote_status = s.remote_status
while "Unknown" or "NotPresent" or "Syncing" or "None" in remote_status:
    time.sleep(60)
    print("Sleeping for 60 while snap status is not 100% present on the destination")
    snap_check = sfe_source.list_group_snapshots(group_snapshot_id=gs_id)
    for snap in snap_check.group_snapshots:
        for s in snap.members:
            remote_status.append(s.remote_status)
            print("Remote snap status is {}".format(s.remote_status))

src_vol_info = sfe_source.list_volumes(volume_ids=source_vol_array)
for v in src_vol_info.volumes:
    for p in v.volume_pairs:
        dest_vol_array.append(p.remote_volume_id)
# source_end_time is used for debugging run times,
#   it is not required for operations
source_end_time = datetime.datetime.now()

print("##################################################"
      "\n###########Switching to replication###############"
      "\n##################################################")

# create an array to make sure all volumes are in a safe state
dest_snap_array = []
# dest_start_time is used for debugging run times,
#   it is not required for operations
dest_start_time = datetime.datetime.now()
sfe_dest = ElementFactory.create(dest_mvip,
                                 dest_user,
                                 dest_password,
                                 print_ascii_art=False)

# Ensure all volumes are set to replication targets, if not exit
check_dest_vol = sfe_dest.list_volumes(volume_ids=dest_vol_array)
for vol in check_dest_vol.volumes:
    print("Volume access state is {}, on volume {}".format(vol.access,vol.volume_id))
    if vol.access != "replicationTarget":
        sys.exit("Destination volumes are not in a replication mode")
# Loop through volumes and ensure they are all in an idle state
#    before proceeding with rollback
rollback_vol_array = []
check_dest_vol = sfe_dest.list_volumes(volume_ids=dest_vol_array)
for vol in check_dest_vol.volumes:
    vol_ID = vol.volume_id
    for v in vol.volume_pairs:
        status_array = [v.remote_replication]
        while status_array[0].snapshot_replication.state != "Idle":
            print("Sleeping as replication state is: "
                  "{}".format(status_array[0].snapshot_replication.state))
            time.sleep(30)
            check_dest_vol = sfe_dest.list_volumes(volume_ids=dest_vol_array)
            for vol in check_dest_vol.volumes:
                for v in vol.volume_pairs:
                    status_array = [v.remote_replication]
        # Ensure that snapshots and volumes match, we don't want to rollback
        #    snap ID 37 on every volume with a snap ID 37
        snaps_dest = sfe_dest.list_snapshots(volume_id=vol_ID)
        for snap2 in snaps_dest.snapshots:
            if "rollback-" in snap2.name:
                sfe_dest.delete_snapshot(snap2.snapshot_id)
            print("Looping through snaps, "
                  "snapshot volume is: {}".format(vol_ID))
            if snap2.snapshot_uuid in snap_uuid_dict.values():
                snap_id = snap2.snapshot_id
                # set volume to readWrite to stop replication
                # create a rollback snapshot and replay the
                #    snapshot into the volume
                # reset the volume to replicationTarget for normal ops
                print("Setting read/write on {}".format(vol_ID))
                sfe_dest.modify_volume(vol_ID, access="readWrite")
                print("rolling back on {}".format(vol_ID))
                sfe_dest.rollback_to_snapshot(vol_ID,
                                              snap_id,
                                              True,
                                              name="rollback-" + gs_time)
                sfe_dest.modify_volume(vol_ID, access="replicationTarget")
                rollback_vol_array.append(vol_ID)

if dest_vol_array != rollback_vol_array:
    print("Error...")
    time.sleep(300)
    for vol in rollback_vol_array:
        snaps_rollback = sfe_dest.list_snapshots(volume_id=vol)
        for snap3 in snaps_rollback:
            sfe_dest.snapshot_rollback(vol, snap3.snapshot_id,save_current_state=False)

# Time outputs are used for debugging run times,
#   they are not required for operations
end_time = datetime.datetime.now()
run_time_diff = end_time - start_time
start_time_diff = source_end_time - start_time
dest_time_diff = end_time - dest_start_time
print("Source side run time was: {}".format(start_time_diff))
print("Desitnation side run time was: {}".format(dest_time_diff))
print("Run time was: {}".format(run_time_diff))
