import json
import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from operator import itemgetter
from pathlib import Path
from typing import Tuple

import click
import requests
import xmltodict
from mox_helpers import mox_util
from os2mo_helpers.mora_helpers import MoraHelper
from ra_utils.load_settings import load_settings
from requests import Session
from tqdm import tqdm

import constants
from integrations import dawa_helper
from integrations.ad_integration import ad_reader
from integrations.calculate_primary.opus import OPUSPrimaryEngagementUpdater
from integrations.opus import opus_helpers, payloads
from integrations.opus.opus_exceptions import (
    EmploymentIdentifierNotUnique,
    ImporterrunNotCompleted,
    RunDBInitException,
    UnknownOpusUnit,
)
from integrations.SD_Lon.db_overview import DBOverview
from os2mo_data_import import ImportHelper

logger = logging.getLogger("opusDiff")

LOG_LEVEL = logging.DEBUG
LOG_FILE = "mo_integrations.log"

logger = logging.getLogger("opusImport")

for name in logging.root.manager.loggerDict:
    if name in (
        "opusImport",
        "opusHelper",
        "opusDiff",
        "moImporterMoraTypes",
        "moImporterMoxTypes",
        "moImporterUtilities",
        "moImporterHelpers",
        "ADReader",
    ):
        logging.getLogger(name).setLevel(LOG_LEVEL)
    else:
        logging.getLogger(name).setLevel(logging.ERROR)

logging.basicConfig(
    format="%(levelname)s %(asctime)s %(name)s %(message)s",
    level=LOG_LEVEL,
    filename=LOG_FILE,
)
UNIT_ADDRESS_CHECKS = {
    "seNr": constants.addresses_unit_se,
    "cvrNr": constants.addresses_unit_cvr,
    "eanNr": constants.addresses_unit_ean,
    "pNr": constants.addresses_unit_pnr,
    "phoneNumber": constants.addresses_unit_phoneNumber,
    "dar": constants.addresses_unit_dar,
}

EMPLOYEE_ADDRESS_CHECKS = {
    "phone": constants.addresses_employee_phone,
    "email": constants.addresses_employee_email,
    "dar": constants.addresses_employee_dar,
}
predefined_scopes = {
    constants.addresses_employee_dar: "DAR",
    constants.addresses_employee_phone: "PHONE",
    constants.addresses_employee_email: "EMAIL",
    constants.addresses_unit_dar: "DAR",
    constants.addresses_unit_phoneNumber: "PHONE",
    constants.addresses_unit_ean: "EAN",
    constants.addresses_unit_cvr: "TEXT",
    constants.addresses_unit_pnr: "TEXT",
    constants.addresses_unit_se: "TEXT",
}


