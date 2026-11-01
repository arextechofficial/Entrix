# Entrix — Hardware Design (v0.1, draft)

> **Status:** proposal for review.
> Prices are approximate 2025–26 LCSC / AliExpress prices and will vary by supplier and quantity.

Entrix is a small controller installed at each electrically operated door or gate. Users open the
door with a 433 MHz RF remote. Each remote has a unique ID, which the controller checks against its
own user list. An admin can add, remove and temporarily disable users, and every access attempt is
logged.

---

## 1. Summary

One small board per door, built from:

* an **ESP32-C6** module (~$3), which has **Bluetooth LE, Zigbee and Wi-Fi** in one chip,
* a **433 MHz superheterodyne receiver** (~$1) for the remotes,
* a **dry-contact relay** that drives any type of electric door,
* a **battery-backed real-time clock (RTC)** so log entries have correct timestamps,
* **power-loss-safe storage** of users and logs in the module's own flash memory,
* an **IP65 outdoor box** powered from the door's existing 12–24 V supply.

| Requirement | How it is met |
|---|---|
| 1. Outdoor installation | IP65/66 polycarbonate box, breather vent, conformal coating, parts rated −40…+85 °C, surge/ESD protection on every wire that leaves the box |
| 2. No Wi-Fi/Ethernet nearby; Bluetooth/Zigbee preferred | The unit needs no network. The admin connects to it directly over **Bluetooth LE** or the **unit's own Wi-Fi hotspot**. Optional **Zigbee mesh** to one gateway gives central management. Optional LoRa/RS485 footprints for doors that are very far away |
| 3. Survives power loss | Users and logs live in on-module flash under power-fail-safe file systems (NVS / LittleFS + CRC-checked append-only log). The RTC runs on a coin cell during outages |
| 4. Access logs | Ring buffer of about 65,000 events, timestamped by the RTC, exportable as CSV or synced over Zigbee |
| 5. As cheap as possible | **≈ $11–13 per door** at 100 pcs on a custom PCB, ≈ $13–23 for a prototype built from modules. Remotes cost $1–3 each |

---

## 2. System overview

```
  RF remote (1 per user)
  ┌───────┐   433.92 MHz
  │ A   B │ ~~~~~~~~~~~~~~~~┐
  │ C   D │                 │
  └───────┘                 ▼
┌──────────────────── Entrix door unit (IP65 box) ─────────────────────┐
│                                                                      │
│  ┌───────────┐ DATA ┌─────────────────────┐ GPIO ┌────────┐          │  NO / COM / NC
│  │ RXB6 433  ├─────►│                     ├─────►│ Relay  ├──────────┼──► lock / gate
│  │ receiver  │      │      ESP32-C6       │      └────────┘          │    "open" input
│  └───────────┘      │ BLE + Zigbee + WiFi │◄──── door contact, exit  │
│  ┌───────────┐ I²C  │ 8 MB flash:         │      button, tamper      │
│  │ RTC +     ├─────►│  users + logs       ├────► LED + buzzer        │
│  │ coin cell │      └──────────┬──────────┘                          │
│  └───────────┘                 │ 2.4 GHz                             │
│  12–24 V AC/DC ─► fuse ─► bridge ─► TVS ─► buck 5 V ─► LDO 3.3 V     │
└────────────────────────────────┼─────────────────────────────────────┘
                                 │
          ┌──────────────────────┼─────────────────────────┐
          ▼                      ▼                         ▼
   Admin phone / laptop    Zigbee mesh (optional)    other Entrix units
   (BLE app, or browser    ──► 1 gateway per site    (each powered unit is
   on the unit's own       (ESP32-C6 + PC/RPi or     also a Zigbee router
   Wi-Fi hotspot)          office Wi-Fi)             that relays for others)
```

---

## 3. Component choices

### 3.1 Microcontroller and radios: ESP32-C6

**Why the ESP32-C6:**

