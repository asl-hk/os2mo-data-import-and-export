def _virkning(dato='1910-01-01 00:00:00'):
    virkning = {
        'from': dato,
        'to': 'infinity',
        'aktoerref': 'ddc99abd-c1b0-48c2-aef7-74fea841adae',
        'aktoertypekode': 'Bruger'
    }
    return virkning


def lora_facet(bvn, org='ddc99abd-c1b0-48c2-aef7-74fea841adae'):
    attributter = {
        'facetegenskaber': [{
            'brugervendtnoegle': bvn,
            'virkning': _virkning(),
        }]
    }
    tilstande = {
        'facetpubliceret': [{
            'publiceret': 'Publiceret',
            'virkning': _virkning()
        }]
    }
    relationer = {
        "ansvarlig": [{
            'objekttype': 'organisation',
            'uuid': org,
            'virkning': _virkning()
        }]
    }
    facet = {
        'attributter': attributter,
        'tilstande': tilstande,
        'relationer': relationer
    }
    return facet


def lora_klasse(nummer, titel, dato, facet, overklasse):
    attributter = {
        'klasseegenskaber': [{
            'brugervendtnoegle': nummer,
            'beskrivelse': titel,
            'titel': titel,
            'virkning': _virkning(dato)
        }]
    }
    tilstande = {
        'klassepubliceret': [{
            'publiceret': 'Publiceret',
            'virkning': _virkning(dato)
        }]
    }
    relationer = {
        'facet': [{
            'uuid': facet,
            'virkning': _virkning(dato),
            'objekttype': 'Facet'
        }],
        'overordnetklasse': [{
            'virkning': _virkning(dato),
            'objekttype': 'Klasse'
        }]
    }
    klasse = {
        'attributter': attributter,
        'tilstande': tilstande,
        'relationer': relationer
    }
    if overklasse is not None:
        klasse['relationer']['overordnetklasse'][0]['uuid'] = overklasse
    else:
        del klasse['relationer']['overordnetklasse']

    return klasse
