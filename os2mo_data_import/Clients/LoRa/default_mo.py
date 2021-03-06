from pydantic import BaseModel

from os2mo_data_import.Clients.LoRa.model import Facet, Organisation
from os2mo_data_import.util import generate_uuid


class ValidMo(BaseModel):
    """
    Organisation and facets.
    One is expected to populate ALL of these facets with classes!
    """

    organisation: Organisation
    org_unit_address_type: Facet
    employee_address_type: Facet
    address_property: Facet
    engagement_job_function: Facet
    org_unit_type: Facet
    engagement_type: Facet
    engagement_association_type: Facet
    association_type: Facet
    role_type: Facet
    leave_type: Facet
    manager_type: Facet
    responsibility: Facet
    manager_level: Facet
    visibility: Facet
    time_planning: Facet
    org_unit_level: Facet
    primary_type: Facet
    org_unit_hierarchy: Facet

    @classmethod
    def from_scratch(cls) -> "ValidMo":
        """
        For when you know nothing, and don't actually care
        :return: A fully equipped MO; With autogenerated but consistent uuids
        """
        seed = "the_best_seed"
        org_uuid = generate_uuid(seed)
        organisation = Organisation.from_simplified_fields(
            uuid=org_uuid, name="Org_name", user_key="Org_bvn"
        )
        org_unit_address_type = Facet.from_simplified_fields(
            uuid=generate_uuid(seed + "org_unit_address_type"),
            user_key="org_unit_address_type",
            organisation_uuid=org_uuid,
        )
        employee_address_type = Facet.from_simplified_fields(
            uuid=generate_uuid(seed + "employee_address_type"),
            user_key="employee_address_type",
            organisation_uuid=org_uuid,
        )
        address_property = Facet.from_simplified_fields(
            uuid=generate_uuid(seed + "address_property"),
            user_key="address_property",
            organisation_uuid=org_uuid,
        )
        engagement_job_function = Facet.from_simplified_fields(
            uuid=generate_uuid(seed + "engagement_job_function"),
            user_key="engagement_job_function",
            organisation_uuid=org_uuid,
        )
        org_unit_type = Facet.from_simplified_fields(
            uuid=generate_uuid(seed + "org_unit_type"),
            user_key="org_unit_type",
            organisation_uuid=org_uuid,
        )
        engagement_type = Facet.from_simplified_fields(
            uuid=generate_uuid(seed + "engagement_type"),
            user_key="engagement_type",
            organisation_uuid=org_uuid,
        )
        engagement_association_type = Facet.from_simplified_fields(
            uuid=generate_uuid(seed + "engagement_association_type"),
            user_key="engagement_association_type",
            organisation_uuid=org_uuid,
        )
        association_type = Facet.from_simplified_fields(
            uuid=generate_uuid(seed + "association_type"),
            user_key="association_type",
            organisation_uuid=org_uuid,
        )
        role_type = Facet.from_simplified_fields(
            uuid=generate_uuid(seed + "role_type"),
            user_key="role_type",
            organisation_uuid=org_uuid,
        )
        leave_type = Facet.from_simplified_fields(
            uuid=generate_uuid(seed + "leave_type"),
            user_key="leave_type",
            organisation_uuid=org_uuid,
        )
        manager_type = Facet.from_simplified_fields(
            uuid=generate_uuid(seed + "manager_type"),
            user_key="manager_type",
            organisation_uuid=org_uuid,
        )
        responsibility = Facet.from_simplified_fields(
            uuid=generate_uuid(seed + "responsibility"),
            user_key="responsibility",
            organisation_uuid=org_uuid,
        )
        manager_level = Facet.from_simplified_fields(
            uuid=generate_uuid(seed + "manager_level"),
            user_key="manager_level",
            organisation_uuid=org_uuid,
        )
        visibility = Facet.from_simplified_fields(
            uuid=generate_uuid(seed + "visibility"),
            user_key="visibility",
            organisation_uuid=org_uuid,
        )
        time_planning = Facet.from_simplified_fields(
            uuid=generate_uuid(seed + "time_planning"),
            user_key="time_planning",
            organisation_uuid=org_uuid,
        )
        org_unit_level = Facet.from_simplified_fields(
            uuid=generate_uuid(seed + "org_unit_level"),
            user_key="org_unit_level",
            organisation_uuid=org_uuid,
        )
        primary_type = Facet.from_simplified_fields(
            uuid=generate_uuid(seed + "primary_type"),
            user_key="primary_type",
            organisation_uuid=org_uuid,
        )
        org_unit_hierarchy = Facet.from_simplified_fields(
            uuid=generate_uuid(seed + "org_unit_hierarchy"),
            user_key="org_unit_hierarchy",
            organisation_uuid=org_uuid,
        )

        return ValidMo(
            organisation=organisation,
            org_unit_address_type=org_unit_address_type,
            employee_address_type=employee_address_type,
            address_property=address_property,
            engagement_job_function=engagement_job_function,
            org_unit_type=org_unit_type,
            engagement_type=engagement_type,
            engagement_association_type=engagement_association_type,
            association_type=association_type,
            role_type=role_type,
            leave_type=leave_type,
            manager_type=manager_type,
            responsibility=responsibility,
            manager_level=manager_level,
            visibility=visibility,
            time_planning=time_planning,
            org_unit_level=org_unit_level,
            primary_type=primary_type,
            org_unit_hierarchy=org_unit_hierarchy,
        )