* One ~$2.5–3.2 module provides **BLE 5**, **IEEE 802.15.4 (Zigbee 3.0 / Thread)** and **2.4 GHz
  Wi-Fi 6**. That covers every wireless option above without extra radio modules.
* 4–8 MB of on-module flash holds the user database and logs, so no SD card is needed.
* The module is rated for −40…+85 °C.
* **Secure boot and flash encryption** stop anyone from reading a stolen unit to clone users or
  remotes.
* The toolchain is free and mature: ESP-IDF (esp-zigbee-sdk, NimBLE, LittleFS, HTTP server) or
  Arduino-ESP32 3.x for faster prototyping.

**Recommended module:** `ESP32-C6-WROOM-1-N8` (PCB antenna, 8 MB flash).
Use `ESP32-C6-WROOM-1U-N8` (u.FL connector for an external antenna) on units that need more Zigbee
range or are mounted on or near metal.

| Alternative | Radios | ~Price | Verdict |
|---|---|---|---|
| ESP32-C3 | Wi-Fi + BLE | ~$1.8 | About $1 cheaper but has no Zigbee. Choose it only if you will never use Zigbee; the rest of the design stays the same |
| ESP32-H2 | BLE + Zigbee | ~$2.5 | No Wi-Fi, so no browser/hotspot admin page |
| nRF52840 module | BLE + Zigbee/Thread | $5–8 | Excellent radio, but about twice the price |
| TI CC2652 | Zigbee + BLE | $5+ | Same issue |

> The C6 has **one** 2.4 GHz radio, which Wi-Fi, BLE and Zigbee share in turns. Running them at
> the same time works, but when Zigbee is in use the Wi-Fi hotspot should be **on demand** (only
> during an admin session), not always on.

### 3.2 RF remote receiver and remotes

**Receiver: `RXB6` (or `RXB12`) 433.92 MHz superheterodyne OOK module, about $1.**

* Runs on 3.3–5.5 V. Power it from **3.3 V** so its data output can connect straight to the
  ESP32, whose GPIOs are not 5 V tolerant.
* Sensitivity is about −107 dBm. That gives much better range and interference rejection than the
  cheap super-regenerative receivers (e.g. the RX board from the XY-MK-5V / FS1000A kits), which
  should be avoided.
* Use the 315 MHz version if your remotes are 315 MHz (common in North America).
* The ESP32 firmware decodes the signal itself (interrupt on the DATA pin, pulse-width decoding).
  No decoder IC is needed, and the firmware reads each remote's **unique ID**, which identifies the
  user.
* **Antenna:** a 17.3 cm straight wire (λ/4 at 433.92 MHz) costs nothing. Where range matters or
  the box is near metal, use an SMA bulkhead and an external 433 MHz whip (~$1.5). Expect about
  30–100 m outdoors.
* Upgrade path: a `CC1101` transceiver module (~$2–3) if you later want RSSI, several frequencies,
  or transmit capability.

**Remotes** (choose per site; the firmware supports both, chosen per user):

| Type | Chip | ~Price | Security | Notes |
|---|---|---|---|---|
| Fixed-code "learning" remote | EV1527 (or PT2262) | $1–1.5 | **Low.** The code can be captured and replayed with a cheap SDR or a "copy remote" | 20-bit unique ID per remote, 4 buttons. Fine for parking barriers and low-risk gates |
| Rolling-code remote | HCS301 (KeeLoq) | $2–3 | **Medium.** 28-bit serial number plus an encrypted counter, so replayed codes are rejected | Needs the manufacturer key. Order remotes programmed with **your own** key (a common OEM service), or program blank HCS301 remotes yourself (the protocol is in the Microchip datasheet). **Recommended for doors** |

The admin can map each button to a function, e.g. button A opens relay 1 and button B opens
relay 2.

### 3.3 Door outputs and inputs

**Outputs**

