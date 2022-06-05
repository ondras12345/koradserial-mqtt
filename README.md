# koradserial-mqtt
MQTT control for KORAD KA3005P power supply

A simple MQTT interface for the KORAD KA3005P power supply written in Python.

**WARNING**: This project is still in development.
Currently, it is only possible to turn the output on and off.


## Installation
- install pyserial
  ```
  pip3 install pyserial
  ```
- install paho-mqtt
  ```
  pip3 install paho-mqtt
  ```
- clone https://github.com/starforgelabs/py-korad-serial
  ```
  git clone https://github.com/starforgelabs/py-korad-serial.git koradserial
  touch ./koradserial/__init__.py
  ```


## Usage
### Command line arguments
```shell
$ ./koradserial_mqtt.py -H
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

### Turn on the output
```
mosquitto_pub -h broker_ip -t lab/KORAD/cmnd/output -u user -P 'password' -m "on"
```

### Get status
We will need to start 2 proceses (2 terminal windows), one with
`mosquitto_sub` and one with `mosquitto_pub`. For each step, two command are
given: one to get just the output status and one to get the full status of the
power supply.

#### Listen for the response
Output status:
```shell
$ mosquitto_sub -h broker_ip -t lab/KORAD/stat/output -u user -P 'password'
```
Full status:
```shell
$ mosquitto_sub -h broker_ip -t lab/KORAD/stat/json -u user -P 'password'
```

#### Request the status
Output status:
```shell
$ mosquitto_pub -h broker_ip -t lab/KORAD/cmnd/output -u user -P 'password' -m "?"
```
Full status:
```shell
$ mosquitto_pub -h broker_ip -t lab/KORAD/cmnd/status -u user -P 'password' -m "?"
```

#### Result
Output status:
```shell
$ mosquitto_sub -h broker_ip -t lab/KORAD/stat/output -u user -P 'password'
on
```

Full status:
```shell
$ mosquitto_sub -h broker_ip -t lab/KORAD/stat/json -u user -P 'password'
{"raw": 65, "channel1": "constant_voltage", "channel2": "constant_current", "tracking": "independent", "beep": "off", "lock": "off", "output": "on"}
```
