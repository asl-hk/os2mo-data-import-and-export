""" Create dummy data to populate MO """
import pickle
import random
import pathlib
import requests
from datetime import datetime
from datetime import timedelta
from uuid import uuid4
from anytree import Node, PreOrderIter


KLASSER = {
    'Stillingsbetegnelse': [
        'Udvikler', 'Specialkonsulent', 'Ergoterapeut', 'Udviklingskonsulent',
        'Specialist', 'Jurist', 'Personalekonsulent', 'Lønkonsulent',
        'Kontorelev', 'Ressourcepædagog', 'Pædagoisk vejleder',
        'Skolepsykolog', 'Støttepædagog', 'Bogopsætter', 'Timelønnet lærer',
        'Pædagogmedhjælper', 'Teknisk Servicemedarb.', 'Lærer/Overlærer'
    ],
    'Enhedstype': [
        'Afdeling', 'Institutionsafsnit', 'Institution', 'Fagligt center',
        'Direktør område'
    ],
    'Lederansvar': [
        'Personale: ansættelse/afskedigelse',
        'Beredskabsledelse',
        'Personale: øvrige administrative opgaver',
        'Personale: Sygefravær',
        'Ansvar for bygninger og arealer',
        'Personale: MUS-kompetence'
    ],
    'Ledertyper': [
        'Direktør', 'Distriktsleder', 'Beredskabschef', 'Sekretariatschef',
        'Systemadministrator', 'Områdeleder', 'Centerchef', 'Institutionsleder'
    ],
    'Rolletype': [
        'Tillidsrepræsentant', 'Ergonomiambasadør', 'Ansvarlig for sommerfest'
    ],
    'Tilknytningstype': ['Problemknuser', 'Konsulent', 'Medhjælper'],
    'Lederniveau': ['Niveau 1', 'Niveau 2', 'Niveau 3', 'Niveau 4']
}

IT_SYSTEMER = ['Active Directory', 'SAP', 'Office 365', 'Plone', 'Open Desk']

START_DATE = '1960-01-01'


# Name handling
def _path_to_names():
    path = pathlib.Path.cwd()
    path = path / 'navne'
    navne_list = [path / 'fornavne.txt',
                  path / 'mellemnavne.txt',
                  path / 'efternavne.txt']
    return navne_list


def _load_names(name_file):
    """ Load a weighted list of names
    :param name_file: Name of the text file with names
    :return: A weighted list of names
    """
    with name_file.open('r') as f:
        names_file = f.read()
    name_lines = names_file.split('\n')
    names = []
    for name_set in name_lines:
        try:
            parts = name_set.split('\t')
            if parts[2].find(',') > 0:
                subnames = parts[2].split(',')
                for subname in subnames:
                    names.append([int(parts[1]), subname])
            else:
                names.append([int(parts[1]), parts[2]])
        except IndexError:
            pass
    return names


def _telefon():
    """ Create a random phone number
    :return: A random phone number
    """
    tlf = str(random.randrange(1, 9))
    for i in range(0, 7):
        tlf += str(random.randrange(0, 9))
    return tlf


def _cpr(time_from=None):
    """ Create a random valid cpr.
    :return: A valid cpr number
    """
    mod_11_table = [4, 3, 2, 7, 6, 5, 4, 3, 2]
    days_in_month = {
        '01': 31, '02': 28, '03': 31, '04': 30,
        '05': 31, '06': 30, '07': 31, '08': 31,
        '09': 30, '10': 31, '11': 30, '12': 31
    }
    month = list(days_in_month.keys())[random.randrange(0, 12)]
    day = str(random.randrange(1, 1 + days_in_month[month])).zfill(2)
    if time_from is not None:
        max_year = min(99, time_from.year - 1900 - 18)
        year = str(random.randrange(40, max_year))
    else:
        year = str(random.randrange(40, 99))
    digit_7 = str(random.randrange(0, 4))  # 1900 < Birth year < 2000

    valid_10 = False
    while not valid_10:
        digit_8_9 = str(random.randrange(10, 100))
        cpr_number = day + month + year + digit_7 + digit_8_9
        mod_11_sum = 0
        for i in range(0, 9):
            mod_11_sum += int(cpr_number[i]) * mod_11_table[i]
        remainder = mod_11_sum % 11

        if remainder == 0:
            digit_10 = '0'
        else:
            digit_10 = str(11 - remainder)
        valid_10 = (remainder is not 1)

    cpr_number = cpr_number + digit_10
    return cpr_number


def _name_to_host(name):
    """ Turn an org name into a valid hostname """
    if name.find(' ') > -1:
        name = name[:name.find(' ')]
    name = name.lower()
    name = name.replace('æ', 'ae')
    name = name.replace('ø', 'o')
    name = name.replace('å', 'a')
    name = name + '.dk'
    return name


