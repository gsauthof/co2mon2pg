This repository contains co2mon2pg, a Python program that streams
CO2 (and temperature) readings of certain devices to a PostgreSQL
database or stdout (CSV).

2023, Georg Sauthoff


## Quickstart

1. Copy `co2mon2pg.py` to `/usr/local/bin/co2mon2pg`
2. Copy `co2mon2pq.service` to `/etc/systemd/system`
3. Create metricsdb user
4. systemctl daemon-reload
5. Create metricsdb Postgres database and metrics table,
   similar to this [schema](https://github.com/gsauthof/lorawan#table-schema)
   (i.e. only the time, device_id and pl columns are required)
6. Copy `99-co2mon.rules` to `/etc/udev/rules.d`
7. Plugin CO2Mon deivce
8. Start service `systemctl enable --now co2mon2pq`

Some steps of the setup are available as an Ansible role, in this repository.
Example usage:

```
ansible-playbook -i hosts co2mon.yml --diff
```

## Grafana Integration

Using the Postgres datasource, the collected data can be
integrated into a Grafana panel with a query like this:

```
SELECT
  $__timeGroupAlias("time",$__interval),
  avg((pl->'co2_ppm')::int) AS "CO2",
  device_id
FROM metrics
WHERE
  $__timeFilter("time")
GROUP BY 1, device_id
ORDER BY 1
```

NB: The temperature field is named `temp_C`.


## CSV Output

For Telegraf integration (using the [execd telegraf plugin][13]), troubleshooting etc.
one can call `co2mon2pg.py` from the command line like this:

```
./co2mon2pg.py --csv
```

In that mode it writes all readings in CSV format to stdout.

Example output:

```
1677453865,1302,20.600000000000023
1677453925,1147,20.537500000000023
1677453986,987,20.475000000000023
```


## Supported Devices

co2mon2pg supports certain CO2 monitor USB devices that identify as:

```
vendor_id     : 0x04d9
product_id    : 0xa052
release_number: 0x0200
serial_number : 2.00
```

NB: There are older devices with release number `0x0100` and serial number
`1.40` that obfuscate their payload ([see also][2]). See the Related Projects Section
for details on how to decode such payload.

I tested it with the 'TFA AIRCO2NTROL MINI CO2 Monitor' (EAN 4009816027351,
Kat.-Nr. 31.5006.02, ID-NR. 31.010 180) which I bought via and from Amazon.de.

The 'TFA AIRCO2NTROL MINI CO2 Monitor' device seems to be a rebranded version of
[ZyAura's ZGm053U][1].

## Related Projects

- [Reverse-Engineering a low-cost USB CO₂ monitor][3] (hackaday.io, 2015), entertaining reverse engineering journey of the release 1 device, including Wiresharking the USB traffic and transcribing the descrambling code with IDA
- [CO2MeterHacking][4] (revspace.nl, 2014-2018), reverse engineering documentation
of a similar device that exposes the payload over a RJ45 serial port (without obfuscation)
- [dmage/co2mon][5] - C program that reads from relase 1 and 2 devices, uses hidapi library, packaged by Fedora
- [JsBergbau/TFACO2AirCO2ntrol_CO2Meter][6] - Python 3 script based on the hackaday findings, supports release 1 and 2 devices. A release 2 device is assumed when the checksum is valid, before applying descrambling. It directly accesses a hidraw device without using the hidapi library.
- [vshmoylov/libholtekco2][7] - C program that supports only release 1 devices, also uses hidapi library, looks like it also runs under Windows, but comes without any makefile
- [heinemml/CO2Meter][8] - Python 2/3 script, supports release 1 and 2 devices, detects release 2 by checking the position of the `0xd` sentinel, also uses a hidraw device, instead of using the hidapi Python package
- [vit1251/rs-co2mon][9] - Rust program, only support release 1 devices, also uses hidapi library
- [MiniMon][10] (sourceforge, no VCS repository) - Python program, supports release 1 and 2 devices via hidraw, similar to heinemml/CO2Meter

Of the co2mon interfacing Python programs, co2mon2pg is the only
one that uses the hidapi library.
In contrast to many other software, co2mon2pg doesn't support
release 1 devices (although added support is straight forward).
More importantly, co2mon2pg's main distinguishing feature is that
it supports writing the sensor data to a PostgreSQL database.


## Device Documentation

- [ZyAura ZG01 CO2 Module User Manual][12] (2013), NB: as of 2023,
  ZyAura markets the ZG09 CO2 module
- [CO2 device RS232 serial communication protocol application note AN146-RAD-0401][11] (2012)


[1]: https://www.zyaura.com/product-detail/zgm053u/
[2]: https://github.com/dmage/co2mon/issues/41#issuecomment-1430523844
[3]: https://hackaday.io/project/5301/logs?sort=oldest
[4]: https://revspace.nl/CO2MeterHacking
[5]: https://github.com/dmage/co2mon
[6]: https://github.com/JsBergbau/TFACO2AirCO2ntrol_CO2Meter
[7]: https://github.com/vshmoylov/libholtekco2
[8]: https://github.com/heinemml/CO2Meter
[9]: https://github.com/vit1251/rs-co2mon
[10]: https://sourceforge.net/projects/minimon/files/
[11]: http://co2meters.com/Documentation/AppNotes/AN146-RAD-0401-serial-communication.pdf
[12]: https://revspace.nl/images/2/2e/ZyAura_CO2_Monitor_Carbon_Dioxide_ZG01_Module_english_manual-1.pdf
[13]: https://github.com/influxdata/telegraf/blob/master/plugins/inputs/execd/README.md