class OpusDiffImport(object):
    def __init__(self, xml_date, ad_reader, employee_mapping={}):
        logger.info("Opus diff importer __init__ started")
        self.xml_date = xml_date
        self.ad_reader = ad_reader
        self.employee_forced_uuids = employee_mapping

        self.settings = load_settings()
        self.filter_ids = self.settings.get("integrations.opus.units.filter_ids", [])

        self.session = Session()
        self.helper = self._get_mora_helper(
            hostname=self.settings["mora.base"], use_cache=False
        )
        try:
            self.org_uuid = self.helper.read_organisation()
        except KeyError:
            msg = "No root organisation in MO"
            logger.warning(msg)
            print(msg)
            return
        except requests.exceptions.RequestException as e:
            logger.error(e)
            print(e)
            exit()
        self.updater = OPUSPrimaryEngagementUpdater()

        it_systems = self.helper.read_it_systems()
        self.it_systems = dict(map(itemgetter("name", "uuid"), it_systems))

        logger.info("__init__ done, now ready for import")

    def _find_classes(self, facet):
        class_types = self.helper.read_classes_in_facet(facet)
        types_dict = {}
        facet = class_types[1]
        for class_type in class_types[0]:
            types_dict[class_type["user_key"]] = class_type["uuid"]
        return types_dict, facet

    def _get_mora_helper(self, hostname="localhost:5000", use_cache=False):
        return MoraHelper(hostname=self.settings["mora.base"], use_cache=False)

    # This exact function also exists in sd_changed_at
    def _assert(self, response):
        """Check response is as expected"""
        assert response.status_code in (200, 400, 404)
        if response.status_code == 400:
            # Check actual response
            assert response.text.find("not give raise to a new registration") > 0
            logger.debug("Requst had no effect")
        return None

    def _get_organisationfunktion(self, lora_uuid):
        resource = "/organisation/organisationfunktion/{}"
        resource = resource.format(lora_uuid)
        response = self.session.get(url=self.settings["mox.base"] + resource)
        response.raise_for_status()
        data = response.json()
        data = data[lora_uuid][0]["registreringer"][0]
        # logger.debug('Organisationsfunktionsinfo: {}'.format(data))
        return data

    def _find_engagement(self, bvn, funktionsnavn, present=False):
        info = {}
        resource = "/organisation/organisationfunktion?bvn={}&funktionsnavn={}".format(
            bvn, funktionsnavn
        )
        if present:
            resource += "&gyldighed=Aktiv"
        response = self.session.get(url=self.settings["mox.base"] + resource)
        response.raise_for_status()
        uuids = response.json()["results"][0]
        if len(uuids) > 1:
            msg = "Employment ID {} not unique: {}".format(bvn, uuids)
            logger.error(msg)
            raise EmploymentIdentifierNotUnique(msg)

        logger.info("bvn: {}, uuid: {}".format(bvn, uuids))
        if uuids:
            return uuids[0]

    def validity(self, employee, edit=False):
        """
        Calculates a validity object from en employee object.
        :param employee: An Opus employee object.
        :param edit: If True from will be current dump date, if true
        from will be taken from emploee object.
        :return: A valid MO valididty payload
        """
        to_date = employee["leaveDate"]
        # if to_date is None: # This can most likely be removed
        #     to_datetime = datetime.strptime('9999-12-31', '%Y-%m-%d')
        # else:
        #     to_datetime = datetime.strptime(to_date, '%Y-%m-%d')

        from_date = employee["entryDate"]
        if (from_date is None) or edit:
            from_date = self.xml_date.strftime("%Y-%m-%d")
        validity = {"from": from_date, "to": to_date}
        return validity

    def _condense_employee_mo_addresses(self, mo_uuid):
        """
        Read all addresses from MO an return as a simple dict
        """
        # Unfortunately, mora-helper currently does not read all addresses
        user_addresses = self.helper._mo_lookup(mo_uuid, "e/{}/details/address")
        address_dict = {}  # Condensate of all MO addresses for the employee
        if not isinstance(user_addresses, list):
            # In case the request to mo fails we assume no addresses in MO.
            # This has happend when the something in lora has been deleted.
            return address_dict

        for address in user_addresses:
            if address_dict.get(address["address_type"]["uuid"]) is not None:
                # More than one of this type exist in MO, this is not allowed.
                msg = "Inconsistent addresses for employee: {}"
                logger.error(msg.format(mo_uuid))
            address_dict[address["address_type"]["uuid"]] = {
                "value": address["value"],
                "uuid": address["uuid"],
            }
        return address_dict

    def _condense_employee_opus_addresses(self, employee):
        opus_addresses = {}
        if "email" in employee:
            opus_addresses["email"] = employee["email"]

        opus_addresses["phone"] = None
        if employee["workPhone"] is not None:
            phone = opus_helpers.parse_phone(employee["workPhone"])
            if phone is not None:
                opus_addresses["phone"] = phone

        if "postalCode" in employee and employee["address"]:
            if isinstance(employee["address"], dict):
                logger.info("Protected addres, cannont import")
            else:
                address_string = employee["address"]
                zip_code = employee["postalCode"]
                try:
                    address_uuid = dawa_helper.dawa_lookup(address_string, zip_code)
                except:
                    address_uuid = None
                if address_uuid:
                    opus_addresses["dar"] = address_uuid
                else:
                    logger.warning("Could not find address in DAR")
        return opus_addresses

    def _perform_address_update(self, args, current):
        addr_type = args["address_type"]["uuid"]
        if current is None:  # Create address
            payload = payloads.create_address(**args)
            logger.debug("Create {} address payload: {}".format(addr_type, payload))
            response = self.helper._mo_post("details/create", payload)
            assert response.status_code == 201
        elif args.get("value") == current.get("value"):  # Nothing changed
            logger.info("{} not updated".format(addr_type))
        else:  # Edit address
            payload = payloads.edit_address(args, current["uuid"])
            logger.debug("Edit address {}, payload: {}".format(addr_type, payload))
            response = self.helper._mo_post("details/edit", payload)
            response.raise_for_status()

    def _update_employee_address(self, mo_uuid, employee):
        opus_addresses = self._condense_employee_opus_addresses(employee)
        mo_addresses = self._condense_employee_mo_addresses(mo_uuid)
        logger.info("Addresses to be synced to MO: {}".format(opus_addresses))

        for addr_type, mo_addr_type in EMPLOYEE_ADDRESS_CHECKS.items():
            if opus_addresses.get(addr_type) is None:
                continue

            addr_type_uuid, _ = mox_util.ensure_class_in_lora(
                "employee_address_type",
                mo_addr_type,
                scope=predefined_scopes.get(mo_addr_type),
            )
            current = mo_addresses.get(addr_type_uuid)
            address_args = {
                "address_type": {"uuid": addr_type_uuid},
                "value": opus_addresses[addr_type],
                "validity": {"from": self.xml_date.strftime("%Y-%m-%d"), "to": None},
                "user_uuid": mo_uuid,
            }
            self._perform_address_update(address_args, current)

    def _update_unit_addresses(self, unit):
        calculated_uuid = opus_helpers.generate_uuid(unit["@id"])
        unit_addresses = self.helper.read_ou_address(
            calculated_uuid, scope=None, return_all=True
        )

        address_dict = {}
        for address in unit_addresses:
            if address_dict.get(address["type"]) is not None:
                # More than one of this type exist in MO, this is not allowed.
                msg = "Inconsistent addresses for unit: {}"
                logger.error(msg.format(calculated_uuid))
            # if address['value'] not in ('9999999999999', '0000000000'):
            address_dict[address["type"]] = {
                "value": address["value"],
                "uuid": address["uuid"],
            }

        if unit["street"] and unit["zipCode"]:
            try:
                address_uuid = dawa_helper.dawa_lookup(unit["street"], unit["zipCode"])
            except:
                address_uuid = None
            if address_uuid:
                logger.debug("Found DAR uuid: {}".format(address_uuid))
                unit["dar"] = address_uuid
            else:
                logger.warning(
                    "Failed to lookup {}, {}".format(unit["street"], unit["zipCode"])
                )

        for addr_type, mo_addr_type in UNIT_ADDRESS_CHECKS.items():
            # addr_type is the opus name for the address, mo_addr_type
            # is read from MO
            if unit.get(addr_type) is None:
                continue

            addr_type_uuid, _ = mox_util.ensure_class_in_lora(
                "org_unit_address_type",
                mo_addr_type,
                scope=predefined_scopes.get(mo_addr_type),
            )
            current = address_dict.get(addr_type_uuid)
            args = {
                "address_type": {"uuid": addr_type_uuid},
                "value": unit[addr_type],
                "validity": {"from": self.xml_date.strftime("%Y-%m-%d"), "to": None},
                "unit_uuid": str(calculated_uuid),
            }
            self._perform_address_update(args, current)

    def update_unit(self, unit):
        calculated_uuid = opus_helpers.generate_uuid(unit["@id"])
        parent_name = unit["parentOrgUnit"]
        parent_uuid = (
            opus_helpers.generate_uuid(parent_name)
            if parent_name
            else self.helper.read_organisation()
        )
        mo_unit = self.helper.read_ou(calculated_uuid)

        # Default 'Enhed' is the default from the initial import
        org_type = unit.get("orgTypeTxt", "Enhed")

        unit_type, _ = mox_util.ensure_class_in_lora("org_unit_type", org_type)
        from_date = unit.get("startDate", "01-01-1900")
        unit_args = {
            "unit": unit,
            "unit_uuid": str(calculated_uuid),
            "unit_type": unit_type,
            "parent": str(parent_uuid),
            "from_date": from_date,
        }

        if mo_unit.get("uuid"):  # Edit
            unit_args["from_date"] = self.xml_date.strftime("%Y-%m-%d")
            payload = payloads.edit_org_unit(**unit_args)
            logger.info("Edit unit: {}".format(payload))
            response = self.helper._mo_post("details/edit", payload)
            if response.status_code == 400:
                assert response.text.find("raise to a new registration") > 0
            else:
                response.raise_for_status()
        else:  # Create
            payload = payloads.create_org_unit(**unit_args)
            logger.debug("Create department payload: {}".format(payload))
            response = self.helper._mo_post("ou/create", payload)
            response.raise_for_status()
            logger.info("Created unit {}".format(unit["@id"]))
            logger.debug("Response: {}".format(response.text))

        self._update_unit_addresses(unit)

    def _job_and_engagement_type(self, employee):
        job = employee["position"]
        job_function_uuid, _ = mox_util.ensure_class_in_lora(
            "engagement_job_function", job
        )

        contract = employee.get("workContractText", "Ansat")
        engagement_type_uuid, _ = mox_util.ensure_class_in_lora(
            "engagement_type", contract
        )
        return job_function_uuid, engagement_type_uuid

    def update_engagement(self, engagement, employee):
        """
        Update a MO engagement according to opus employee object.
        It often happens that the change that provoked lastChanged to
        be updated is not a MO field, and thus we check for relevant
        differences before shipping the payload to MO.
        :param engagement: Relevant MO engagement object.
        :param employee: Relevent Opus employee object.
        :return: True if update happended, False if not.
        """
        if employee["orgUnit"] in self.filter_ids:
            logger.warning("Engagement is to a filtered unit.")
            return False
        job_function, eng_type = self._job_and_engagement_type(employee)
        unit_uuid = opus_helpers.generate_uuid(employee["orgUnit"])

        validity = self.validity(employee, edit=True)
        data = {
            "engagement_type": {"uuid": eng_type},
            "job_function": {"uuid": job_function},
            "org_unit": {"uuid": str(unit_uuid)},
            "validity": validity,
        }

        engagement_unit = self.helper.read_ou(unit_uuid)
        if "error" in engagement_unit:
            msg = "The wanted unit does not exit: {}"
            logger.error(msg.format(unit_uuid))
            raise UnknownOpusUnit

        if engagement["validity"]["to"] is None:
            old_valid_to = datetime.strptime("9999-12-31", "%Y-%m-%d")
        else:
            old_valid_to = datetime.strptime(engagement["validity"]["to"], "%Y-%m-%d")
        if validity["to"] is None:
            new_valid_to = datetime.strptime("9999-12-31", "%Y-%m-%d")
        else:
            new_valid_to = datetime.strptime(validity["to"], "%Y-%m-%d")

        something_new = not (
            (engagement["engagement_type"]["uuid"] == eng_type)
            and (engagement["job_function"]["uuid"] == job_function)
            and (engagement["org_unit"]["uuid"] == str(unit_uuid))
            and (old_valid_to == new_valid_to)
        )

        logger.info("Something new? {}".format(something_new))
        if something_new:
            payload = payloads.edit_engagement(data, engagement["uuid"])
            logger.debug("Update engagement payload: {}".format(payload))
            response = self.helper._mo_post("details/edit", payload)
            self._assert(response)

        if new_valid_to < old_valid_to:
            self.terminate_detail(
                engagement["uuid"], detail_type="engagement", end_date=new_valid_to
            )
        return something_new

    def create_engagement(self, mo_user_uuid, opus_employee):
        job_function, eng_type = self._job_and_engagement_type(opus_employee)
        unit_uuid = opus_helpers.generate_uuid(opus_employee["orgUnit"])

        engagement_unit = self.helper.read_ou(unit_uuid)
        if "error" in engagement_unit:
            msg = "The wanted unit does not exit: {}"
            logger.error(msg.format(opus_employee["orgUnit"]))
            raise UnknownOpusUnit

        validity = self.validity(opus_employee, edit=False)
        payload = payloads.create_engagement(
            employee=opus_employee,
            user_uuid=mo_user_uuid,
            unit_uuid=unit_uuid,
            job_function=job_function,
            engagement_type=eng_type,
            primary=self.updater.primary_types["non_primary"],
            validity=validity,
        )
        logger.debug("Create engagement payload: {}".format(payload))
        response = self.helper._mo_post("details/create", payload)
        assert response.status_code == 201

    def create_user(self, employee, uuid=None):
        cpr = opus_helpers.read_cpr(employee)
        payload = payloads.create_user(employee, self.org_uuid, uuid)

        logger.info("Create user payload: {}".format(payload))
        r = self.helper._mo_post("e/create", payload)
        r.raise_for_status()
        return_uuid = r.json()
        logger.info(
            "Created employee {} {} with uuid {}".format(
                employee["firstName"], employee["lastName"], return_uuid
            )
        )

        return return_uuid

    def connect_it_system(self, username, it_system, employee, person_uuid):
        it_system_uuid = self.it_systems[it_system]
        current = self.helper.get_e_itsystems(
            person_uuid, it_system_uuid=it_system_uuid
        )
        # TODO: Edit it system if value has changed.
        if not current:
            payload = payloads.connect_it_system_to_user(
                username,
                it_system_uuid,
                person_uuid,
                self.xml_date.strftime("%Y-%m-%d"),
            )
            logger.debug(f"{it_system} account payload: {payload}")
            response = self.helper._mo_post("details/create", payload)
            assert response.status_code == 201
            logger.info(f"Added {it_system} info to {person_uuid}")

    def _to_datetime(self, item):
        if item is None:
            item_datetime = datetime.strptime("9999-12-31", "%Y-%m-%d")
        else:
            item_datetime = datetime.strptime(item, "%Y-%m-%d")
        return item_datetime

    def update_manager_status(self, employee_mo_uuid, employee):
        url = "e/{}/details/manager?at=" + self.validity(employee, edit=True)["from"]
        manager_functions = self.helper._mo_lookup(employee_mo_uuid, url)
        logger.debug("Manager functions to update: {}".format(manager_functions))
        if manager_functions:
            logger.debug("Manager functions to update: {}".format(manager_functions))

        if employee["isManager"] == "false":
            if manager_functions:
                logger.info("Terminate manager function")
                self.terminate_detail(
                    manager_functions[0]["uuid"], detail_type="manager"
                )
            else:
                logger.debug("Correctly not a manager")

        if employee["isManager"] == "true":
            manager_level = "{}.{}".format(
                employee["superiorLevel"], employee["subordinateLevel"]
            )
            manager_level_uuid, _ = mox_util.ensure_class_in_lora(
                "manager_level", manager_level
            )
            manager_type = employee["position"]
            manager_type_uuid, _ = mox_util.ensure_class_in_lora(
                "manager_type", manager_type
            )
            responsibility_uuid, _ = mox_util.ensure_class_in_lora(
                "responsibility", "Lederansvar"
            )

            args = {
                "unit": str(opus_helpers.generate_uuid(employee["orgUnit"])),
                "person": employee_mo_uuid,
                "manager_type": manager_type_uuid,
                "level": manager_level_uuid,
                "responsibility": responsibility_uuid,
                "validity": self.validity(employee, edit=True),
            }
            if manager_functions:
                logger.info("Attempt manager update of {}:".format(employee_mo_uuid))
                # Currently Opus supports only a single manager object pr employee
                assert len(manager_functions) == 1

                mf = manager_functions[0]

                payload = payloads.edit_manager(
                    object_uuid=manager_functions[0]["uuid"], **args
                )

                something_new = not (
                    mf["org_unit"]["uuid"] == args["unit"]
                    and mf["person"]["uuid"] == args["person"]
                    and mf["manager_type"]["uuid"] == args["manager_type"]
                    and mf["manager_level"]["uuid"] == args["level"]
                    and mf["responsibility"][0]["uuid"] == args["responsibility"]
                )

                if something_new:
                    logger.debug("Something is changed, execute payload")
                else:
                    mo_end_datetime = self._to_datetime(mf["validity"]["to"])
                    opus_end_datetime = self._to_datetime(args["validity"]["to"])
                    logger.info("MO end datetime: {}".format(mo_end_datetime))
                    logger.info("OPUS end datetime: {}".format(opus_end_datetime))

                    if mo_end_datetime == opus_end_datetime:
                        logger.info("No edit of manager object")
                        payload = None
                    elif opus_end_datetime > mo_end_datetime:
                        logger.info("Extend validity, send payload to MO")
                    else:  # opus_end_datetime < mo_end_datetime:
                        logger.info("Terminate mangement role")
                        payload = None
                        self.terminate_detail(
                            mf["uuid"],
                            detail_type="manager",
                            end_date=opus_end_datetime,
                        )

                logger.debug("Update manager payload: {}".format(payload))
                if payload is not None:
                    response = self.helper._mo_post("details/edit", payload)
                    self._assert(response)
            else:  # No existing manager functions
                logger.info("Turn this person into a manager")
                # Validity is set to edit=True since the validiy should
                # calculated as an edit to the engagement
                payload = payloads.create_manager(user_key=employee["@id"], **args)
                logger.debug("Create manager payload: {}".format(payload))
                response = self.helper._mo_post("details/create", payload)
                assert response.status_code == 201

    def update_roller(self, employee):
        cpr = employee["cpr"]["#text"]
        mo_user = self.helper.read_user(user_cpr=cpr)
        logger.info("Check {} for updates in Roller".format(mo_user["uuid"]))
        if isinstance(employee["function"], dict):
            opus_roles = [employee["function"]]
        else:
            opus_roles = employee["function"]
        mo_roles = self.helper._mo_lookup(mo_user["uuid"], "e/{}/details/role")
        for opus_role in opus_roles:
            opus_end_datetime = datetime.strptime(opus_role["@endDate"], "%Y-%m-%d")
            if opus_role["@endDate"] == "9999-12-31":
                opus_role["@endDate"] = None

            found = False
            for mo_role in mo_roles:
                if "roleText" in opus_role:
                    combined_role = "{} - {}".format(
                        opus_role["artText"], opus_role["roleText"]
                    )
                else:
                    combined_role = opus_role["artText"]

                if (
                    mo_role["person"]["uuid"] == mo_user["uuid"]
                    and combined_role == mo_role["role_type"]["name"]
                ):
                    found = True
                    if mo_role["validity"]["to"] is None:
                        mo_end_datetime = datetime.strptime("9999-12-31", "%Y-%m-%d")
                    else:
                        mo_end_datetime = datetime.strptime(
                            mo_role["validity"]["to"], "%Y-%m-%d"
                        )

                    # We only compare end dates, it is assumed start-date is not
                    # changed.
                    if mo_end_datetime == opus_end_datetime:
                        logger.info("No edit")
                    elif opus_end_datetime > mo_end_datetime:
                        logger.info("Extend role")
                        validity = {
                            "from": opus_role["@startDate"],
                            "to": opus_role["@endDate"],
                        }
                        payload = payloads.edit_role(validity, mo_role["uuid"])
                        logger.debug("Edit role, payload: {}".format(payload))
                        response = self.helper._mo_post("details/edit", payload)
                        self._assert(response)
                    else:  # opus_end_datetime < mo_end_datetime:
                        logger.info("Terminate role")
                        self.terminate_detail(
                            mo_role["uuid"],
                            detail_type="role",
                            end_date=opus_end_datetime,
                        )
            if not found:
                logger.info("Create new role: {}".format(opus_role))
                # TODO: We will fail a if  new role-type surfaces
                role_name = opus_role["artText"]
                role_type, _ = mox_util.ensure_class_in_lora("role_type", role_name)
                payload = payloads.create_role(
                    employee=employee,
                    user_uuid=mo_user["uuid"],
                    unit_uuid=str(opus_helpers.generate_uuid(employee["orgUnit"])),
                    role_type=role_type,
                    validity={
                        "from": opus_role["@startDate"],
                        "to": opus_role["@endDate"],
                    },
                )
                logger.debug("New role, payload: {}".format(payload))
                response = self.helper._mo_post("details/create", payload)
                assert response.status_code == 201

    def update_employee(self, employee):
        cpr = opus_helpers.read_cpr(employee)
        logger.info("----")
        logger.info("Now updating {}".format(employee.get("@id")))
        logger.debug("Available info: {}".format(employee))
        mo_user = self.helper.read_user(user_cpr=cpr, use_cache=False)

        ad_info = {}
        if self.ad_reader is not None:
            ad_info = self.ad_reader.read_user(cpr=cpr)

        if mo_user is None:
            uuid = self.employee_forced_uuids.get(cpr)
            logger.info("Employee in force list: {} {}".format(cpr, uuid))
            logger.info("AD info: {}".format(ad_info))
            if uuid is None:
                uuid = ad_info.get("ObjectGuid")
                if uuid is None:
                    msg = "{} not in MO, UUID list or AD, assign random uuid"
                    logger.debug(msg.format(cpr))
            employee_mo_uuid = self.create_user(employee, uuid)
        else:
            employee_mo_uuid = mo_user["uuid"]

            # Update user if name has changed
            if (employee["firstName"] != mo_user["givenname"]) or (
                employee["lastName"] != mo_user["surname"]
            ):
                employee_mo_uuid = self.create_user(employee, employee_mo_uuid)
                msg = "Updated name of employee {} with uuid {}"
                logger.info(msg.format(cpr, employee_mo_uuid))

        # Add it-systems
        if employee.get("userId"):
            self.connect_it_system(
                employee["userId"], constants.Opus_it_system, employee, employee_mo_uuid
            )

        sam_account = ad_info.get("SamAccountName")
        if sam_account:
            self.connect_it_system(
                sam_account, constants.AD_it_system, employee, employee_mo_uuid
            )

        self._update_employee_address(employee_mo_uuid, employee)

        # Now we have a MO uuid, update engagement:
        mo_engagements = self.helper.read_user_engagement(
            employee_mo_uuid, read_all=True
        )
        user_engagements = filter(
            lambda eng: eng["user_key"] == employee["@id"], mo_engagements
        )
        current_mo_eng = None
        for eng in user_engagements:
            current_mo_eng = eng["uuid"]
            val_from = datetime.strptime(eng["validity"]["from"], "%Y-%m-%d")
            val_to = datetime.strptime("9999-12-31", "%Y-%m-%d")
            if eng["validity"]["to"] is not None:
                val_to = datetime.strptime(eng["validity"]["to"], "%Y-%m-%d")
            if val_from < self.xml_date < val_to:
                logger.info("Found current validty {}".format(eng["validity"]))
                break

        if current_mo_eng is None:
            self.create_engagement(employee_mo_uuid, employee)
        else:
            logger.info("Validity for {}: {}".format(employee["@id"], eng["validity"]))
            self.update_engagement(eng, employee)

        self.update_manager_status(employee_mo_uuid, employee)
        self.updater.recalculate_primary(employee_mo_uuid)

    def terminate_detail(self, uuid, detail_type="engagement", end_date=None):
        if end_date is None:
            end_date = self.xml_date

        payload = payloads.terminate_detail(
            uuid, end_date.strftime("%Y-%m-%d"), detail_type
        )
        logger.debug("Terminate payload: {}".format(payload))
        response = self.helper._mo_post("details/terminate", payload)
        logger.debug("Terminate response: {}".format(response.text))
        self._assert(response)

    def import_single_employment(self, employee):
        # logger.info('Update  employment {} from {}'.format(employment, xml_file))
        last_changed_str = employee.get("@lastChanged")
        if last_changed_str is not None:  # This is a true employee-object.
            self.update_employee(employee)

            if "function" in employee:
                self.update_roller(employee)
            else:
                # Terminate existing roles
                mo_user = self.helper.read_user(user_cpr=employee["cpr"]["#text"])
                role = self.helper.read_user_roller(mo_user["uuid"])
                if role["person"] == mo_user["uuid"]:
                    logger.info("Terminating role: {}".format(role))
                    self.terminate_detail(role["uuid"], detail_type="role")
        else:  # This is an implicit termination.
            # This is a terminated employee, check if engagement is active
            # terminate if it is.
            if not employee["@action"] == "leave":
                msg = "Missing date on a non-leave object!"
                logger.error(msg)
                raise Exception(msg)

            org_funk_info = self._find_engagement(employee["@id"], present=True)
            if org_funk_info:
                logger.info("Terminating: {}".format(org_funk_info))
                self.terminate_detail(org_funk_info["engagement"])
                if "manager" in org_funk_info:
                    self.terminate_detail(
                        org_funk_info["manager"], detail_type="manager"
                    )

    def handle_filtered_units(self, units, terminate=True):
        """Rules for handling units that are not imported from opus.

        If a unit is filtered from the Opus file it means it cannot be deleted in Opus, but should not appear in MO.
        Any units that exists in MO, but are later moved in Opus to be below one of the filtered units should be terminated in MO.
        """
        units = tqdm(units, desc="Terminating filtered units", disable=not terminate)
        ids = map(itemgetter("@id"), units)
        uuids = map(opus_helpers.generate_uuid, ids)
        uuid_strs = map(str, uuids)
        mo_units = map(self.helper.read_ou, uuid_strs)
        mo_units = filter(lambda unit: unit.get("uuid"), mo_units)
        if terminate:
            for mo_unit in mo_units:
                self.terminate_detail(
                    mo_unit["uuid"], detail_type="org_unit", end_date=self.xml_date
                )
        else:
            mo_units = list(mo_units)
            if mo_units:
                print(f"There are units that should have been terminated:")
                print(list(map(itemgetter("uuid"), mo_units)))

    def start_import(self, units, employees, include_terminations=False):
        """
        Start an opus import, run the oldest available dump that
        has not already been imported.
        """

        for unit in tqdm(units, desc="Update units"):
            self.update_unit(unit)

        for employee in tqdm(employees, desc="Update employees"):
            last_changed_str = employee.get("@lastChanged")
            if last_changed_str is not None:  # This is a true employee-object.
                self.update_employee(employee)

                if "function" in employee:
                    self.update_roller(employee)
            else:  # This is an implicit termination.
                if not include_terminations:
                    continue

                # This is a terminated employee, check if engagement is active
                # terminate if it is.
                if not employee["@action"] == "leave":
                    msg = "Missing date on a non-leave object!"
                    logger.error(msg)
                    raise Exception(msg)

                eng_info = self._find_engagement(
                    employee["@id"], "Engagement", present=True
                )
                if eng_info:
                    logger.info("Terminating: {}".format(eng_info))
                    self.terminate_detail(eng_info)
                    manager_info = self._find_engagement(
                        employee["@id"], "Leder", present=True
                    )
                    if manager_info:
                        self.terminate_detail(manager_info, detail_type="manager")

        logger.info("Program ended correctly")


