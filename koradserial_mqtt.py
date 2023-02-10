#!/usr/bin/env python3
import os
import sys
import argparse
import logging
import serial
import json
from enum import Enum
from getpass import getpass
from koradserial.koradserial import KoradSerial
import paho.mqtt.client as mqtt
from typing import Dict, Callable


power_supply = None

# without trailing /
err_topic = None
stat_topic = None
cmnd_topic = None

ENVIRON_USERNAME = "KORADSERIAL_MQTT_USERNAME"
ENVIRON_PASSWORD = "KORADSERIAL_MQTT_PASSWORD"


def cmnd_output(msg: str) -> None:
    OUTPUT_CMDS = {
        'on': power_supply.output.on,
        'off': power_supply.output.off,
        '?': lambda: None,  # empty lambda - only stat_output()
        '': lambda: None,
    }

    if msg in OUTPUT_CMDS:
        OUTPUT_CMDS[msg]()
        stat_output()
    else:
        cmnd_err('output', msg)


def cmnd_status(msg: str) -> None:
    stat_json()


def cmnd_voltage(msg: str) -> None:
    try:
        voltage = float(msg)
    except ValueError as e:
        cmnd_err('voltage', str(e))
        return
    power_supply.channels[0].voltage = voltage


def cmnd_current(msg: str) -> None:
    try:
        current = float(msg)
    except ValueError as e:
        cmnd_err('current', str(e))
        return
    power_supply.channels[0].current = current


COMMANDS: Dict[str, Callable[[str], None]] = {
    # MQTT topic after cmnd: function
    'output': cmnd_output,
    'status': cmnd_status,
    'voltage': cmnd_voltage,
    'current': cmnd_current,
}


def stat_output():
    out = power_supply.status.output
    log.debug(f"Output state: {out}")
    client.publish(f"{stat_topic}/output", out.name)


class StatusEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.name

        return json.JSONEncoder.default(self, obj)


def stat_json():
    status = power_supply.status
    status_json = StatusEncoder().encode(vars(status))
    log.debug('Sending JSON status')
    client.publish(f"{stat_topic}/json", status_json)


def cmnd_err(command: str, msg: str) -> None:
    error_message = f"Unknown command for {cmnd_topic}/{command}: {msg}"
    log.error(error_message)
    client.publish(err_topic, error_message)


def on_connect(client, userdata, flags, rc):
    log.info(f"MQTT connected with result code {str(rc)}")
    if rc == 5:
        sys.exit("Incorrect MQTT login credentials")

    client.publish(f'{stat_topic}/availability', 'online',
                   retain=True)

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    log.debug(f"Subscribing to {cmnd_topic}/+")
    client.subscribe(f"{cmnd_topic}/+")


# Python3.9 has removeprefix, but this program needs to work without it
def remove_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix):]
    return text


def on_message(client, userdata, msg):
    log.debug(f"{msg.topic}: {msg.payload}")
    command = remove_prefix(msg.topic, f"{cmnd_topic}/")
    if command in COMMANDS:
        COMMANDS[command](msg.payload.decode('ascii'))


def main():
    # add_help=False avoids conflict with -h for hostname
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("-H", "--help", action="help",
                        help="show this help message and exit")

    parser.add_argument("-h", "--hostname", default="localhost",
                        help="MQTT broker host (default: %(default)s)")

    parser.add_argument("-p", "--port", type=int, default=1883,
                        help="MQTT broker port (default: %(default)d)")

    parser.add_argument("-t", "--topic", default="lab/KORAD",
                        help="MQTT topic prefix (default: %(default)s)")

    parser.add_argument(
        "-u", "--username", default=None,
        help=f"MQTT username (default: {ENVIRON_USERNAME} environment "
             "variable if it exists, otherwise anonymous login)"
    )

    parser.add_argument(
        "-P", "--password", default=None,
        help=f"MQTT password (default: {ENVIRON_PASSWORD} environment "
             "variable if it exists, otherwise prompt for password)"
    )

    parser.add_argument("-v", "--verbose", action="store_true",
                        help="log debug level messages")

    parser.add_argument("--logfile", default=None,
                        help="file to output the log to (default: stderr)")

    parser.add_argument("device",
                        help="serial port the power supply is attached to")

    global args
    args = parser.parse_args()

    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG

    format_string = '%(asctime)s %(levelname)s %(message)s'
    formatter = logging.Formatter(format_string)
    global log
    log = logging.getLogger()
    log.setLevel(logging.DEBUG)
    if args.logfile is not None:
        # At least some info in stderr
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        log.addHandler(handler)

        handler = logging.FileHandler(args.logfile)
        handler.setLevel(level)
        handler.setFormatter(formatter)
        log.addHandler(handler)

    else:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        handler.setFormatter(formatter)
        log.addHandler(handler)

    global err_topic
    err_topic = f"{args.topic}/err"
    log.debug(f"err topic: {err_topic}")
    global stat_topic
    stat_topic = f"{args.topic}/stat"
    log.debug(f"stat topic: {stat_topic}")
    global cmnd_topic
    cmnd_topic = f"{args.topic}/cmnd"
    log.debug(f"cmnd topic: {cmnd_topic}")

    log.info('Connecting to the power supply')
    global power_supply
    try:
        power_supply = KoradSerial(args.device)
    except serial.serialutil.SerialException:
        sys.exit(f"Bad serial port: {args.device}")

    log.info(f"Power supply model: {power_supply.model}")
    log.info(f"Power supply status: {power_supply.status}")

    try:
        global client
        client = mqtt.Client()
        client.on_connect = on_connect
        client.on_message = on_message
        log.info(f"Connecting to MQTT on {args.hostname}:{args.port}")
        username = args.username
        if username is None:
            username = os.environ.get(ENVIRON_USERNAME)
        if username is not None:
            password = args.password
            if password is None:
                password = os.environ.get(ENVIRON_PASSWORD)
            if password is None:
                password = getpass()

            client.username_pw_set(username, password)

        client.will_set(f'{stat_topic}/availability', 'offline',
                        retain=True)
        client.connect(args.hostname, args.port)
        client.loop_forever()

    except KeyboardInterrupt:
        log.info('^C received. Stopping')
        client.publish(f'{stat_topic}/availability',
                       'offline', retain=True)
        client.disconnect()
        power_supply.close()


if __name__ == '__main__':
    main()