class CreateDummyOrg(object):
    """ Create a dummy organisation to use as test data """

    def __init__(self, kommunekode, kommunenavn, path_to_names):
        self.global_start_date = datetime.strptime(START_DATE, '%Y-%m-%d')
        self.klasser = KLASSER
        self.it_systemer = IT_SYSTEMER
        self.nodes = {}
        self.kommunenavn = kommunenavn
        self.kommunekode = kommunekode
        _name_to_host(kommunenavn)
        try:
            with open(str(kommunekode) + '.p', 'rb') as file_handle:
                self.adresser = pickle.load(file_handle)
        except OSError:
            addr = ('http://dawa.aws.dk/adresser' +
                    '?kommunekode={}&struktur=mini')
            r = requests.get(addr.format(kommunekode))
            self.adresser = r.json()
            with open(str(kommunekode) + '.p', 'wb') as file_handle:
                pickle.dump(self.adresser, file_handle)

        self.names = {'first': _load_names(path_to_names[0]),
                      'middle': _load_names(path_to_names[1]),
                      'last': _load_names(path_to_names[2])}

        self.nodes['root'] = Node(kommunenavn, adresse=self._adresse(),
                                  type='ou', key='root')
        # Used to keep track of used bvns to keep them unique
        self.used_bvns = []

    def _pick_name_from_list(self, name_type):
        """
        Pick a name
        :param name_type: Type of name, first, middle or last
        :return: A name
        """
        names = self.names[name_type]
        total_weight = 0
        for name in names:
            total_weight += name[0]
        weight = 0
        stop_weight = random.randrange(total_weight)
        for name in names:
            weight += name[0]
            if weight > stop_weight:
                break
        return name[1]

    def _postdistrikter(self):
        """
        Create a list of all unique postal areas
        :return: List of all unique postal areas
        """
        postdistrikter = []
        for adresse in self.adresser:
            if adresse['postnrnavn'] not in postdistrikter:
                postdistrikter.append(adresse['postnrnavn'])
        return postdistrikter

    def _adresse(self):
        """ Create a Danish adresse """
        addr = self.adresser[random.randrange(len(self.adresser))]
        adresse = {'postnummer': addr['postnr'],
                   'postdistrikt': addr['postnrnavn'],
                   'adresse': addr['vejnavn'] + ' ' + addr['husnr'],
                   'dar-uuid': addr['id']}
        return adresse

    def create_name(self, bvn=False):
        """
        Create a full name
        :return: The full name as a string
        """
        first = self._pick_name_from_list('first')

        middle = ''
        if random.random() > 0.3:
            middle = middle + self._pick_name_from_list('middle')
        if random.random() > 0.9:
            middle = middle + ' ' + self._pick_name_from_list('middle')

        last = self._pick_name_from_list('last')
        name = first + ' ' + middle + ' ' + last
        bvn = first + last[0]
        i = 0
        while bvn in self.used_bvns:
            i = i + 1
            bvn = first[0:i+2] + last[0:i]
            if i > len(last):
                bvn = bvn + str(random.randrange(1, 999))
        self.used_bvns.append(bvn)

        if bvn:
            return name, bvn
        else:
            return name

    def create_bruger(self, manager=[]):
        """
        Create a MO user with a random name and phone
        :return: A Dict with information about the user
        """
        name, user_key = self.create_name(bvn=True)
        it_systems = random.sample(self.it_systemer, random.randrange(0, 3))

        from_delta = timedelta(days=30 * random.randrange(0, 750))
        # Some employees will fail cpr-check. So be it.
        time_from = self.global_start_date + from_delta
        if random.random() > 0.8:
            to_delta = timedelta(days=30 * random.randrange(100, 500))
            time_to = time_from + to_delta
        else:
            time_to = None

        host = _name_to_host(self.kommunenavn)
        bruger = {'fra': time_from,
                  'til': time_to,
                  'brugervendtnoegle': user_key,
                  'brugernavn': name,
                  'email': user_key.lower() + '@' + host,
                  'telefon': _telefon(),
                  'cpr': _cpr(time_from),
                  'manager': manager,
                  'it_systemer': it_systems,
                  'adresse': self._adresse()
                  }
        return bruger

    def _create_org_level(self, org_list, parent):
        """
        Create a dict with names, adresses and parents
        :param org_list: List of names of the organisation
        :return: A flat dict with name, random adress and room for sub-units
        """
        uuid_list = []
        for org in org_list:
            uuid = uuid4()
            uuid_list.append(uuid)
            self.nodes[uuid] = Node(org, adresse=self._adresse(),
                                    type='ou', parent=parent, key=str(uuid))
        return uuid_list

    def create_org_func_tree(self):
        orgs = ['Borgmesterens Afdeling',
                'Teknik og Miljø',
                'Skole og Børn',
                'Social og sundhed']
        self._create_org_level(orgs, parent=self.nodes['root'])

        for node in list(self.nodes.keys()):
            org = self.nodes[node].name
            if org == 'Teknik og Miljø':
                orgs = ['Kloakering',
                        'Park og vej',
                        'Renovation',
                        'Belysning',
                        'IT-Support']
                uuids = self._create_org_level(orgs, self.nodes[node])
                for uuid in uuids:
                    if random.random() > 0.5:
                        self._create_org_level(['Kantine'], self.nodes[uuid])

            if org == 'Borgmesterens Afdeling':
                orgs = ['Budget og Planlægning',
                        'HR og organisation',
                        'Erhverv',
                        'Byudvikling',
                        'IT-Support']
                self._create_org_level(orgs, self.nodes[node])

            if org == 'Skole og Børn':
                orgs = ['Social Indsats', 'IT-Support']
                self._create_org_level(orgs, self.nodes[node])

                org = ['Skoler og børnehaver']
                uuid = self._create_org_level(org, self.nodes[node])[0]

                skoler = [dist + " skole" for dist in self._postdistrikter()]
                self._create_org_level(skoler, self.nodes[uuid])

                børnehaver = [dist + " børnehus"
                              for dist in self._postdistrikter()]
                uuids = self._create_org_level(børnehaver, self.nodes[uuid])
                for uuid in uuids:
                    if random.random() > 0.5:
                        self._create_org_level(['Administration'],
                                               self.nodes[uuid])
                    elif random.random() > 0.5:
                        self._create_org_level(
                            ['Administration', 'Teknisk Support'],
                            self.nodes[uuid]
                        )

    def create_manager(self):
        """
        Create a user, that is also a manager.
        :return: The user object, including manager classes
        """
        antal_ansvar = len(KLASSER['Lederansvar'])
        ansvar_list = [0]
        ansvar_list += random.sample(range(1, antal_ansvar), 2)
        responsibility_list = []
        for i in ansvar_list:
            ansvar = KLASSER['Lederansvar'][i]
            responsibility_list.append(ansvar)
        user = self.create_bruger(manager=responsibility_list)
        user['association'] = None
        user['role'] = None
        return user

    def add_user_func(self, facet, node=None):
        """
        Add a function to a user, ie. a Role or an Association
        :param facet: The kind of function to add to the user
        :param node: If a node is given, this will be used for the unit
        otherwise a random unit is chocen
        :return: The payload to create the function
        """
        if node is not None:
            unit = node.key
        else:
            unit = random.choice(list(self.nodes.keys()))
        payload = None
        if random.random() > 0.6:
            payload = {
                'unit': unit,
                'type': random.choice(KLASSER[facet])
            }
        return payload

    def add_users_to_tree(self, ou_size_scale):
        new_nodes = {}
        for node in PreOrderIter(self.nodes['root']):
            size = ou_size_scale * (node.depth + 1)
            ran_size = random.randrange(round(size/4), size)
            for _ in range(0, ran_size):
                user = self.create_bruger()
                user['association'] = self.add_user_func('Tilknytningstype')
                user['role'] = self.add_user_func('Rolletype', node)

                new_nodes[uuid4()] = {'name': user['brugernavn'], 'user': user,
                                      'parent': node}

            # In version one we always add a single manager to a OU
            # This should be randomized and also sometimes be a vacant
            # position
            user = self.create_manager()
            new_nodes[uuid4()] = {'name': user['brugernavn'], 'user': user,
                                  'parent': node}

        for key, user_info in new_nodes.items():
            user_node = Node(user_info['user']['brugernavn'],
                             user=user_info['user'], type='user',
                             parent=user_info['parent'])
            self.nodes[key] = user_node


if __name__ == '__main__':
    dummy_creator = CreateDummyOrg(860, 'Hjørring Kommune',
                                   _path_to_names())
    dummy_creator.create_org_func_tree()
    dummy_creator.add_users_to_tree(ou_size_scale=1)

    # Example of iteration over all nodes:
    for node in PreOrderIter(dummy_creator.nodes['root']):

        if node.type == 'ou':
            print()
            print(node.name)  # Name of the ou
            if node.parent:
                print(node.parent.key)  # Key for parent unit
            # Postal address of the ou, real-world name also available
            print(node.adresse['dar-uuid'])

        if node.type == 'user':
            print()
            print(node.name)  # Name of the employee
            print(node.parent.key)  # Key for parent unit
            user = node.user  # All unser information is here
            print(user['brugervendtnoegle'])
            # Postal address of the employee, real-world name also available
            print(user['adresse']['dar-uuid'])
            print(user['email'])
            print(user['telefon'])
            print(user['role'])
            print(user['association'])
            print(user['manager'])  # True if employee is manager
            print(user['fra'])
            print(user['til'])
