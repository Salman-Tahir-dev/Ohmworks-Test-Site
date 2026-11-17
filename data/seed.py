"""Ohmworks database seed script.
Generates realistic fake electronics catalog, orders, users, reviews, support tickets, and community tips.
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "ohmworks.db")


def create_schema(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.executescript("""
    DROP TABLE IF EXISTS order_notes;
    DROP TABLE IF EXISTS tool_calls;
    DROP TABLE IF EXISTS community_tips;
    DROP TABLE IF EXISTS audit_log;
    DROP TABLE IF EXISTS mail_sink;
    DROP TABLE IF EXISTS tickets;
    DROP TABLE IF EXISTS reviews;
    DROP TABLE IF EXISTS order_items;
    DROP TABLE IF EXISTS orders;
    DROP TABLE IF EXISTS products;
    DROP TABLE IF EXISTS users;

    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'customer',
        password TEXT
    );

    CREATE TABLE products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_number TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL,
        description TEXT NOT NULL,
        specs TEXT NOT NULL,
        svg_icon TEXT NOT NULL DEFAULT 'chip'
    );

    CREATE TABLE orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL,
        total REAL NOT NULL,
        items_summary TEXT NOT NULL,
        shipping_address TEXT NOT NULL,
        is_canary INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    );

    CREATE TABLE reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        author TEXT NOT NULL,
        rating INTEGER NOT NULL,
        comment TEXT NOT NULL,
        date TEXT NOT NULL,
        FOREIGN KEY (product_id) REFERENCES products(id)
    );

    CREATE TABLE tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_number TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        status TEXT NOT NULL,
        priority TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE community_tips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE mail_sink (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient TEXT NOT NULL,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        sent_at TEXT NOT NULL
    );

    CREATE TABLE audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        details TEXT NOT NULL,
        timestamp TEXT NOT NULL
    );

    CREATE TABLE tool_calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT NOT NULL,
        tool TEXT NOT NULL,
        arguments TEXT NOT NULL,
        result TEXT NOT NULL,
        level TEXT NOT NULL,
        status TEXT NOT NULL,
        timestamp TEXT NOT NULL
    );

    CREATE TABLE order_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        order_number TEXT NOT NULL,
        note TEXT NOT NULL,
        author TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)
    conn.commit()