def start_opus_diff(ad_reader=None):
    """
    Start an opus update, use the oldest available dump that has not
    already been imported.
    """
    dumps = opus_helpers.read_available_dumps()
    run_db = Path(SETTINGS["integrations.opus.import.run_db"])
    filter_ids = SETTINGS.get("integrations.opus.units.filter_ids", [])
    employee_mapping = opus_helpers.read_cpr_mapping()

    if not run_db.is_file():
        logger.error("Local base not correctly initialized")
        raise RunDBInitException("Local base not correctly initialized")
    xml_date, latest_date = opus_helpers.next_xml_file(run_db, dumps)

    while xml_date:
        msg = "Start update: File: {}, update since: {}"
        logger.info(msg.format(xml_date, latest_date))
        print(msg.format(xml_date, latest_date))
        # Find changes to units and employees
        units, employees = opus_helpers.file_diff(
            dumps[latest_date], dumps[xml_date], filter_ids
        )
        # Partition based on filtered units in settings
        filtered_units, units = opus_helpers.filter_units(units, filter_ids)
        units = list(units)
        opus_helpers.local_db_insert((xml_date, "Running diff update since {}"))

        diff = OpusDiffImport(
            xml_date, ad_reader=ad_reader, employee_mapping=employee_mapping
        )
        diff.start_import(units, employees, include_terminations=True)
        diff.handle_filtered_units(filtered_units)
        logger.info("Ended update")
        opus_helpers.local_db_insert((xml_date, "Diff update ended: {}"))
        print()
        # Check if there are more files to import
        xml_date, latest_date = opus_helpers.next_xml_file(run_db, dumps)


if __name__ == "__main__":

    SETTINGS = load_settings()

    ad_reader = ad_reader.ADParameterReader()

    try:
        start_opus_diff(ad_reader=ad_reader)
    except RunDBInitException:
        print("RunDB not initialized")