* **Relay 1 (always fitted):** 5 V coil, 10 A contacts, NO/COM/NC (e.g. `HF46F-5V`,
  `SRD-05VDC-SL-C`). It is driven by an NPN or N-MOSFET with a flyback diode. A **pull-down
  resistor on the driver input** ensures the relay can never click during boot or reset.
* **Relay 2 (optional footprint):** for a second door, roller-shutter up/down, a siren, etc.
* A potential-free (dry) contact works with **any** electric door type (see §6).

**Inputs.** Each input goes through a `PC817` optocoupler (~$0.03 each) to survive long cables and
surges.

* Door position contact (reed switch): enables "door forced open" and "door held open" log events.
* Exit / request-to-exit push button.
* Tamper switch on the box lid.

**Local feedback:** a bi-color LED and a small buzzer for granted/denied, plus one **setup button**
inside the box (factory reset / enable the admin hotspot).

### 3.4 Power supply and protection

Doors usually have 12 V DC (lock power supply), 24 V AC/DC (gate-motor accessory output) or only
230 V AC. A single input stage accepts all of the low-voltage options:

```
VIN 12–24 V AC or DC (either polarity)
 └► PTC resettable fuse 500 mA
    └► bridge rectifier (MB10S)          — accepts AC and reversed DC
       └► TVS SMBJ40A + 470 µF / 63 V    — surge clamp and hold-up
          └► buck converter rated 80 V in (XL7015-class) → 5 V   (relay)
             └► LDO ≥600 mA (AP2112K-3.3) → 3.3 V               (ESP32-C6, RTC, RXB6)
```

* 24 V AC rectifies to about 34–37 V peak. A 40 V regulator (e.g. LM2596) would have no margin, so
  use an **80 V** buck. The SMBJ40A clamps at about 65 V, which the regulator can survive.
* **230 V-only sites:** add a sealed AC/DC module (`HLK-PM12` / `HLK-5M12`, ~$2–3, or Mean Well
  `IRM-05-12`, ~$6) that feeds the same 12 V input.
* **Power budget:** about 0.5 W idle (BLE/Zigbee listening, relay off) and about 1.5 W peak (relay
  on plus hotspot transmitting).
* **Backup battery** is *not* needed to keep the data (see §3.5). If the door itself must work
  during outages, its lock power supply needs a battery anyway; the usual choice is a 12 V
  access-control PSU with a 7 Ah SLA battery. Power Entrix from that same PSU.

### 3.5 Non-volatile storage and power-loss safety

All persistent data lives in the ESP32-C6 module's 8 MB SPI flash. There is **no SD card**, because
SD cards corrupt on sudden power loss and their contacts corrode outdoors.

**Partition plan (8 MB):**

| Partition | Size | Contents |
|---|---|---|
| `nvs` | 24 KB | Settings, admin password hash, BLE/Zigbee keys, rolling-code counters |
| `otadata`, `phy_init` | 12 KB | System |
| `ota_0` / `ota_1` | 2 × 2 MB | Firmware A/B slots for safe over-the-air updates |
| `users` (LittleFS) | 512 KB | User database |
| `logs` (raw ring) | 2 MB | Access log, 32-byte records, about 65,500 events |
| `zb_storage`, `zb_fct` | ~20 KB | Zigbee stack |
| spare | ~1.4 MB | Reserve |

**Power-loss rules:**

1. **NVS and LittleFS are designed to survive a power cut in the middle of a write.** An
   interrupted write leaves the previous version intact.
2. **Changes to the user database are atomic:** the firmware writes `users.tmp`, then renames it
   over the old file. The database is therefore always either the old version or the new one,
   never half of each.
3. **The log is append-only.** Each record carries a sequence number and a CRC32. On boot, the
   firmware scans for the newest valid record; a half-written last record is simply discarded.
4. The **brown-out detector** built into the ESP32 is enabled, so the chip resets cleanly instead of
   writing garbage while the voltage sags.
