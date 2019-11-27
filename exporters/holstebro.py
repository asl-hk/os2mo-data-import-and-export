# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

"""
Holstebro Kommune specific queries into MO. 
"""
from os2mo_helpers.mora_helpers import MoraHelper
import common_queries as cq
import os
import queue
import threading
import time

import click
from anytree import PreOrderIter

# http:://os2mo-test.holstebro.dk
#itdig_uuid = '9f981b4d-66c3-4100-b800-000001480001'


@click.command()
@click.option('--root', default=None, help='uuid of the root to be exported.')
@click.option('--threaded-speedup', default=False, help='Run in multithreaded mode')
@click.option('--hostname', envvar='MORA_BASE', default=None, required=True, help='MO hostname')
@click.option('--api_token', envvar='SAML_TOKEN', default=None, required=True, help='SAML API Token')
def export_from_mo(root, threaded_speedup, hostname, api_token):
    threaded_speedup = threaded_speedup
    t = time.time()

    if api_token is None:
        raise NameError('Ugyldigt argument')

    mh = MoraHelper(hostname=hostname, export_ansi=False)

    org = mh.read_organisation()

    # find Holstebro Kommune root uuid, if no uuid is specified
    if root is None:
        roots = mh.read_top_units(org)
        for root in roots:
            if root['name'] == 'Holstebro Kommune':
                holstebro_uuid = root['uuid']
    else:
        holstebro_uuid = root

    nodes = mh.read_ou_tree(holstebro_uuid)

    print('Read nodes: {}s'.format(time.time() - t))

    if threaded_speedup:
        cq.pre_cache_users(mh)
        print('Build cache: {}'.format(time.time() - t))

    filename_org = 'planorama_org.csv'
    filename_persons = 'planorama_persons.csv'
    export_to_planorama(mh, nodes, filename_org, filename_persons)
    print('planorama_org.csv: {}s'.format(time.time() - t))


def export_to_planorama(mh, nodes, filename_org, filename_persons):
    """ Traverses a tree of OUs, for each OU finds the manager of the OU.
    :param nodes: The nodes of the OU tree
    """
    fieldnames_persons = ['UUID', 'Username', 'Password', 'Name', 'Title',
                          'Address', 'Zip', 'Country', 'CPR', 'Email',
                          'Number', 'Mobile', 'Telephone', 'Responsible', 'Responsible_UUID', 'Company']
    fieldnames_org = ['Root', 'Number', 'Name']

    rows_org = []
    rows_persons = []

    for node in PreOrderIter(nodes['root']):
        ou = mh.read_ou(node.name)
        # Do not add "Afdelings-niveau"
        if ou['org_unit_type']['name'] != 'Afdelings-niveau':
            fra = ou['validity']['from'] if ou['validity']['from'] else ''
            til = ou['validity']['to'] if ou['validity']['to'] else ''
            over_uuid = ou['parent']['uuid'] if ou['parent'] else ''
            row_org = {'Root': over_uuid,
                       'Number': ou['uuid'],
                       'Name': ou['name']}
            rows_org.append(row_org)

            employees = mh.read_organisation_people(node.name, 'engagement', False)
            # Does this node have a new name?
            manager = find_org_manager(mh, node)
            if(manager['uuid'] != ''):
                manager_engagement = mh.read_user_engagement(manager['uuid'])
            else:
                manager_engagement = [{'user_key': ''}]

            for uuid, employee in employees.items():
                row = {}
                address = mh.read_user_address(uuid, username=True, cpr=True)
                #manager = mh.read_engagement_manager(employee['Engagement UUID'])
                # row.update(address)  # E-mail, Telefon, Brugernavn, CPR NR
                # row.update(employee)  # Everything else
                row = {'UUID': uuid,
                       'Username': employee['User Key'],
                       'Password': '',
                       'Name': employee['Navn'],
                       'Title': employee['Stillingsbetegnelse'][0] if len(employee['Stillingsbetegnelse']) > 0 else '',
                       'Address': address['Lokation'] if 'Lokation' in address else '',
                       'Zip': '',
                       'Country': '',
                       'CPR': '',  # we do not send CPR to planorama
                       # 'CPR': address['CPR-Nummer'],
                       'Email': address['E-mail'] if 'E-mail' in address else '',
                       'Number': '',
                       'Mobile': address['Mobiltelefon'] if 'Mobiltelefon' in address else '',
                       'Telephone': address['Telefon'] if 'Telefon' in address else '',
                       'Responsible': manager_engagement[0]['user_key'] if len(manager_engagement) > 0 else '',
                       'Responsible_UUID': manager['uuid'] if 'uuid' in manager else '',
                       'Company': employee['Org-enhed UUID']
                       }

                rows_persons.append(row)

    mh._write_csv(fieldnames_persons, rows_persons, filename_persons)
    mh._write_csv(fieldnames_org, rows_org, filename_org)


def find_org_manager(mh, node):

    if(node.is_root):
        print("root node")
        # return {'uuid': ''}

    new_manager = mh.read_ou_manager(node.name, True)

    if new_manager:
        return new_manager
    elif node.depth != 0:
        return find_org_manager(mh, node.parent)
    else:
        return {'uuid': ''}


def export_planorama_org(mh, nodes, filename):
    fieldnames = ['Root', 'Number', 'Name']
    rows = []
    for node in PreOrderIter(nodes['root']):
        ou = mh.read_ou(node.name)
        # Do not add "Afdelings-niveau"
        if ou['org_unit_type']['name'] != 'Afdelings-niveau':
            fra = ou['validity']['from'] if ou['validity']['from'] else ''
            til = ou['validity']['to'] if ou['validity']['to'] else ''
            over_uuid = ou['parent']['uuid'] if ou['parent'] else ''
            row = {'Root': over_uuid,
                   'Number': ou['uuid'],
                   'Name': ou['name']}
            rows.append(row)

    mh._write_csv(fieldnames, rows, filename)


if __name__ == '__main__':
    export_from_mo()
