#!/usr/bin/env python3
import sys
import argparse
import logging
import serial
import json
from enum import Enum
from getpass import getpass
from koradserial.koradserial import KoradSerial
import paho.mqtt.client as mqtt


power_supply = None

# without trailing /
err_topic = 'unset'
stat_topic = 'unset'
cmnd_topic = 'unset'


def cmnd_output(msg):
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


def cmnd_status(msg):
    stat_json()


COMMANDS = {
    # MQTT topic after cmnd: function
    'output': cmnd_output,
    'status': cmnd_status,
}


def stat_output():
    out = power_supply.status.output
    log.debug('Output state: {}'.format(out))
    client.publish('{}/output'.format(stat_topic), out.name)


class StatusEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.name

        return json.JSONEncoder.default(self, obj)


def stat_json():
    status = power_supply.status
    status_json = StatusEncoder().encode(vars(status))
    log.debug('Sending JSON status')
    client.publish('{}/json'.format(stat_topic), status_json)


def cmnd_err(command, msg):
    log.error('Unknown command for {}/{}: {}'.format(cmnd_topic,
                                                     command, msg))
    client.publish(err_topic,
                   'Unknown command for {}/{}: {}'.format(cmnd_topic, command,
                                                          msg))


def on_connect(client, userdata, flags, rc):
    log.info('MQTT connected with result code {}'.format(str(rc)))
    if rc == 5:
        log.critical('Incorrect MQTT login credentials')
        sys.exit(2)

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    log.debug('Subscribing to {}/+'.format(cmnd_topic))
    client.subscribe('{}/+'.format(cmnd_topic))


# Python3.9 has removeprefix, but this program needs to work without it
def remove_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix):]
    return text


def on_message(client, userdata, msg):
    log.debug('{}: {}'.format(msg.topic, str(msg.payload)))
    command = remove_prefix(msg.topic, '{}/'.format(cmnd_topic))
    if command in COMMANDS:
        COMMANDS[command](msg.payload.decode('ascii'))


def main():
    # add_help=False avoids conflict with -h for hostname
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument('--help', '-H', action='help',
                        help='show this help message and exit')

    parser.add_argument('--hostname', '-h', default='localhost',
                        help='MQTT broker host (default: localhost)')

    parser.add_argument('--port', '-p', type=int, default=1883,
                        help='MQTT broker port (default: 1883)')

    parser.add_argument('--topic', '-t', default='lab/KORAD',
                        help='MQTT topic prefix (default: lab/KORAD)')

    parser.add_argument('--username', '-u', default=None,
                        help='MQTT username (default: anonymous login)')

    parser.add_argument('--password', '-P', default=None,
                        help='MQTT password (default: prompt for password)')

    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Log debug level messages')

    parser.add_argument('--logfile', default=None,
                        help='File to output the log to. (default: stderr)')

    parser.add_argument('COM',
                        help='Serial port the power supply is attached to')

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
    err_topic = '{}/err'.format(args.topic)
    log.debug('err topic: {}'.format(err_topic))
    global stat_topic
    stat_topic = '{}/stat'.format(args.topic)
    log.debug('stat topic: {}'.format(stat_topic))
    global cmnd_topic
    cmnd_topic = '{}/cmnd'.format(args.topic)
    log.debug('cmnd topic: {}'.format(cmnd_topic))

    log.info('Connecting to the power supply')
    global power_supply
    try:
        power_supply = KoradSerial(args.COM)
    except serial.serialutil.SerialException:
        log.critical('Bad serial port: {}'.format(args.COM))
        sys.exit(1)

    log.info('Power supply model: {}'.format(power_supply.model))
    log.info('Power supply status: {}'.format(power_supply.status))

    try:
        global client
        client = mqtt.Client()
        client.on_connect = on_connect
        client.on_message = on_message
        log.info('Connecting to MQTT on {}:{}'.format(args.hostname,
                                                      args.port))
        if args.username is not None:
            password = args.password
            if password is None:
                password = getpass()

            client.username_pw_set(args.username, password)

        client.connect(args.hostname, args.port, 60)
        client.loop_forever()

    except KeyboardInterrupt:
        log.info('^C received. Stopping')
        client.disconnect()
        power_supply.close()


if __name__ == '__main__':
    main()