5. A **VIN-sense** ADC pin (through a resistor divider) and the bulk capacitor let the firmware
   detect falling input power and stop starting new flash writes during the last tens of ms.
6. On every boot a **"power restored"** event is logged with the RTC time, which also gives you a
   record of outages.

**Flash wear check:** 200 events/day × 32 B = 6.4 KB/day, so the 2 MB log ring wraps about every
300 days. Each flash sector is then erased about once a year, against an endurance of about 100,000
cycles. The user database (1,000 users × 64 B = 64 KB) is written rarely and is cached in RAM for
instant lookups.

*Optional:* FRAM (e.g. `MB85RC256V`, 32 KB I²C, ~$2) gives unlimited fast writes. v1 does not need
it; keep an I²C footprint for it.

### 3.6 Real-time clock

The ESP32 has no battery-backed clock, so it loses the time whenever power is lost. An external RTC
is needed for meaningful log timestamps and for "disabled until <date>" and schedules.

* **Default: `PCF8563`** (or the pin-compatible `BM8563`), about $0.2, plus a 32.768 kHz crystal and
  a coin cell. The time is synced automatically whenever an admin connects (from the phone or
  browser clock) or from the Zigbee gateway, and the firmware can learn the drift and correct for
  it.
* **If standalone doors are visited rarely** and you need minute accuracy over a year, use a
  `DS3231` instead (TCXO, ±2 ppm, about 1 min/year). It costs about $1.5–4 more.
* **Battery:** use a **BR2032** (Li/CF, rated −30…+85 °C) instead of a CR2032 (−20…+70 °C), because
  a box in the sun gets hot. It should last 5–10 years.

### 3.7 Communication and admin interface

The hardware is the same for every option below; only the firmware differs.

| Option | Extra hardware | Typical outdoor range | Pros | Cons |
|---|---|---|---|---|
| **A. Unit's own Wi-Fi hotspot + web page** | none | 30–50 m | Works in any phone or laptop browser (Android **and** iPhone); no app to build or install. Needs **no** Wi-Fi infrastructure, because the unit *is* the access point | The admin walks to each door. The hotspot is on demand only |
| **B. Bluetooth LE + phone app** | none | 10–40 m | Secure pairing, low power, can stay always on | You must build an app; Web Bluetooth does not work on iPhone |
| **C. Zigbee mesh + gateway** | 1 gateway per site (~$8–15) | ~50–200 m per hop. Every powered unit is a router that relays for the others | Central administration: add, remove or disable a user once and it is pushed to every door. Live logs | Each door must be within hop range of another door or the gateway. Most firmware work |
| D. ESP-NOW (Espressif peer-to-peer) | none | 200 m+; up to ~1 km line of sight in long-range mode | Free, simpler than Zigbee | Espressif-only, not a standard |
| E. LoRa (optional module) | UART LoRa module, $5–8 per door | 1–5 km | Very long range | Low data rate. Use **868/915 MHz** modules, never 433 MHz, which would interfere with the remote receiver |
| F. RS485 (optional transceiver) | `MAX3485`/`SP3485`, ~$0.3, plus cable | 1,200 m | Most reliable | Needs a cable |

**Recommendation:**

* **Firmware v1: A + B.** Neither needs extra hardware.
  * The admin opens the hotspot by **holding a button on a designated admin remote for 5 s**, or by
    pressing the setup button inside the box. The hotspot closes after 10 min idle.
  * The hotspot uses WPA2 with a unique password per device, and the web page has its own admin
    login. BLE uses LE Secure Connections pairing with a passkey.
  * The user list can be **exported and imported as a file**. Enroll a remote at one door, then
    upload the file at the other doors.
