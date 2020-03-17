from sqlalchemy import Column, ForeignKey, Boolean, Integer, String
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()


class Facet(Base):
    __tablename__ = 'facetter'
    uuid = Column(String(36), nullable=False, primary_key=True)
    bvn = Column(String(250), nullable=False)


class Klasse(Base):
    __tablename__ = 'klasser'

    uuid = Column(String(36), nullable=False, primary_key=True)
    bvn = Column(String(250), nullable=False)
    titel = Column(String(250), nullable=False)
    facet_uuid = Column(String(36))  # , ForeignKey('facetter.uuid'))
    facet_bvn = Column(String(250), nullable=False)


class Bruger(Base):
    __tablename__ = 'brugere'

    uuid = Column(String(36), nullable=False, primary_key=True)
    fornavn = Column(String(250), nullable=True)
    efternavn = Column(String(250), nullable=True)
    cpr = Column(String(250), nullable=False)


class Enhed(Base):
    __tablename__ = 'enheder'

    uuid = Column(String(36), nullable=False, primary_key=True)
    navn = Column(String(250), nullable=False)
    forældreenhed_uuid = Column(String(36), nullable=True, primary_key=False)
    enhedstype_uuid = Column(String(36))  # , ForeignKey('klasser.uuid'))
    enhedstype_titel = Column(String(250), nullable=False)
    enhedsniveau_uuid = Column(String(36),
                               nullable=True)  # ForeignKey('klasser.uuid'))
    enhedsniveau_titel = Column(String(250), nullable=True)
    organisatorisk_sti = Column(String(1000), nullable=False)
    # Will be populated before ledere, cannot use ForeignKey
    leder_uuid = Column(String(36))
    fungerende_leder_uuid = Column(String(36))
    # start_date # TODO


class Adresse(Base):
    __tablename__ = 'adresser'

    uuid = Column(String(36), nullable=False, primary_key=True)
    bruger_uuid = Column(String(36), nullable=True)  # , ForeignKey('brugere.uuid'))
    enhed_uuid = Column(String(36), nullable=True)  # , ForeignKey('enheder.uuid'))
    værdi = Column(String(250), nullable=True)
    dar_uuid = Column(String(36), nullable=True)
    adressetype_uuid = Column(String(36), ForeignKey('klasser.uuid'))
    adressetype_scope = Column(String(250), nullable=False)
    adressetype_titel = Column(String(250), nullable=False)
    synlighed_uuid = Column(String(36),
                            nullable=True)  # , ForeignKey('klasser.uuid'))
    synlighed_titel = Column(String(250), nullable=True)
    # start_date # TODO


class Engagement(Base):
    __tablename__ = 'engagementer'

    uuid = Column(String(36), nullable=False, primary_key=True)
    bruger_uuid = Column(String(36))  # , ForeignKey('brugere.uuid'))
    enhed_uuid = Column(String(36))  # , ForeignKey('enheder.uuid'))
    bvn = Column(String(250), nullable=False)
    arbejdstidsfraktion = Column(Integer)
    engagementstype_uuid = Column(String(36))  # , ForeignKey('klasser.uuid'))
    engagementstype_titel = Column(String(250), nullable=False)
    primærtype_uuid = Column(String(36),
                             nullable=True)  # , ForeignKey('klasser.uuid'))
    primærtype_titel = Column(String(250), nullable=True)
    stillingsbetegnelse_uuid = Column(String(36))  # , ForeignKey('klasser.uuid'))
    stillingsbetegnelse_titel = Column(String(250), nullable=False)
    primær_boolean = Column(Boolean)
    udvidelse_1 = Column(String(250), nullable=True)
    udvidelse_2 = Column(String(250), nullable=True)
    udvidelse_3 = Column(String(250), nullable=True)
    udvidelse_4 = Column(String(250), nullable=True)
    udvidelse_5 = Column(String(250), nullable=True)
    udvidelse_6 = Column(String(250), nullable=True)
    udvidelse_7 = Column(String(250), nullable=True)
    udvidelse_8 = Column(String(250), nullable=True)
    udvidelse_9 = Column(String(250), nullable=True)
    udvidelse_10 = Column(String(250), nullable=True)
    # start_date,
    # end_date


class Rolle(Base):
    __tablename__ = 'roller'

    uuid = Column(String(36), nullable=False, primary_key=True)
    bruger_uuid = Column(String(36))  # , ForeignKey('brugere.uuid'))
    enhed_uuid = Column(String(36))  # , ForeignKey('enheder.uuid'))
    rolletype_uuid = Column(String(36))  # , ForeignKey('klasser.uuid'))
    rolletype_titel = Column(String(250), nullable=False)
    # start_date, # TODO
    # end_date # TODO


class Tilknytning(Base):
    __tablename__ = 'tilknytninger'

    uuid = Column(String(36), nullable=False, primary_key=True)
    bvn = Column(String(250), nullable=False)
    bruger_uuid = Column(String(36))  # , ForeignKey('brugere.uuid'))
    enhed_uuid = Column(String(36))  # , ForeignKey('enheder.uuid'))
    tilknytningstype_uuid = Column(String(36))  # , ForeignKey('klasser.uuid'))
    tilknytningstype_titel = Column(String(250), nullable=False)
    # start_date, # TODO
    # end_date # TODO


class Orlov(Base):
    __tablename__ = 'orlover'

    uuid = Column(String(36), nullable=False, primary_key=True)
    bvn = Column(String(250), nullable=False)
    bruger_uuid = Column(String(36))  # , ForeignKey('brugere.uuid'))
    orlovstype_uuid = Column(String(36))  # , ForeignKey('klasser.uuid'))
    orlovstype_titel = Column(String(250), nullable=False)
    # start_date # TODO
    # end_date # TODO


class ItSystem(Base):
    __tablename__ = 'it_systemer'

    uuid = Column(String(36), nullable=False, primary_key=True)
    navn = Column(String(250), nullable=False)


class ItForbindelse(Base):
    __tablename__ = 'it_forbindelser'

    uuid = Column(String(36), nullable=False, primary_key=True)
    it_system_uuid = Column(String(36))  # , ForeignKey('it_systemer.uuid'))
    bruger_uuid = Column(String(36), nullable=True)  # , ForeignKey('brugere.uuid'))
    enhed_uuid = Column(String(36), nullable=True)  # , ForeignKey('enheder.uuid'))
    brugernavn = Column(String(250), nullable=True)


class Leder(Base):
    __tablename__ = 'ledere'

    uuid = Column(String(36), nullable=False, primary_key=True)
    bruger_uuid = Column(String(36))  # , ForeignKey('brugere.uuid'))
    enhed_uuid = Column(String(36))  # , ForeignKey('enheder.uuid'))
    ledertype_uuid = Column(String(36))  # , ForeignKey('klasser.uuid'))
    ledertype_titel = Column(String(250), nullable=False)
    niveautype_uuid = Column(String(36))  # , ForeignKey('klasser.uuid'))
    niveautype_titel = Column(String(250), nullable=False)


class LederAnsvar(Base):
    __tablename__ = 'leder_ansvar'

    id = Column(Integer, nullable=False, primary_key=True)
    leder_uuid = Column(String(36))  # , ForeignKey('ledere.uuid'))
    lederansvar_uuid = Column(String(36))  # , ForeignKey('klasser.uuid'))
    lederansvar_titel = Column(String(250), nullable=False)