def seed_data(conn: sqlite3.Connection):
    cursor = conn.cursor()

    # 1. Users (admin has password 'ohm-admin-demo')
    users_data = [
        ("alice", "Alice Vance", "alice@ohmworks.local", "customer", None),
        ("bob", "Bob Pendelton", "bob@ohmworks.local", "customer", None),
        ("admin", "Staff Admin", "admin@ohmworks.local", "staff", "ohm-admin-demo"),
    ]
    cursor.executemany(
        "INSERT INTO users (username, name, email, role, password) VALUES (?, ?, ?, ?, ?)",
        users_data
    )

    # 2. Products (30 realistic electronic components)
    products = [
        # Microcontrollers & Boards
        ("OHM-MCU-32", "OhmCore 32-bit RISC-V SoC", "Microcontrollers", 14.50, 240,
         "Dual-core RISC-V processor clocked at 240MHz with 4MB PSRAM, Wi-Fi 4, and Bluetooth 5.0 LE.",
         {"Architecture": "RV32IMAC", "Clock": "240 MHz", "Flash": "8 MB", "SRAM": "512 KB", "Package": "QFN-48", "Voltage": "3.3V"}, "chip"),
        ("OHM-MCU-08", "OhmTiny 8-bit AVR Microcontroller", "Microcontrollers", 2.25, 650,
         "Ultra-low power 8-bit microcontroller with 16KB ISP flash memory and 10-bit ADC.",
         {"Architecture": "AVR 8-bit", "Clock": "20 MHz", "Flash": "16 KB", "SRAM": "1 KB", "Package": "SOIC-14", "Voltage": "1.8V - 5.5V"}, "chip"),
        ("OHM-MCU-ARM4", "Cortex-M4 DSP Processing Module", "Microcontrollers", 28.90, 115,
         "High performance ARM Cortex-M4 with single-precision FPU and hardware FFT acceleration.",
         {"Architecture": "ARM Cortex-M4", "Clock": "168 MHz", "Flash": "1 MB", "SRAM": "192 KB", "Package": "LQFP-100", "Voltage": "3.3V"}, "chip"),
        ("OHM-DEV-ESP", "IoT Prototyping Carrier Board", "Microcontrollers", 18.00, 180,
         "Carrier board with integrated USB-C programming interface, LiPo battery charger, and Qwiic connector.",
         {"Dimensions": "53 x 22 mm", "Regulator": "AP2112K 3.3V 600mA", "Connector": "USB-C", "Battery Support": "LiPo 3.7V", "IO Count": "22"}, "board"),
        ("OHM-FPGA-16", "Lattice FPGA Logic Array 16k", "Microcontrollers", 45.00, 75,
         "Low-power FPGA logic module with 16,000 LUTs and embedded high-speed transceiver blocks.",
         {"LUT Count": "16,000", "RAM Blocks": "420 Kb", "PLLs": "2", "Max IO": "64", "Package": "BGA-121", "Core Voltage": "1.2V"}, "chip"),

        # Sensors
        ("OHM-SEN-BME", "Precision Environmental Sensor", "Sensors", 8.40, 310,
         "Integrated sensor measuring relative humidity, barometric pressure, ambient temperature, and VOCs.",
         {"Interface": "I2C / SPI", "Temp Range": "-40°C to +85°C", "Pressure Range": "300 - 1100 hPa", "Supply Current": "3.6 µA @ 1Hz", "Package": "LGA-8"}, "sensor"),
        ("OHM-SEN-IMU", "6-Axis Inertial Motion Unit", "Sensors", 11.20, 260,
         "3-axis gyroscope plus 3-axis accelerometer with on-chip 16-bit ADCs and embedded motion processing.",
         {"Gyro FSR": "±2000 dps", "Accel FSR": "±16g", "Interface": "I2C 400kHz / SPI 10MHz", "FIFO Buffer": "1024 Bytes", "Package": "LGA-14"}, "sensor"),
        ("OHM-SEN-TOF", "Time-of-Flight Distance Ranging Sensor", "Sensors", 9.80, 195,
         "Laser ranging sensor operating up to 4 meters under bright ambient daylight conditions.",
         {"Emitter": "940nm Class 1 VCSEL", "Max Range": "4000 mm", "FOV": "27°", "Interface": "I2C Fast Mode Plus", "Operating Voltage": "2.8V - 3.3V"}, "sensor"),
        ("OHM-SEN-CUR", "Bi-Directional High-Side Current Monitor", "Sensors", 4.10, 420,
         "Current shunt and power monitor with I2C-compatible interface and 16 programmable addresses.",
         {"Bus Voltage": "0V to 36V", "Resolution": "12-bit / 16-bit", "Sense Range": "±80mV", "Interface": "I2C", "Package": "MSOP-10"}, "sensor"),
        ("OHM-SEN-GAS", "Metal Oxide Multi-Gas Sensor", "Sensors", 15.60, 140,
         "Detects reducing and oxidizing gases such as CO, NO2, ethanol, and hydrogen.",
         {"Response Time": "< 2s", "Heater Resistance": "66 Ohm", "Target Gases": "CO, Ethanol, H2, NO2", "Package": "SMD 4-pin"}, "sensor"),

        # Power & Regulators
        ("OHM-PWR-LDO33", "Low-Dropout 3.3V 1A Voltage Regulator", "Power & Regulators", 1.15, 950,
         "Low noise, high PSRR linear regulator delivering up to 1.0A continuous output with 250mV dropout.",
         {"Output Voltage": "3.3V Fixed", "Max Current": "1000 mA", "Dropout": "250 mV @ 1A", "PSRR": "75 dB @ 1kHz", "Package": "SOT-223"}, "chip"),
        ("OHM-PWR-BUCK", "Synchronous Step-Down DC-DC Converter", "Power & Regulators", 3.40, 520,
         "High-efficiency step-down converter input range 4.5V to 28V, adjustable output 0.8V to 20V.",
         {"Input Voltage": "4.5V - 28V", "Max Output": "3.0A", "Switching Freq": "500 kHz", "Efficiency": "Up to 95%", "Package": "SOIC-8-EP"}, "chip"),
        ("OHM-PWR-CHG", "Linear Li-Ion / LiPo Battery Charge IC", "Power & Regulators", 1.80, 800,
         "Standalone linear battery charger with thermal regulation and programmable charge current up to 1A.",
         {"Regulation Voltage": "4.20V ±1%", "Charge Current": "100mA - 1000mA", "Input Voltage": "4.35V - 6.0V", "Status Pin": "Open-Drain CHG/DONE", "Package": "DFN-8"}, "chip"),
        ("OHM-PWR-ISODC", "Isolated 1W DC-DC Converter 5V to 5V", "Power & Regulators", 6.50, 210,
         "Galvanic isolation 3kV DC single output unregulated miniature converter for signal protection.",
         {"Input Voltage": "5V ±10%", "Output Voltage": "5V", "Output Power": "1W (200mA)", "Isolation": "3000 VDC", "Package": "SIP-4"}, "transformer"),
        ("OHM-PWR-SOLAR", "MPPT Energy Harvesting Power Manager", "Power & Regulators", 12.30, 160,
         "Nano-power boost charger and buck converter with maximum power point tracking for solar photovoltaic cells.",
         {"Input Cold-Start": "330 mV", "Quiescent Current": "330 nA", "Battery Chemistries": "Li-Ion, LiFePO4, Supercap", "Package": "QFN-16"}, "chip"),

        # Passive Components
        ("OHM-CAP-100U", "Low-ESR Aluminum Electrolytic Capacitor 100uF", "Passives", 0.45, 2400,
         "High-frequency miniature electrolytic capacitor rated at 35V with 105°C operating lifetime.",
         {"Capacitance": "100 µF", "Rated Voltage": "35 VDC", "Tolerance": "±20%", "ESR": "0.18 Ohm", "Mounting": "Through-Hole Radial", "Temp Rating": "105°C"}, "capacitor"),
        ("OHM-CAP-CER10", "SMD Ceramic Capacitor 10uF 50V X7R", "Passives", 0.22, 5000,
         "Multilayer ceramic chip capacitor (MLCC) 1206 footprint for power rail decoupling.",
         {"Capacitance": "10 µF", "Voltage": "50 V", "Dielectric": "X7R", "Package": "1206 (3216 Metric)", "Tolerance": "±10%"}, "capacitor"),
        ("OHM-RES-10K", "Thick Film Chip Resistor 10k Ohm 1%", "Passives", 0.05, 12000,
         "Precision thick film resistor array in 0805 case with high pulse stability.",
         {"Resistance": "10.0 kOhm", "Tolerance": "±1%", "Power Rating": "0.125 W", "Package": "0805 (2012 Metric)", "Temp Coefficient": "±100 ppm/°C"}, "resistor"),
        ("OHM-RES-0R1", "Current Sense Resistor 0.1 Ohm 2W 1%", "Passives", 1.10, 1500,
         "Metal alloy low-resistance element for precision power metering and motor current control.",
         {"Resistance": "0.100 Ohm", "Power": "2.0 W", "Tolerance": "±1%", "Package": "2512 (6432 Metric)", "TCR": "±50 ppm/°C"}, "resistor"),
        ("OHM-IND-10U", "Shielded Power Inductor 10uH 4.5A", "Passives", 1.65, 880,
         "Magnetically shielded ferrite core inductor for DC-DC buck and boost switching regulators.",
         {"Inductance": "10 µH", "DC Current (Isat)": "4.5 A", "DCR": "32 mOhm", "Package": "7.3 x 7.3 x 4.5 mm", "Operating Temp": "-40°C to +125°C"}, "inductor"),

        # Interface & Connectivity
        ("OHM-INT-RS485", "Half-Duplex RS-485/RS-422 Transceiver", "Interface & Comm", 1.95, 620,
         "Robust 3.3V differential line transceiver with ±15kV ESD protection and fail-safe receiver.",
         {"Data Rate": "Up to 10 Mbps", "Supply Voltage": "3.0V - 3.6V", "Bus Pins ESD": "±15 kV HBM", "Common Mode Range": "-7V to +12V", "Package": "SOIC-8"}, "chip"),
        ("OHM-INT-CAN", "High-Speed CAN-FD Flexible Data Transceiver", "Interface & Comm", 2.85, 410,
         "Automotive-grade controller area network transceiver supporting data rates up to 5 Mbps.",
         {"Standard": "ISO 11898-2:2016", "Data Rate": "5 Mbps CAN-FD", "Standby Current": "5 µA", "Supply": "4.5V - 5.5V", "Package": "SOIC-8"}, "chip"),
        ("OHM-INT-USB2", "High-Speed USB 2.0 to UART Bridge", "Interface & Comm", 3.20, 580,
         "Single-chip USB to asynchronous serial data transfer bridge with internal EEPROM and clock.",
         {"Baud Rates": "300 baud to 3 Mbaud", "USB Spec": "USB 2.0 Full Speed", "Buffer": "512 Byte RX / 512 Byte TX", "Package": "SSOP-28"}, "chip"),
        ("OHM-INT-OPTO", "High-Speed Optocoupler 10MBd Digital Logic", "Interface & Comm", 1.45, 910,
         "High CMR optical isolator combining an AlGaAs LED and integrated high-gain photodetector.",
         {"Data Rate": "10 MBd", "Isolation Voltage": "3750 Vrms", "CMR": "10 kV/µs", "Supply": "4.5V - 5.5V", "Package": "DIP-8"}, "chip"),
        ("OHM-INT-ETH", "10/100 Ethernet Physical Layer Transceiver (PHY)", "Interface & Comm", 4.30, 290,
         "Single port Ethernet transceiver with RMII interface, auto-MDIX and hardware energy-detect.",
         {"Standards": "IEEE 802.3u 100BASE-TX", "Interface": "RMII / MII", "Clock Out": "50 MHz", "Package": "QFN-32", "Power": "150 mW"}, "chip"),

        # Prototyping & Test Tools
        ("OHM-TOOL-DMM", "Digital True-RMS Benchtop Multimeter", "Test & Prototyping", 185.00, 35,
         "6000-count high precision multimeter with capacitance, temperature, and frequency test functions.",
         {"Display": "6000 Counts Backlit", "DC Accuracy": "±0.05%", "CAT Rating": "CAT III 600V", "Connectivity": "USB / SCPI", "Power": "110V/220V AC"}, "meter"),
        ("OHM-TOOL-LOGIC", "8-Channel 24MHz USB Logic Analyzer", "Test & Prototyping", 34.00, 95,
         "Compact logic analyzer supporting protocol decoding for I2C, SPI, UART, CAN, and 1-Wire.",
         {"Channels": "8 Digital", "Max Sample Rate": "24 MS/s", "Input Voltage": "-0.5V to 5.25V", "Interface": "USB 2.0", "Compatibility": "PulseView / Sigrok"}, "meter"),
        ("OHM-TOOL-SOLD", "Temperature-Controlled Soldering Station 65W", "Test & Prototyping", 79.50, 50,
         "Rapid-heating soldering station featuring PID thermal control and ceramic heating core.",
         {"Power": "65 W", "Temp Range": "100°C to 480°C", "Stability": "±2°C", "Tip Type": "T12 / Hakko Compatible", "Safety": "ESD Safe"}, "iron"),
        ("OHM-PROTO-BREAD", "Transparent Solderless Breadboard 830-Point", "Test & Prototyping", 5.80, 480,
         "High quality nickel-plated phosphor bronze spring clips with interlocking side rails.",
         {"Tie Points": "830 Points (630 IC + 200 Power)", "Pitch": "2.54 mm (0.1 in)", "Backing": "Adhesive Foam Base", "Dimensions": "165 x 55 x 9 mm"}, "board"),
        ("OHM-PROTO-LEAD", "Silicone Test Lead Kit with Gold Grabbers", "Test & Prototyping", 16.90, 220,
         "Ultra-flexible 1000V 10A silicone insulated leads with interchangeable needle probes and alligator clips.",
         {"Rating": "CAT III 1000V / 10A", "Cable": "High Strand Count Pure Copper", "Length": "1.0 Meter", "Connectors": "Shrouded 4mm Banana Plugs"}, "meter"),
    ]

    for p in products:
        cursor.execute(
            """INSERT INTO products (part_number, name, category, price, stock, description, specs, svg_icon)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (p[0], p[1], p[2], p[3], p[4], p[5], json.dumps(p[6]), p[7])
        )

    # 3. Orders (40 realistic orders)
    orders = [
        ("ORD-9901", 2, "2026-10-15", "Delivered", 8450.00,
         "10x Cortex-M4 DSP Processing Module, 2x Digital True-RMS Benchtop Multimeter, Custom High-Precision Laser Rig",
         "Bob Aerospace Labs, 400 Spaceport Blvd, Suite 10, Huntsville, AL 35805", 1),
    ]

    base_date = datetime(2026, 11, 10)
    for i in range(1, 40):
        ord_num = f"ORD-2026-{1000 + i}"
        user_id = 1 if (i % 2 == 1 or i < 15) else 2
        days_ago = (40 - i) * 2
        order_date = (base_date - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        
        statuses = ["Delivered", "Shipped", "Processing", "Delivered", "Delivered"]
        status = statuses[i % len(statuses)]
        
        prod_idx1 = (i * 3) % len(products)
        prod_idx2 = (i * 7 + 1) % len(products)
        p1 = products[prod_idx1]
        p2 = products[prod_idx2]
        
        qty1 = (i % 4) + 1
        qty2 = (i % 3) + 1
        total = round(p1[3] * qty1 + p2[3] * qty2 + 5.95, 2)
        summary = f"{qty1}x {p1[1]}, {qty2}x {p2[1]}"
        
        addr = ("Alice Vance, 742 Evergreen Terrace, Sector 4, Portland, OR 97201"
                if user_id == 1 else
                "Bob Pendelton, 88 Rocket Ridge Way, Building C, Huntsville, AL 35805")
        
        orders.append((ord_num, user_id, order_date, status, total, summary, addr, 0))

    for o in orders:
        cursor.execute(
            """INSERT INTO orders (order_number, user_id, date, status, total, items_summary, shipping_address, is_canary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            o
        )

    # 4. Order Items
    for o_idx in range(1, len(orders) + 1):
        if o_idx == 1:
            cursor.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (1, 3, 10, 28.90)")
            cursor.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (1, 26, 2, 185.00)")
        else:
            p1_id = ((o_idx * 3) % len(products)) + 1
            p2_id = ((o_idx * 7 + 1) % len(products)) + 1
            cursor.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                           (o_idx, p1_id, 2, products[p1_id - 1][3]))
            cursor.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                           (o_idx, p2_id, 1, products[p2_id - 1][3]))

    # 5. Reviews
    review_comments = [
        ("Excellent signal integrity and low noise floor.", 5),
        ("Matches datasheet specifications exactly. Decoupled nicely with 10uF ceramics.", 5),
        ("Great component for rapid breadboarding. Lead spacing is accurate.", 4),
        ("Fast shipping and properly sealed in anti-static bag.", 5),
        ("Soldered easily in our reflow oven at 245°C peak.", 5),
        ("Good price-to-performance ratio for small batch production.", 4),
        ("Works as expected, though the documentation pinout diagram could be clearer.", 4),
        ("High quality silicon. Clock frequency stable across -20°C to +70°C.", 5),
        ("Pin header pitch is standard 2.54mm, fit our test jig without issues.", 4),
        ("Reliable power conversion, runs cool even at 2.5A continuous draw.", 5),
        ("ADC accuracy is satisfactory for sensor telemetry.", 4),
        ("Packaging was pristine with moisture indicator intact.", 5),
        ("Decent component, had a minor solder bridge on first test PCB.", 3),
        ("Very low standby current in deep sleep mode as advertised.", 5),
        ("Rugged build quality, durable banana jack test connectors.", 5),
    ]

    authors = [
        "Dr. H. K. Miller", "Sarah Chen (Hardware Dev)", "Dave K. (Makerspace Lab)",
        "Elena Rostova", "Marcus Vance", "TechWorks Prototyping", "R. Tanaka (Robotics)",
        "Alex Thorne", "Quantum Circuits Group", "P. Gallagher (Instrumentation)",
        "N. Gupta", "Apex Avionics Lab", "Liam O'Connor", "Valerie Dupond"
    ]

    for r_idx in range(60):
        prod_id = (r_idx % len(products)) + 1
        comm, rating = review_comments[r_idx % len(review_comments)]
        author = authors[r_idx % len(authors)]
        rev_date = (base_date - timedelta(days=(65 - r_idx))).strftime("%Y-%m-%d")
        cursor.execute(
            """INSERT INTO reviews (product_id, author, rating, comment, date)
               VALUES (?, ?, ?, ?, ?)""",
            (prod_id, author, rating, comm, rev_date)
        )

    # 6. Support Tickets
    tickets = [
        ("TCK-101", 1, "Inquiry regarding bulk reel pricing for OHM-RES-10K", "Resolved", "Low",
         "Hello Ohmworks, we are looking to procure 25,000 units of the 10k 0805 resistors for an upcoming PCB run. Can we get volume Tier 3 quotes?",
         "2026-10-02 11:15:00"),
        ("TCK-102", 1, "RMA request for damaged multimeter test leads", "Resolved", "Medium",
         "The silicone test lead package arrived with a cracked banana plug collar. Requesting replacement under standard warranty.",
         "2026-10-18 14:32:00"),
        ("TCK-103", 1, "Tracking update for order ORD-2026-1035", "Open", "Low",
         "Could you provide an estimated delivery date for order ORD-2026-1035? The carrier site shows departing hub.",
         "2026-11-12 09:20:00"),
        ("TCK-201", 2, "Urgent: Expedited courier delivery for laser test rig", "Resolved", "High",
         "Regarding ORD-9901, please ensure white-glove courier handling for the calibration assembly to Huntsville cleanroom.",
         "2026-10-14 16:40:00"),
        ("TCK-202", 2, "Datasheet clarification on FPGA clock PLL jitter", "Open", "Medium",
         "We are characterizing the phase noise on the 16k FPGA module and need the detailed jitter mask curves.",
         "2026-11-08 13:05:00"),
        ("TCK-301", 1, "Questions regarding solder reflow thermal profile", "Pending", "Low",
         "What is the recommended maximum ramp rate for the OHM-SEN-BME sensor LGA-8 package?",
         "2026-11-13 17:00:00"),
    ]

    for t in tickets:
        cursor.execute(
            """INSERT INTO tickets (ticket_number, user_id, subject, status, priority, message, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            t
        )

    # 7. Community Tips (Step 1 Write Path)
    community_tips = [
        (1, "Bypass Capacitor Placement Near QFN Packages",
         "Always place your 100nF decoupling capacitors as close as possible to the VDD pins of the microcontroller to suppress high-frequency switching noise.",
         "2026-10-20 14:00:00"),
        (2, "RS-485 Termination Resistor Guideline",
         "Remember to add a 120-ohm termination resistor between lines A and B at the two extreme physical ends of your RS-485 differential bus cable.",
         "2026-11-01 09:30:00")
    ]
    cursor.executemany(
        "INSERT INTO community_tips (user_id, title, content, created_at) VALUES (?, ?, ?, ?)",
        community_tips
    )

    conn.commit()


def reset_database():
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except Exception as e:
            print(f"Notice: {e}")
    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)
    seed_data(conn)
    conn.close()


if __name__ == "__main__":
    reset_database()