* **Firmware v2: C (Zigbee)** for central management, if the doors are within mesh range of each
  other. The gateway is an ESP32-C6 (the same board, or a DevKit with an external antenna) at the
  office. It connects to a PC or Raspberry Pi over USB, or to the office Wi-Fi.
  * The standard **Zigbee Door Lock cluster** already defines users, enabled/disabled status,
    schedules and an event log. Implementing it would also let Home Assistant / Zigbee2MQTT manage
    Entrix.
* **E and F are optional footprints** on the PCB that cost almost nothing. Populate them only at
  doors that are out of reach.

**Admin functions** (the same in every option):

* **Add a user:** click "Add" and press the user's remote. The firmware captures the remote ID
  automatically; the admin then types a name and chooses which buttons/doors the user may open.
* **Remove a user.**
* **Temporarily disable a user:** an on/off toggle, or "disabled until <date/time>", which
  re-enables the user automatically using the RTC. Optional validity window (valid from/to) and
  weekly schedule.
* **View, filter and export the logs** (CSV).
* **Settings:** door pulse time, relay mode (pulse/toggle), time sync, admin password change,
  firmware update (OTA).

### 3.8 Outdoor enclosure and environment

* **Enclosure:** IP65–IP67 **polycarbonate** (or UV-stabilised ABS/ASA), light grey or white, about
  115 × 90 × 55 mm, ~$2–4. Plain ABS turns brittle in sunlight.
* **Cable glands:** IP68 nylon, PG7/PG9 or M12/M16. Cables enter **from the bottom only**, with a
  drip loop.
* **Pressure-equalisation vent:** an ePTFE membrane, M12, ~$0.5. It stops the box from "breathing"
  moisture in as it heats and cools, which is the most common way outdoor electronics fail.
* **Conformal coating** (acrylic spray) on the PCB.
* **All parts rated −40…+85 °C**, including the BR2032 coin cell.
* **A plastic box** so that the 433 MHz and 2.4 GHz antennas work from inside it. If the unit is
  mounted on a metal gate or post, use external antennas (SMA or u.FL pigtail).
* Mount the box out of direct sun, or add a small sun hood.
* **Surge/ESD protection:**
  * TVS diode on the power input and a PTC fuse.
  * Optocoupled inputs.
  * Flyback diode across DC lock coils.
  * Varistor or RC snubber across the relay contacts for AC or inductive loads.

### 3.9 Physical security (important)

* The box contains the relay. If it is mounted on the public side, anyone can open it and short
  COM–NO to open the door. **Mount the unit on the secure side** (inside the property, inside the
  gate-motor housing, or above the door frame indoors) and **bring only the 433 MHz antenna
  outside**.
* A **tamper switch** on the lid is logged and can trigger an optional buzzer alarm.
* In production, enable **ESP32 secure boot and flash encryption** so that a stolen unit cannot be
  read out (to clone users/remotes) or reflashed.
* Whether a door stays locked or opens during a power cut (fail-secure or fail-safe) depends on the
  lock you choose (electric strike or maglock). Check the local fire code for exit doors.

---

## 4. Suggested ESP32-C6 pin map

| GPIO | Function | Notes |
|---|---|---|
| 0 | `VIN_SENSE` (ADC1_CH0) | Divider from rectified VIN, for power-fail detection |
| 1 | `RF_DATA` | 433 MHz receiver output (3.3 V level) |
| 2 | `RELAY1` | Via transistor, 10 kΩ pull-down |
| 3 | `RELAY2` (optional) | Via transistor, 10 kΩ pull-down |
| 4 | `RS485_DE/RE` or `LORA_M0` (optional) | 10 kΩ pull-down |
| 5 | `LORA_M1` (optional) | |
| 6 | `I2C_SDA` | RTC (+ optional FRAM) |
| 7 | `I2C_SCL` | RTC (+ optional FRAM) |
| 9 | `SETUP` button | Also the BOOT strap pin; button to GND |
| 10 | `IN_DOOR` | Door contact, via optocoupler |
| 11 | `IN_EXIT` | Exit button, via optocoupler |
| 18 | `IN_TAMPER` | Lid switch |
| 19 | `LED_GREEN` | |
| 20 | `LED_RED` | |
| 21 | `BUZZER` | Via transistor |
| 22 | `UART1_TX` (optional) | RS485 DI **or** LoRa module RXD (populate one) |
| 23 | `UART1_RX` (optional) | RS485 RO **or** LoRa module TXD |
| 12 / 13 | USB D− / D+ | Programming and debugging (built-in USB-Serial-JTAG) |
| 16 / 17 | UART0 TX / RX | Debug console |
| 8, 15 | Strapping pins | Leave as the datasheet recommends |

