from typing import Dict, Type
from .. import Module

from .armor import Armor
from .battery import Battery
from .chassis import Chassis

modules: Dict[str, Type[Module]] = {
    'armor': Armor,
    'battery': Battery,
    'chassis': Chassis,
}
