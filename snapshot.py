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

start_time = datetime.datetime.now()

dest_vol_array = []
snap_dict = {}
snap_time = datetime.datetime.now().strftime('%b-%d-%G_%H-%M-%S')
gs_time = "gs-%s" % snap_time

# connect to source, create group snap from volume array
# verify that each volume in the array is reporting that the
#    snapshot from its volume is present on the destination
sfe_source = ElementFactory.create(source_mvip,
                                   source_user,
                                   source_password,
                                   print_ascii_art=False)
sfe_source.create_group_snapshot(source_vol_array,
                                 enable_remote_replication=True,
                                 retention=ret_time,
                                 name=gs_time)
snaps_group_source = sfe_source.list_group_snapshots(source_vol_array)
count_snap_source = len(source_vol_array)

src_vol_info = sfe_source.list_volumes(volume_ids=source_vol_array)
for v in src_vol_info.volumes:
    for p in v.volume_pairs:
        dest_vol_array.append(p.remote_volume_id)

for snap in snaps_group_source.group_snapshots:
    if gs_time in snap.name:
        gs_uuid_source = snap.group_snapshot_uuid

for vol in src_vol_info.volumes:
    source_snaps = sfe_source.list_snapshots(volume_id = vol.volume_id)
    # Create loop to ensure the snapshot is seen
    #    on the destination before proceeding
    for snap1 in source_snaps.snapshots:
        if gs_time in snap1.name:
            snap_dict[snap1.volume_id] = snap1.snapshot_uuid
            for s in snap1.remote_statuses:
               if s.remote_status != "Present":
                print("Sleeping as snapshot status is: {}".format(s.remote_status))
                time.sleep(60)
                source_snaps = sfe_source.list_snapshots(volume_id = vol.volume_id)
                for snap1 in snaps_group_source.group_snapshots:
                    gs_uuid_source = snap.group_snapshot_uuid
                    for snap1 in source_snaps.snapshots:
                        snap_status = snap1.remote_statuses

print("##################################################"
      "\n###########Switching to replication###############"
      "\n##################################################")
      
print("snap dictionary is {}".format(snap_dict))

# create an array to make sure all volumes are in a safe state
dest_snap_array = []
sfe_dest = ElementFactory.create(dest_mvip,
                                 dest_user,
                                 dest_password,
                                 print_ascii_art=False)

# Loop through volumes and ensure they are all in an idle state
#    before proceeding with rollback
check_dest_vol = sfe_dest.list_volumes(volume_ids=dest_vol_array)
for vol in check_dest_vol.volumes:
    vol_ID = vol.volume_id
    for v in vol.volume_pairs:
        status_array = [v.remote_replication]
        while status_array[0].snapshot_replication.state != "Idle":
            print("Sleeping as replication state is: {}".format(status_array[0].snapshot_replication.state))
            time.sleep(30)
            check_dest_vol = sfe_dest.list_volumes(volume_ids=dest_vol_array)
            for vol in check_dest_vol.volumes:
                for v in vol.volume_pairs:
                    status_array = [v.remote_replication]
        # Ensure that snapshots and volumes match, we don't want to rollback
        #    snap ID 37 on every volume with a snap ID 37
        snaps_dest = sfe_dest.list_snapshots(volume_id=vol_ID)
        for snap2 in snaps_dest.snapshots:
            print("Looping through snaps, snapshot volume is: {}".format(vol_ID))
            if snap2.snapshot_uuid in snap_dict.values():
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
                                              name="rollback")
                sfe_dest.modify_volume(vol_ID, access="replicationTarget")

end_time = datetime.datetime.now()

time_diff = end_time - start_time
print("Run time was: {}".format(time_diff))