> Before laying out a PCB, check this against the "Strapping Pins" section of the ESP32-C6
> datasheet and the pin-out of the exact module you buy. GPIO4/5/8/9/15 are strapping pins; the uses
> above keep them in their default states during boot.

---

## 5. Bill of materials and cost

### 5.1 Prototype from off-the-shelf modules (qty 1–10)

| Item | Example | ~USD |
|---|---|---|
| MCU board | ESP32-C6 DevKitC-1 (or a clone / "ESP32-C6 SuperMini") | 3–9 |
| 433 MHz receiver | RXB6 (superheterodyne) | 1–1.5 |
| Relay | 1-channel 5 V relay module, optocoupled. **Use high-level-trigger mode**: 3.3 V GPIOs cannot fully switch off low-level-trigger modules powered at 5 V | 0.8–1.2 |
| Power | XL7015 buck module (5–80 V in) set to 5 V | 1–1.5 |
| RTC | DS3231 or PCF8563 module with battery | 1–1.5 |
| Protection and wiring | Bridge rectifier, TVS, PTC fuse, terminal blocks, perfboard | 1–2 |
| I/O | LED, buzzer, reed switch, tamper micro-switch | 0.5–1 |
| Enclosure | IP65 box, 2 cable glands, vent | 3–6 |
| **Total** | | **≈ 13–23** |

### 5.2 Production on a custom PCB (2-layer, JLCPCB/LCSC assembly, qty 100)

| Block | Parts | ~USD |
|---|---|---|
| MCU | ESP32-C6-WROOM-1-N8 | 2.8–3.2 |
| RF receiver | RXB6 module soldered to the board (a later chip-down SYN480R design saves ~$0.5) | 0.8–1.0 |
| Relay + driver | HF46F-5V / SRD-05 + MOSFET/NPN + diode + resistors | 0.35 |
| Power | PTC, MB10S, SMBJ40A, 470 µF/63 V, XL7015 + inductor + Schottky, AP2112K-3.3 | 0.9 |
| RTC | PCF8563/BM8563 + crystal + BR2032 + holder | 0.8 |
| I/O | 3× PC817, LED, buzzer, setup and tamper switches | 0.4 |
| Connectors | Pluggable terminal blocks (~10 positions), u.FL/SMA | 0.6 |
| PCB | 2-layer, ~80 × 60 mm | 0.3 |
| Assembly | SMT plus hand-soldered through-hole parts, set-up cost spread over the batch | 1–1.5 |
| Enclosure | IP65 box, glands, vent, coating | 3–4 |
| **Total** | | **≈ 11–13** |

### 5.3 Per-site extras

| Item | ~USD |
|---|---|
| Remote, EV1527 fixed code | 1–1.5 each |
| Remote, HCS301 rolling code | 2–3 each |
| Zigbee gateway (firmware v2) | 8–15 per site |
| External 433 MHz whip antenna + SMA bulkhead | ~1.5 |
| External 2.4 GHz 3–5 dBi antenna + u.FL pigtail | ~2 |
| AC/DC module for 230 V-only sites | 2–6 |

---

## 6. Connecting to different door types

