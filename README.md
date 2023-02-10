# koradserial-mqtt
MQTT control for KORAD KA3005P power supply

A simple MQTT interface for the KORAD KA3005P power supply written in Python.

**WARNING**: This project is still in development.
Currently, it is only possible to control channel 1.


## Installation
Clone this repository, `cd` into it and run
```sh
pip3 install .
```


## Usage
### Command line arguments
```
$ koradserial_mqtt.py -H
usage: koradserial_mqtt.py [-H] [-h HOSTNAME] [-p PORT] [-t TOPIC]
                           [-u USERNAME] [-P PASSWORD] [-v] [--logfile LOGFILE]
                           device

positional arguments:
  device                serial port the power supply is attached to

optional arguments:
  -H, --help            show this help message and exit
  -h HOSTNAME, --hostname HOSTNAME
                        MQTT broker host (default: localhost)
  -p PORT, --port PORT  MQTT broker port (default: 1883)
  -t TOPIC, --topic TOPIC
                        MQTT topic prefix (default: lab/KORAD)
  -u USERNAME, --username USERNAME
                        MQTT username (default: anonymous login)
  -P PASSWORD, --password PASSWORD
                        MQTT password (default: prompt for password)
  -v, --verbose         log debug level messages
  --logfile LOGFILE     file to output the log to (default: stderr)
```

### Turn the output on
```sh
mosquitto_pub -h broker_ip -t lab/KORAD/cmnd/output -u user -P 'password' -m "on"
```

### Set output voltage and current
```sh
mosquitto_pub -h broker_ip -t lab/KORAD/cmnd/voltage -u user -P 'password' -m "3.3"
mosquitto_pub -h broker_ip -t lab/KORAD/cmnd/current -u user -P 'password' -m "1.5"
```

### Get status
We will need to start 2 proceses (2 terminal windows), one with
`mosquitto_sub` and one with `mosquitto_pub`. For each step, two command are
given: one to get just the output status and one to get the full status of the
power supply.

#### Listen for the response
Output status:
```sh
$ mosquitto_sub -h broker_ip -t lab/KORAD/stat/output -u user -P 'password'
```
Full status:
```sh
$ mosquitto_sub -h broker_ip -t lab/KORAD/stat/json -u user -P 'password'
```

#### Request the status
Output status:
```sh
$ mosquitto_pub -h broker_ip -t lab/KORAD/cmnd/output -u user -P 'password' -m "?"
```
Full status:
```sh
$ mosquitto_pub -h broker_ip -t lab/KORAD/cmnd/status -u user -P 'password' -m "?"
```

#### Result
Output status:
```sh
$ mosquitto_sub -h broker_ip -t lab/KORAD/stat/output -u user -P 'password'
on
```

Full status:
```sh
$ mosquitto_sub -h broker_ip -t lab/KORAD/stat/json -u user -P 'password'
{"raw": 65, "channel1": "constant_voltage", "channel2": "constant_current", "tracking": "independent", "beep": "off", "lock": "off", "output": "on"}
```


## Udev rules and systemd service
To make this start automatically when the power supply is connected to a
GNU/Linux server, a `systemd` service can be created.

**WARNING**: This is not all that useful, because the program blocks the local
control panel of the power supply for a while when it starts.

It is necessary that the device file name of your power supply stays the same
between restarts of the server. Udev rules can be used to achieve this.

You'll need to know what the attributes of your power supply are. Use the
following command to find out.
```sh
udevadm info --name=/dev/ttyUSB0 --attribute-walk
```

Fill in the attributes here:
```sh
sudo tee -a /etc/udev/rules.d/51-ttyUSB-symlinks.rules << EOF
# Korad KA3005P
SUBSYSTEM=="tty", ATTRS{idVendor}=="0416", ATTRS{idProduct}=="5011", ATTRS{serial}=="NT2009101400", SYMLINK+="ttyUSB-korad"
EOF

sudo udevadm control --reload-rules
```
When the power power supply is next connected, it should be accessible as
`/dev/ttyUSB-korad` in addition to the regular `/dev/ttyUSBx` file.

A systemd unit file can now be created to make this program start
automatically. This example is assuming that the `mosquitto` MQTT broker is
running on the same computer as this program.

For this example, the program should be installed in `/opt/koradserial-mqtt`:
```sh
cd /opt
sudo mkdir koradserial-mqtt
sudo chown $USERNAME:$USERNAME koradserial-mqtt
python3 -m venv koradserial-mqtt
. /opt/koradserial-mqtt/bin/activate
pip3 install git+https://github.com/ondras12345/koradserial-mqtt.git
```

The program is started as the `homeassistant` user. That user will most likely
not exist on your server, so please put in a valid username.

```sh
sudo tee /etc/systemd/system/koradserial_mqtt.service << EOF
[Unit]
Description=MQTT control for KORAD KA3005P power supply
After=mosquitto.service dev-ttyUSB\\x2dkorad.device

[Service]
User=homeassistant
ExecStart=/opt/koradserial-mqtt/bin/koradserial_mqtt.py /dev/ttyUSB-korad
Restart=no

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable koradserial_mqtt.service
```

Modify the udev rule to start the service when the device is connected:
```sh

sudo sed '/ttyUSB-korad/s/$/, TAG+="systemd", ENV{SYSTEMD_WANTS}+="koradserial_mqtt.service"/' -i /etc/udev/rules.d/51-ttyUSB-symlinks.rules

sudo udevadm control --reload-rules
```



## TODO
- case insensitive commands
- periodically poll the device
