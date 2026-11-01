# Entrix

A low-cost, outdoor access controller for electrically operated doors and gates.

* Users open the door with a **433 MHz RF remote**. Every remote has a unique ID that the
  controller checks against its user list.
* Admins can **add, remove and temporarily disable** users from a phone or laptop, using Bluetooth
  LE or the unit's own Wi-Fi hotspot. An optional Zigbee mesh gives central management.
* Every access attempt is **logged with a timestamp**.
* Users and logs **survive power loss**.
* Built around an **ESP32-C6** for about **$11–13 per door** in volume.

## Documentation

* [Hardware design](docs/hardware-design.md): component choices, power, storage, enclosure, pin
  map, BOM and cost.
* [Schematic, Rev A draft (PDF)](hardware/schematic/entrix-schematic-revA.pdf), with the
  [netlist](hardware/schematic/netlist.md) and [BOM](hardware/schematic/bom.csv).
