import logging
import random
import time

from tqdm import tqdm

from .ad_common import AD

logger = logging.getLogger("AdReader")


# SKIP_BRUGERTYPE


def first_included(settings, users):
    """
    include: given a list of users, return the first one that is included
    exclude: given a list of users, return the first one that is not excluded
    """
    discrim_field = settings.get("discriminator.field")

    if not discrim_field:
        return next(iter(users), {})

    users = list(filter(lambda user: discrim_field in user, users))

    for value in settings.get("discriminator.values", []):
        for user in users:
            value_found = value == user[discrim_field]
            if settings["discriminator.function"] == "include" and value_found:
                return user
            if settings["discriminator.function"] == "exclude" and not value_found:
                return user
    return {}


class ADParameterReader(AD):
    def read_encoding(self):
        """
        Read the character encoding of the Power Shell session.
        """
        ps_script = "$OutputEncoding | ConvertTo-Json"
        response = self._run_ps_script(ps_script)
        return response

    def read_it_all(self, print_progress=False):
        return self.cache_all(print_progress=print_progress)

    # Hvornår skal vi læse og skrive i hvad?
    #
    # Opdatering af OS2mo fra AD:
    # -> ad_sync: vi læser alle (for i in...) Ny reader og opdater mo
    #
    # Opdatering af AD fra OS2mo:
    # -> mo_to_ad_sync: skriv kun til det første (og læs kun fra det første)
    #
    # Indlæsning fra Opus og SD:
    # -> Her læser vi fra 0'eren - vi skal have fat i object-guid
    # cpr-uid-map-til rollekatalog skal også kun læse fra 0 (for now....)
    # vi kan teste en del med den, altså:
    # -> venv/bin/python exporters/cpr_uuid.py --use-ad
    #
    # cpr_mo_ad_map.csv har kun uuider/brugernavne pǻ de linier, hvor den
    # sd-importerede bruger også er i AD.

    def uncached_read_user(self, user=None, cpr=None, ria=None):
        # read one or more users using cpr-pattern.
        # if list is passed in ria (read it all) then this is extended
        # with found users - this way the function replaces the old
        # 'read it all' function, so there is now only one function
        # reading from AD.
        settings = self._get_setting()

        logger.debug("Uncached AD read, user {}, cpr {}".format(user, cpr))

        server = None
        if self.all_settings["primary"]["servers"]:
            server = random.choice(self.all_settings["primary"]["servers"])

        response = self.get_from_ad(user=user, cpr=cpr, server=server)

        users_by_cpr = {}
        for user in response:
            users_by_cpr.setdefault(user[settings["cpr_field"]], []).append(user)

        try:
            for userlist in users_by_cpr.values():

                current_user = first_included(settings, userlist)

                if current_user:

                    cpr = current_user[settings["cpr_field"]].replace(
                        settings["cpr_separator"], ""
                    )

                    self.results[current_user["SamAccountName"]] = current_user

                    if settings.get("caseless_samname", False):
                        if (
                            current_user["SamAccountName"]
                            .lower()
                            .startswith(settings["sam_filter"].lower())
                        ):
                            self.results[cpr] = current_user
                    else:
                        if current_user["SamAccountName"].startswith(
                            settings["sam_filter"]
                        ):
                            self.results[cpr] = current_user

                    if ria is not None:
                        ria.append(current_user)

        except Exception:
            logger.error("Response from uncached_read_user: {}".format(response))
            raise

    def cache_all(self, print_progress=False):
        logger.info("Caching all users")
        t = time.time()
        return_value = []
        date_range = range(1, 32)
        if print_progress:
            date_range = tqdm(date_range, desc="Fetching AD accounts")
        for i in date_range:
            day = str(i).zfill(2)
            self.uncached_read_user(cpr="{}*".format(day), ria=return_value)
            logger.debug(len(self.results))
            logger.debug("Read time: {}".format(time.time() - t))
        return return_value

    def read_user(self, user=None, cpr=None, cache_only=False):
        """Read all properties of an AD user.

        The user can be retrived either by cpr or by AD user name.

        :param user: The AD username to retrive.
        :param cpr: CPR number of the user to retrive.
        :param cache_only: Return {} if user is not already cached
        :return: All properties listed in AD for the user.
        """
        logger.debug("Cached AD read, user {}, cpr {}".format(user, cpr))
        if (not cpr) and (not user):
            return

        if user:
            dict_key = user
            if user in self.results:
                return self.results[user]

        if cpr:
            dict_key = cpr
            if cpr in self.results:
                return self.results[cpr]

        if cache_only:
            return {}

        # Populate self.results:
        self.uncached_read_user(user=user, cpr=cpr)

        logger.debug(
            "Returned info for {}: {}".format(dict_key, self.results.get(dict_key, {}))
        )
        return self.results.get(dict_key, {})


if __name__ == "__main__":
    ad_reader = ADParameterReader()
    # import pickle
    # with open("mypickle.p","bw") as f:
    #    f.write(pickle.dumps(ad_reader.read_it_all()))
    everything = ad_reader.read_it_all()
    for user in everything:
        print(
            "Name: {}, Sam: {}, Manager: {} CPR: {}".format(
                user["Name"],
                user["SamAccountName"],
                user.get("Manager"),
                "cpr: " + str(user.get("xAttrCPR")),
            )
        )
        if user["SamAccountName"] == "johndoe":
            for key in sorted(user.keys()):
                print("{}: {}".format(key, user[key]))
