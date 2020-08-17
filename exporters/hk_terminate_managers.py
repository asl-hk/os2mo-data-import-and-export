# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
"""
Holstebro Kommune specific queries into MO.
"""
import json
import logging
import os
import pathlib
import queue
import threading
import time
import string

from datetime import datetime, timedelta

import click
import requests
from anytree import Node, PreOrderIter

import common_queries as cq
import holstebro_helpers as hh
import holstebro_logger
from os2mo_helpers.mora_helpers import MoraHelper

cfg_file = pathlib.Path.cwd() / 'settings' / 'holstebro.settings.json'
if not cfg_file.is_file():
    raise Exception('No setting file')
SETTINGS = json.loads(cfg_file.read_text())

logger = logging.getLogger('LederHierarki')


@click.command()
@click.option('--prod', 'hostname', required=True, flag_value='https://os2mo.holstebro.dk', help='MO Prod server')
@click.option('--test', 'hostname', required=True, flag_value='https://os2mo-test.holstebro.dk', help='MO Test server')
@click.option('--dev', 'hostname', required=True, flag_value='https://os2mo-dev.holstebro.dk', help='MO Dev server')
def terminate_managers(hostname):
    holstebro_logger.start_logging(SETTINGS['logging.holstebro.leaders_logfile'])

    t = time.time()

    mh = MoraHelper(hostname=hostname, export_ansi=False)

    logger.info(f"Reading organisation from: {hostname}")
    org = mh.read_organisation()

    # find Holstebro Kommune root uuid, if no uuid is specified
    roots = mh.read_top_units(org)
    for root in roots:
        if root['name'] == SETTINGS['municipality.name']:
            holstebro_uuid = root['uuid']

    managerHelper = hh.HolstebroHelper(mh)

    nodes = mh.read_ou_tree(holstebro_uuid)

    logger.info('Read nodes: {}s'.format(time.time() - t))

    for node in PreOrderIter(nodes['root']):
        ou = mh.read_ou(node.name)

        # Get non-inherited manager, ALWAYS returns 1 or no manager
        ou_manager = mh.read_ou_manager(ou['uuid'], False)

        if ou_manager != {}:  # no manager, create it
            managerHelper._terminate_manager(ou_manager['relation_uuid'])


if __name__ == '__main__':
    terminate_managers()