#!/usr/bin/env python3
#
# Copyright (c) 2017-2018, Magenta ApS
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
import os
import pickle
import hashlib
import requests
import datetime
import xmltodict
from anytree import Node


# ORIGIN FOR TESTS WIH ACTUAL API
GLOBAL_GET_DATE = datetime.datetime(2019, 2, 15, 0, 0)
INSTITUTION_IDENTIFIER = os.environ.get('INSTITUTION_IDENTIFIER')
SD_USER = os.environ.get('SD_USER', None)
SD_PASSWORD = os.environ.get('SD_PASSWORD', None)
if not (INSTITUTION_IDENTIFIER and SD_USER and SD_PASSWORD):
    raise Exception('Credentials missing')


def _dawa_request(address, adgangsadresse=False,
                  skip_letters=False, add_letter=False):
    """ Perform a request to DAWA and return the json object
    :param address: An address object as returned by APOS
    :param adgangsadresse: If true, search for adgangsadresser
    :param skip_letters: If true, remove letters from the house number
    :return: The DAWA json object as a dictionary
    """
    if adgangsadresse:
        base = 'https://dawa.aws.dk/adgangsadresser?'
    else:
        base = 'https://dawa.aws.dk/adresser?strukur=mini'
    params = '&postnr={}&q={}'

    street_name = address['StandardAddressIdentifier']
    last_is_letter = (street_name[-1].isalpha() and
                      (not street_name[-2].isalpha()))
    if (skip_letters and last_is_letter):
        street_name = address['StandardAddressIdentifier'][:-1]
    full_url = base + params.format(address['PostalCode'], street_name)

    path_url = full_url.replace('/', '_')
    try:
        with open(path_url + '.p', 'rb') as f:
            response = pickle.load(f)
    except FileNotFoundError:
        response = requests.get(full_url)
        with open(path_url + '.p', 'wb') as f:
            pickle.dump(response, f, pickle.HIGHEST_PROTOCOL)

    dar_data = response.json()
    return dar_data


