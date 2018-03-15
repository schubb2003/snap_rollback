#! /usr/bin/python
import argparse
import datetime
import time
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

snap_time = datetime.datetime.now().strftime('%b-%d-%I%M%p-%G')
gs_time = "gs-%s" % snap_time
i = 0
l = 1

# connect to source, create group snap from volume array
# verify that each volume in the array is reporting that the snapshot from its volume is present on the destination
sfe_source = ElementFactory.create(source_mvip,source_user,source_password)
sfe_source.create_group_snapshot(source_vol_array,enable_remote_replication=True,retention=ret_time,name=gs_time)
snaps_group_source = sfe_source.list_group_snapshots(source_vol_array)
count_snap_source = len(source_vol_array)
for snap in snaps_group_source.group_snapshots:
    gs_uuid_source = snap.group_snapshot_uuid
source_snaps = sfe_source.list_snapshots()
for snap in source_snaps.snapshots:
    if gs_uuid_source == snap.group_snapshot_uuid:
        while "remote_status='Present'" not in str(snap.remote_statuses):
            print("Sleeping as snapshot is not reported as present on remote")
            time.sleep(60)
            i = i + 60
            l = l + 1
            print(("%s seconds have elapsed" % i) + \
                  "\nLoop #%s has started" % l)
            for snap in snaps_group_source.group_snapshots:
                gs_uuid_source = snap.group_snapshot_uuid
                source_snaps = sfe_source.list_snapshots()
                for snap in source_snaps.snapshots:
                    snap_status = snap.remote_statuses

di = 0
dl = 1
# create an array to make sure all volumes are in a safe state
dest_vol_array = []
sfe_dest = ElementFactory.create(dest_mvip,dest_user,dest_password)
snaps_dest = sfe_dest.list_snapshots()
# rollback snapshots, you must do each volume separately
# verify replication state is idle, change vol to read/write, rollback, reset to replication
for snap2 in snaps_dest.snapshots:
    if snap2.name == 'rollback':
        sfe_dest.delete_snapshot(snap2.snapshot_id)
    if gs_uuid_source == snap2.group_snapshot_uuid:
        dest_vol_array.append(snap2.volume_id)
        # print("vol array is %s" % dest_vol_array)
dest_vol_array = set(dest_vol_array)
count_snap_dest = len(dest_vol_array)
if count_snap_source != count_snap_dest:
    sys.exit("Incorrect snap count, unable to proceed")
# for dest_vol in dest_vol_array:
    check_dest_vol = sfe_dest.list_volumes()
    for vol in check_dest_vol.volumes:
        repl_status = vol.volume_pairs
        while "snapshot_replication=SnapshotReplication(state='Idle'" not in str(repl_status):
            print("Sleeping as replication state is not idle")
            time.sleep(60)
            di = di + 60
            dl = dl + 1
            print(("%s seconds have elapsed" % di) + \
                  "\nLoop #%s has started" % dl)
            for dest_vol in dest_vol_array:
                check_dest_vol = sfe_dest.list_volumes()
                for vol in check_dest_vol.volumes:
                    repl_status = vol.volume_pairs
    print(dest_vol)
    sfe_dest.modify_volume(dest_vol,access="readWrite")
    sfe_dest.rollback_to_snapshot(dest_vol,snap2.snapshot_id,True,name="rollback")
    sfe_dest.modify_volume(dest_vol,access="replicationTarget")
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
snap_dict = {}
snap_time = datetime.datetime.now().strftime('%b-%d-%I%M%p-%G')
gs_time = "gs-%s" % snap_time
i = 0
l = 1

# connect to source, create group snap from volume array
# verify that each volume in the array is reporting that the snapshot from its volume is present on the destination
sfe_source = ElementFactory.create(source_mvip,source_user,source_password,print_ascii_art=False)
sfe_source.create_group_snapshot(source_vol_array,enable_remote_replication=True,retention=ret_time,name=gs_time)
snaps_group_source = sfe_source.list_group_snapshots(source_vol_array)
count_snap_source = len(source_vol_array)
for snap in snaps_group_source.group_snapshots:
    if gs_time in snap.name:
        gs_uuid_source = snap.group_snapshot_uuid

source_snaps = sfe_source.list_snapshots()
for snap1 in source_snaps.snapshots:
    snap_dict[snap1.volume_id] = snap1.snapshot_id
    if gs_time in snap.name:
        while "remote_status='Present'" not in str(snap1.remote_statuses):
            print("Sleeping as snapshot is not reported as present on remote")
            time.sleep(60)
            i = i + 60
            l = l + 1
            print(("%s seconds have elapsed" % i) + \
                  "\nLoop #%s has started" % l)
            for snap1 in snaps_group_source.group_snapshots:
                gs_uuid_source = snap.group_snapshot_uuid
                source_snaps = sfe_source.list_snapshots()
                for snap1 in source_snaps.snapshots:
                    snap_status = snap1.remote_statuses

print("##################################################"
      "\n###########Switching to replication###############"
      "\n##################################################")

di = 0
dl = 1
# create an array to make sure all volumes are in a safe state
dest_vol_array = []
sfe_dest = ElementFactory.create(dest_mvip,dest_user,dest_password,print_ascii_art=False)
snaps_dest = sfe_dest.list_snapshots()
# rollback snapshots, you must do each volume separately
# verify replication state is idle, change vol to read/write, rollback, reset to replication
for snap2 in snaps_dest.snapshots:
    if snap2.name == 'rollback':
        sfe_dest.delete_snapshot(snap2.snapshot_id)
    if gs_time in snap2.name:
        dest_vol_array.append(snap2.volume_id)
        # print("vol array is %s" % dest_vol_array)
print(dest_vol_array)

count_snap_dest = len(dest_vol_array)
if count_snap_dest != count_snap_source:
    sys.exit("Incorrect snap count, unable to proceed")
# for dest_vol in dest_vol_array:
check_dest_vol = sfe_dest.list_volumes()
for vol in check_dest_vol.volumes:
    if vol.volume_id in dest_vol_array:
        repl_status = vol.volume_pairs
        print(repl_status)
        while "snapshot_replication=SnapshotReplication(state='Idle'" not in str(repl_status):
            print("Sleeping as replication state is not idle")
            time.sleep(30)
            di = di + 30
            dl = dl + 1
            print(("%s seconds have elapsed" % di) + \
                  "\nLoop #%s has started" % dl)
            check_dest_vol = sfe_dest.list_volumes()
            for vol in check_dest_vol.volumes:
                if vol.volume_id in dest_vol_array:
                    repl_status = vol.volume_pairs
                    #print(repl_status)
        print(vol.volume_id)
        key = vol.volume_id
        for key in snap_dict:
            sfe_dest.modify_volume(vol.volume_id,access="readWrite")
            sfe_dest.rollback_to_snapshot(vol.volume_id,snap3.snapshot_id,True,name="rollback")
            sfe_dest.modify_volume(vol.volume_id,access="replicationTarget")
