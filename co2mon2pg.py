#!/usr/bin/env python3

# Stream CO2Mon readings to a Postgres database or CSV

# SPDX-FileCopyrightText: © 2023 Georg Sauthoff <mail@gms.tf>
# SPDX-License-Identifier: GPL-3.0-or-later


# See also:
#
# [1]: https://revspace.nl/images/2/2e/ZyAura_CO2_Monitor_Carbon_Dioxide_ZG01_Module_english_manual-1.pdf, page 8


import configargparse
import datetime
import enum
import hid
import signal
import sqlalchemy
import subprocess
import sys
import systemd.daemon
import time

prefix = '/usr'
prog   = 'co2mon2pg'

def parse_args():
    p = configargparse.ArgParser(
            default_config_files=[f'{prefix}/lib/{prog}/config.ini',
                f'/etc/{prog}.ini', f'~/.config/{prog}.ini'])
    p.add('-c', '--config', is_config_file=True,
          help='config file')
    p.add('--csv', action='store_true',
          help='just stream sensor data as csv to stdout')
    p.add('--co2mond', action='store_true',
          help='read CO2Mon through co2mond (e.g. when using an old hardware revision)')
    p.add('--db', default='postgresql:///metricsdb',
          help='PostgreSQL metrics database URL (default: %(default)s)')
    p.add('--debug', action='store_true',
          help='enable verbose output')
    p.add('--device', default='co2mon',
          help='Sensor device id (default: %(default)s)')
    p.add('--dry', action='store_true',
          help="don't actually commit any changes to the database")
    p.add('--every', type=int, default=12,
          help=('Collect every nth value.'
                ' NB: base frequency is 1 value per 5 seconds'
                ' (default: %(default)s)'))
    p.add('--echo', action='store_true',
          help='echo SQLAlchemy statements to the log stream')
    p.add('--old', action='store_true',
          help='read old style of co2mon device (use in combination with --co2mond)')
    p.add('--systemd', action='store_true',
          help='notify systemd during startup')
    args = p.parse_args()
    return args


def yield_co2mond(flags=[]):
    with subprocess.Popen(['co2mond'] + flags, stdout=subprocess.PIPE,
                                               universal_newlines=True) as p:
        for line in p.stdout:
            xs = line.split()
            if len(xs) < 2:
                continue
            if xs[0] == 'Tamb':
                temp_C = float(xs[1])
            elif xs[0] == 'CntR':
                co2_ppm = int(xs[1])
                if temp_C is not None:
                    yield co2_ppm, temp_C
                    temp_C = None



def is_valid(xs):
    checksum = sum(xs[:3]) % 256
    if checksum != xs[3]:
        return False
    if xs[4] != 0xd:
        return False
    return True


# cf. [1]
class CO2Mon_Item(enum.IntEnum):
    TEMP_C  = 0x42
    CO2_PPM = 0x50

def yield_co2mon():
    d = hid.device()
    # i.e. 'manufacturer_string': 'Holtek'
    #      'product_string'     : 'USB-zyTemp'
    # NB: release=0x0100 / serial=1.40 devices obfuscate their payload,
    #     while release=0x0200 / serial=2.00 don't
    #     we only support the latter for now
    #     cf. co2mon how to decode/descramble their payload
    d.open(vendor_id=0x4d9, product_id=0xa052, serial_number='2.00')

    # tell device to transmit data
    # yup, still required with release 2 devices
    # although they don't use that 'report' to scramble the data, anymore
    r = d.send_feature_report([0] * 8)
    if r == -1:
        raise RuntimeError("co2mon device didn't accept 'feature report'")

    try:
        temp_C = None
        while True:
            xs = d.read(5, timeout_ms=5000)
            if xs == -1:
                raise RuntimeError("co2mon read error")

            hx = [ hex(x) for x in xs ]
            if not is_valid(xs):
                continue
            v = (xs[1] << 8) + xs[2]
            if   xs[0] == CO2Mon_Item.TEMP_C:
                temp_C = v / 16 - 273.15       # cf. [1]
            elif xs[0] == CO2Mon_Item.CO2_PPM:
                co2_ppm = v
                if temp_C is not None:
                    yield co2_ppm, temp_C
                    temp_C = None

    finally:
        d.close()


def tail_co2mon(args, db, metrics_ins):
    flags = [] if args.old else ['-n']
    i = 0
    ys = yield_co2mond(flags) if args.co2mond else yield_co2mon()
    for co2_ppm, temp_C in ys:
        i += 1
        if i < args.every:
            continue
        if args.csv:
            ts = int(time.time())
            print(f'{ts},{co2_ppm},{temp_C}')
            i = 0
            continue

        if args.debug:
            ts = int(time.time())
            print(f'{ts} {co2_ppm} {temp_C}')
        db.execute(metrics_ins, {
            'time'     : datetime.datetime.now(datetime.timezone.utc),
            'device_id': args.device,
            'pl'       : { 'temp_C': temp_C, 'co2_ppm': co2_ppm }
            })
        if args.dry:
            db.rollback()
        else:
            db.commit()
        i = 0

def on_sigterm(sig, frm):
    # raise this as we already deal with it ...
    raise KeyboardInterrupt()

def mainP():
    signal.signal(signal.SIGTERM, on_sigterm)
    args   = parse_args()

    if args.csv:
        tail_co2mon(args, None, None)

    engine = sqlalchemy.create_engine(args.db, echo=args.echo, future=True)
    with engine.connect() as db:
        db.execute(sqlalchemy.text('SET synchronous_commit = off'))
        meta          = sqlalchemy.MetaData()
        metrics_table = sqlalchemy.Table('metrics', meta, autoload_with=engine)
        metrics_ins   = metrics_table.insert()

        if args.systemd:
            systemd.daemon.notify('READY=1')

        tail_co2mon(args, db, metrics_ins)


def main():
    try:
        return mainP()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    sys.exit(main())