class SdImport(object):
    def __init__(self, importer, org_name, municipality_code,
                 forced_uuids={}):
        self.base_url = 'https://service.sd.dk/sdws/'

        self.double_employment = []
        self.address_errors = {}

        self.importer = importer
        self.importer.add_organisation(
            identifier=org_name,
            user_key=org_name,
            municipality_code=municipality_code
        )
        self.employee_forced_uuids = forced_uuids

        self.nodes = {}  # Will be populated when org-tree is created
        self.add_people()
        self.info = self._read_department_info()
        for level in [(1040, 'Leder'), (1035, 'Chef'), (1030, 'Direktør')]:
            self._add_klasse(level[0], level[1], 'manager_level')

        self._add_klasse('Pnummer', 'Pnummer',
                         'org_unit_address_type', 'PNUMBER')
        self._add_klasse('AddressMailUnit', 'Postdresse',
                         'org_unit_address_type', 'DAR')
        self._add_klasse('AdresseReturUnit', 'Returadresse',
                         'org_unit_address_type', 'DAR')
        self._add_klasse('AdresseHenvendelseUnit', 'Henvendelsessted',
                         'org_unit_address_type', 'DAR')
        self._add_klasse('PhoneUnit', 'Telefon',
                         'org_unit_address_type', 'PHONE')
        self._add_klasse('EmailUnit', 'Email',
                         'org_unit_address_type', 'EMAIL')

        self._add_klasse('AdressePostEmployee', 'Postadresse',
                         'employee_address_type', 'DAR')
        self._add_klasse('PhoneEmployee', 'Telefon',
                         'employee_address_type', 'PHONE')
        self._add_klasse('LocationEmployee', 'Lokation',
                         'employee_address_type', 'TEXT')
        self._add_klasse('EmailEmployee', 'Email',
                         'employee_address_type', 'EMAIL')

        self._add_klasse('Orphan', 'Virtuel Enhed', 'org_unit_type')

        self._add_klasse('Lederansvar', 'Lederansvar', 'responsibility')

        self._add_klasse('Ansat', 'Ansat', 'engagement_type')

        self._add_klasse('non-primary', 'Ikke-primær ansættelse', 'engagement_type')

        self._add_klasse('SD-medarbejder', 'SD-medarbejder', 'association_type')

        self._add_klasse('Ekstern', 'Må vises eksternt', 'visibility', 'PUBLIC')
        self._add_klasse('Intern', 'Må vises internt', 'visibility', 'INTERNAL')
        self._add_klasse('Hemmelig', 'Hemmelig', 'visibility', 'SECRET')

    def _sd_lookup(self, url, params={}):
        full_url = self.base_url + url

        payload = {
            'InstitutionIdentifier': INSTITUTION_IDENTIFIER,
        }
        payload.update(params)
        m = hashlib.sha256()
        m.update(str(payload).encode())
        m.update(full_url.encode())
        lookup_id = m.hexdigest()

        try:
            with open(lookup_id + '.p', 'rb') as f:
                response = pickle.load(f)
            print('CACHED')
        except FileNotFoundError:
            response = requests.get(
                full_url,
                params=payload,
                auth=(SD_USER, SD_PASSWORD)
            )
            with open(lookup_id + '.p', 'wb') as f:
                pickle.dump(response, f, pickle.HIGHEST_PROTOCOL)

        xml_response = xmltodict.parse(response.text)[url]
        return xml_response

    def _read_department_info(self):
        """ Load all deparment details and store for later user """
        department_info = {}

        params = {
            'ActivationDate': GLOBAL_GET_DATE.strftime('%d.%m.%Y'),
            'DeactivationDate': GLOBAL_GET_DATE.strftime('%d.%m.%Y'),
            'ContactInformationIndicator': 'true',
            'DepartmentNameIndicator': 'true',
            'PostalAddressIndicator': 'true',
            'ProductionUnitIndicator': 'true',
            'UUIDIndicator': 'true',
            'EmploymentDepartmentIndicator': 'false'
        }
        departments = self._sd_lookup('GetDepartment20111201', params)

        for department in departments['Department']:
            uuid = department['DepartmentUUIDIdentifier']
            department_info[uuid] = department
            unit_type = department['DepartmentLevelIdentifier']
            if not self.importer.check_if_exists('klasse', unit_type):
                self.importer.add_klasse(identifier=unit_type,
                                         facet_type_ref='org_unit_type',
                                         user_key=unit_type,
                                         title=unit_type,
                                         scope='TEXT')
        return department_info

    def _add_klasse(self, klasse_id, klasse, facet, scope='TEXT'):
        if isinstance(klasse_id, str):
            klasse_id = klasse_id.replace('&', '_')
        if not self.importer.check_if_exists('klasse', klasse_id):
            self.importer.add_klasse(identifier=klasse_id,
                                     facet_type_ref=facet,
                                     user_key=str(klasse_id),
                                     scope=scope,
                                     title=klasse)
        return klasse_id

    def _dawa_lookup(self, address):
        """ Lookup an APOS address object in DAWA and find a UUID
        for the address.
        :param address: APOS address object
        :return: DAWA UUID for the address, or None if it is not found
        """
        dar_uuid = None
        dar_data = _dawa_request(address)
        if len(dar_data) == 0:
            # Found no hits, first attempt is to remove the letter
            # from the address
            dar_data = _dawa_request(address, skip_letters=True,
                                     adgangsadresse=True)
            if len(dar_data) == 1:
                dar_uuid = dar_data[0]['id']
        elif len(dar_data) == 1:
            dar_uuid = dar_data[0]['id']
        else:
            # Multiple results typically means we have found an
            # adgangsadresse
            dar_data = _dawa_request(address, adgangsadresse=True)
            if len(dar_data) == 1:
                dar_uuid = dar_data[0]['id']
        return dar_uuid

    def _add_sd_department(self, department, contains_subunits=False):
        """
        Add add a deparment to MO. If the unit has parents, these will
        also be added
        :param department: The SD-department, including parent units.
        :param contains_subunits: True if the unit has sub-units.
        """
        ou_level = department['DepartmentLevelIdentifier']
        unit_id = department['DepartmentUUIDIdentifier']
        user_key = department['DepartmentIdentifier']
        parent_uuid = None
        if 'DepartmentReference' in department:
            parent_uuid = (department['DepartmentReference']
                           ['DepartmentUUIDIdentifier'])

        info = self.info[unit_id]
        assert(info['DepartmentLevelIdentifier'] == ou_level)

        if not contains_subunits and parent_uuid is None:
            parent_uuid = 'OrphanUnits'

        date_from = info['ActivationDate']
        # No units have termination dates: date_to is None
        if not self.importer.check_if_exists('organisation_unit', unit_id):
            self.importer.add_organisation_unit(
                identifier=unit_id,
                name=info['DepartmentName'],
                user_key=user_key,
                type_ref=ou_level,
                date_from=date_from,
                uuid=unit_id,
                date_to=None,
                parent_ref=parent_uuid)

        if 'ContactInformation' in info:
            emails = info['ContactInformation']['EmailAddressIdentifier']
            for email in emails:
                if email.find('Empty') == -1:
                    self.importer.add_address_type(
                        organisation_unit=unit_id,
                        type_ref='EmailUnit',
                        value=email,
                        date_from=date_from
                    )
            if 'TelephoneNumberIdentifier' in info['ContactInformation']:
                # We only a sinlge phnone number, this is most likely
                # no a real number
                pass

        if 'ProductionUnitIdentifier' in info:
            self.importer.add_address_type(
                organisation_unit=unit_id,
                type_ref='Pnummer',
                value=info['ProductionUnitIdentifier'],
                date_from=date_from
            )

        if 'PostalAddress' in info:
            needed = ['StandardAddressIdentifier', 'PostalCode']
            if all(element in info['PostalAddress'] for element in needed):
                dar_uuid = self._dawa_lookup(info['PostalAddress'])
                if dar_uuid is not None:
                    self.importer.add_address_type(
                        organisation_unit=unit_id,
                        type_ref='AddressMailUnit',
                        value=dar_uuid,
                        date_from=date_from
                    )
                else:
                    self.address_errors[unit_id] = info

        # Include higher level OUs, these do not have their own entry in SD
        if 'DepartmentReference' in department:
            self._add_sd_department(department['DepartmentReference'],
                                    contains_subunits=True)

    def _create_org_tree_structure(self):
        nodes = {}
        all_ous = self.importer.export('organisation_unit')
        new_ous = []
        for key, ou in all_ous.items():
            parent = ou.parent_ref
            if parent is None:
                print(ou)
                uuid = key
                print(uuid)
                print('----')
                niveau = ou.type_ref
                nodes[uuid] = Node(niveau, uuid=uuid)
            else:
                new_ous.append(ou)

        while len(new_ous) > 0:
            print(len(new_ous))
            all_ous = new_ous
            new_ous = []
            for ou in all_ous:
                parent = ou.parent_ref
                if parent in nodes.keys():
                    uuid = ou.uuid
                    niveau = ou.type_ref
                    nodes[uuid] = Node(niveau, parent=nodes[parent], uuid=uuid)
                else:
                    new_ous.append(ou)
        return nodes

    def add_people(self):
        """ Load all person details and store for later user """
        params = {
            'EffectiveDate': GLOBAL_GET_DATE.strftime('%d.%m.%Y'),
            'StatusActiveIndicator': 'true',
            'StatusPassiveIndicator': 'false',
            'ContactInformationIndicator': 'false',
            'PostalAddressIndicator': 'false'
        }
        people = self._sd_lookup('GetPerson20111201', params)

        for person in people['Person']:
            cpr = person['PersonCivilRegistrationIdentifier']
            name = (person['PersonGivenName'] + ' ' +
                    person['PersonSurnameName'])
            uuid = self.employee_forced_uuids.get(cpr, None)
            print(cpr)
            print(uuid)

            self.importer.add_employee(
                name=name,
                identifier=cpr,
                cpr_no=cpr,
                user_key=name,
                uuid=uuid
            )

    def create_ou_tree(self):
        """ Read all department levels from SD """
        self.importer.add_organisation_unit(
                identifier='OrphanUnits',
                name='Forældreløse enheder',
                user_key='OrphanUnits',
                type_ref='Orphan',
                date_from='1900-01-01',
                date_to=None,
                parent_ref=None)
        params = {
            'ActivationDate': GLOBAL_GET_DATE.strftime('%d.%m.%Y'),
            'DeactivationDate': GLOBAL_GET_DATE.strftime('%d.%m.%Y'),
            'UUIDIndicator': 'true'
        }
        organisation = self._sd_lookup('GetOrganization20111201', params)

        departments = organisation['Organization']['DepartmentReference']
        for department in departments:
            self._add_sd_department(department)
        self.nodes = self._create_org_tree_structure()

    def create_employees(self):
        params = {
            'EffectiveDate': GLOBAL_GET_DATE.strftime('%d.%m.%Y'),
            'StatusActiveIndicator': 'true',
            'DepartmentIndicator': 'true',
            'EmploymentStatusIndicator': 'true',
            'ProfessionIndicator': 'true',
            'WorkingTimeIndicator': 'true',
            'UUIDIndicator': 'true',
            'StatusPassiveIndicator': 'false',
            'SalaryAgreementIndicator': 'false',
            'SalaryCodeGroupIndicator': 'false'
        }
        persons = self._sd_lookup('GetEmployment20111201', params)

        for person in persons['Person']:
            cpr = person['PersonCivilRegistrationIdentifier']
            employments = person['Employment']
            if not isinstance(employments, list):
                employments = [employments]

            max_rate = 0
            min_id = 999999
            for employment in employments:
                status = employment['EmploymentStatus']['EmploymentStatusCode']
                if (int(status) == 0):
                    continue
                employment_id = int(employment['EmploymentIdentifier'])
                occupation_rate = float(employment['WorkingTime']
                                        ['OccupationRate'])
                if occupation_rate == 0:
                    continue

                if occupation_rate == max_rate:
                    if employment_id < min_id:
                        min_id = employment_id
                if occupation_rate > max_rate:
                    max_rate = occupation_rate
                    min_id = employment_id

            exactly_one_primary = False
            for employment in employments:
                status = employment['EmploymentStatus']['EmploymentStatusCode']
                if int(status) == 0:
                    continue
                occupation_rate = float(employment['WorkingTime']
                                        ['OccupationRate'])
                employment_id = int(employment['EmploymentIdentifier'])

                if occupation_rate == max_rate and employment_id == min_id:
                    assert(exactly_one_primary is False)
                    engagement_type_ref = 'Ansat'
                    exactly_one_primary = True
                else:
                    engagement_type_ref = 'non-primary'

                job_id = int(employment['Profession']['JobPositionIdentifier'])
                job_func = employment['Profession']['EmploymentName']
                job_func_ref = self._add_klasse(job_func,
                                                job_func,
                                                'engagement_job_function')
                emp_dep = employment['EmploymentDepartment']
                unit = emp_dep['DepartmentUUIDIdentifier']

                date_from = emp_dep['ActivationDate']
                date_to = emp_dep['DeactivationDate']
                if date_to == '9999-12-31':
                    date_to = None

                # Employees are not allowed to be in these units (allthough
                # we do make an association). We must instead find the lowest
                # higher level to put she or he.
                too_deep = ['Afdelings-niveau', 'NY1-niveau', 'NY2-niveau']
                original_unit = unit
                while self.nodes[unit].name in too_deep:
                    unit = self.nodes[unit].parent.uuid
                try:
                    self.importer.add_engagement(
                        employee=cpr,
                        organisation_unit=unit,
                        job_function_ref=job_func_ref,
                        engagement_type_ref=engagement_type_ref,
                        date_from=date_from,
                        date_to=date_to
                    )
                    # Remove this to remove any sign of the employee from the
                    # lowest levels of the org
                    self.importer.add_association(
                        employee=cpr,
                        organisation_unit=original_unit,
                        association_type_ref='SD-medarbejder',
                        date_from=date_from
                    )

                except AssertionError:
                    self.double_employment.append(cpr)
                if job_id in [1040, 1035, 1030]:
                    manager_type_ref = 'manager_type_' + job_func
                    manager_type_ref = self._add_klasse(manager_type_ref,
                                                        job_func,
                                                        'manager_type')

                    self.importer.add_manager(
                        employee=cpr,
                        organisation_unit=unit,
                        manager_level_ref=job_id,
                        address_uuid=None,  # TODO?
                        manager_type_ref=manager_type_ref,
                        responsibility_list=['Lederansvar'],
                        date_from=date_from,
                        date_to=date_to
                    )
            # This assertment really should hold...
            # assert(exactly_one_primary is True)
            if exactly_one_primary is not True:
                print()
                print(employments)
