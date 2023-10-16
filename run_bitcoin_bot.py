import logging
import asyncio
from datetime import datetime
import signal
import sys
from pathlib import Path
from monstr.exception import ConfigurationError
from monstr.client.client import Client, ClientPool
from monstr.util import util_funcs
from monstr.encrypt import Keys
from bots.bitcoind import BitcoindBot, BitcoindRPC
from util import load_toml


# working directory
WORK_DIR = f'{Path.home()}/.nostrpy/'
# config file
CONFIG_FILE = f'bitcoin_bot.toml'
# default relay
DEFAULT_RELAY = 'ws://localhost:8081'
# default key - if None it'll be generated each run
USE_KEY = 'nsec1fnyygyh57chwf7zhw3mwmrltc2hatfwn0hldtl4z5axv4netkjlsy0u220'

# for connecting to bitcoind
BITCOIND_NETWORK = 'test'            #   not yet used have to manually change port
BITCOIND_USER = 'monty'              #
BITCOIND_PASSWORD = 'Fl09q6kMFioOKyICCtXY5CJ082aawgS4SrIGFC7yxGE'

# default bitcoind config
BITCOIND_WALLET = 'test'
BITCOIND_HOST = 'http://localhost'
BITCOIND_PORT = 8332
# BITCOIND_PORT = 18332


def get_args() -> dict:
    ret = {
        'work-dir': WORK_DIR,
        'conf': CONFIG_FILE,
        'keys': USE_KEY,
        'relays': DEFAULT_RELAY,
        'bitcoind-host': BITCOIND_HOST,
        'bitcoind-wallet': BITCOIND_WALLET,
        'bitcoind-port': BITCOIND_PORT,
        'bitcoind-user': BITCOIND_USER,
        'bitcoind-password': BITCOIND_PASSWORD
    }

    # update from toml file
    ret.update(load_toml(ret['conf'], ret['work-dir']))

    # TODO - parse args cli
    # ret.update(get_cmdline_args(ret))

    use_keys = Keys.get_key(ret['keys'])
    if use_keys is None or use_keys.private_key_hex() is None:
        raise ConfigurationError(f'{ret["keys"]} bad key value or public key only')

    ret['keys'] = use_keys

    return ret


async def run_bot(args):
    # just the keys, change to profile?
    keys: Keys = args['keys']

    # relays we'll watch
    relays = args['relays']

    # bitcoin connection stuff - note this will probably become bitcoin_ after we add argparse
    bitcoin_host = args['bitcoind-host']
    bitcoin_port = args['bitcoind-port']
    # this should probably just be default wallet to use (or always expected passed in on call?)
    bitcoin_wallet = args['bitcoind-wallet']
    bitcoin_url = f'{bitcoin_host}:{bitcoin_port}/wallet/{bitcoin_wallet}'
    bitcoin_user = args['bitcoind-user']
    bitcoin_password = args['bitcoind-password']

    # actually create the client pool
    def on_connect(the_client: Client):
        print('try connect', bot.kind)
        the_client.subscribe(sub_id='bot_watch',
                             handlers=[bot],
                             filters={
                                 'kinds': [bot.kind],
                                 '#p': [keys.public_key_hex()],
                                 'since': util_funcs.date_as_ticks(datetime.now())
                             })

    clients = ClientPool(clients=relays.split(','),
                         on_connect=on_connect)

    # actually create the bot
    bot = BitcoindBot(keys=keys,
                      clients=clients,
                      bitcoin_rpc=BitcoindRPC(
                          url=bitcoin_url,
                          user=bitcoin_user,
                          password=bitcoin_password
                      ))

    # start the clients
    print(f'monitoring for events from or to account {keys.public_key_hex()} on relays {relays}')
    def sigint_handler(signal, frame):
        clients.end()
        sys.exit(0)

    signal.signal(signal.SIGINT, sigint_handler)
    await clients.run()


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    try:
        asyncio.run(run_bot(get_args()))
    except ConfigurationError as ce:
        print(ce)