| Door / lock type | Behaviour without power | Wiring to the Entrix relay |
|---|---|---|
| Electric strike / solenoid bolt, 12 V DC | Fail-secure (stays locked) | PSU+ → COM; NO → lock+; lock− → PSU−. Diode across the lock coil |
| Magnetic lock (maglock), 12/24 V DC | Fail-safe (opens) | PSU+ → COM; NC → maglock+. The relay pulses to cut power and release the lock |
| Gate / garage / barrier motor controller | Depends on the motor | COM + NO across the motor's "push-button / START / OPEN" input (dry contact, 0.5–1 s pulse) |
| Automatic sliding door operator | — | COM + NO across the "external open / key switch" input |
| Roller shutter (up/down) | — | Uses relay 2 (button A = up, button B = down), or the shutter's own step input |

---

## 7. Firmware data formats that affect the hardware

These records set the flash sizing in §3.5.

```c
// User record: 64 bytes, stored in /users.bin (LittleFS), cached in RAM.
typedef struct {
    uint16_t user_id;
    uint8_t  remote_type;     // 0 = EV1527 fixed code, 1 = HCS301 rolling code
    uint8_t  flags;           // bit0 = enabled, bit1 = admin remote
    uint32_t remote_serial;   // 20-bit (EV1527) or 28-bit (HCS301) ID
    uint8_t  button_mask;     // buttons this user may use
    uint8_t  relay_map;       // which relay each button drives
    uint16_t schedule_id;     // 0 = 24/7
    uint32_t valid_from;      // Unix time, 0 = no limit
    uint32_t valid_until;     // Unix time, 0 = no limit
    uint32_t disabled_until;  // temporary disable, 0 = not disabled
    char     name[24];
    uint8_t  reserved[12];
    uint32_t crc32;
} user_t;

// Log record: 32 bytes, append-only ring in the "logs" partition.
typedef struct {
    uint32_t seq;             // increases forever; locates the newest record after reboot
    uint32_t timestamp;       // Unix time from the RTC
    uint8_t  event;           // GRANTED, DENIED_UNKNOWN, DENIED_DISABLED, DENIED_SCHEDULE,
                              // DENIED_REPLAY, DOOR_FORCED, DOOR_HELD, EXIT_BUTTON, TAMPER,
                              // POWER_ON, ADMIN_CHANGE, TIME_SET, ...
    uint8_t  button;
    uint16_t user_id;         // 0xFFFF = unknown remote
    uint32_t remote_serial;
    uint8_t  detail[12];      // admin action, rolling counter, etc.
    uint32_t crc32;
} log_record_t;
```

---

## 8. Open questions and assumptions

| Question | Assumption used in this draft |
|---|---|
| Distance between doors, and from the doors to an office/admin point? | Unknown. This decides between walk-up admin (A/B), a Zigbee mesh (C) and LoRa (E) |
| Power available at each door? | 12 V DC or 24 V AC/DC; 230 V-only sites need an AC/DC module |
| Region? | 433.92 MHz remotes (315 MHz in North America); 868 or 915 MHz if LoRa is used |
| Users and traffic per door? | ≤ 1,000 users and ≤ 200 events/day per door |
| Security level? | Rolling-code remotes for doors; fixed-code acceptable for low-risk barriers |
| Must doors open during a power cut? | No. Only the data must survive; a battery-backed lock PSU is needed otherwise |

## 9. Next steps

1. **Breadboard prototype (§5.1):** ESP32-C6 DevKit, RXB6, relay module and RTC module. Firmware:
   decode the remote → look up the user → pulse the relay → write a log record.
2. **Hotspot web UI:** user add/remove/temporary disable, log viewer and export, time sync.
3. **Field test** at a real door: remote range, BLE/hotspot range, Zigbee range between two units.
4. **Custom PCB rev A** with optional relay 2, RS485/LoRa and FRAM footprints.
5. **Zigbee gateway** and central admin UI (firmware v2).
