from typing import Dict, Type
from .. import Module

from .arm import Arm
from .armor import Armor
from .battery import Battery
from .camera import Camera
from .chassis import Chassis
from .gripper import Gripper
from .servo import Servo

modules: Dict[str, Type[Module]] = {
    'arm': Arm,
    'armor': Armor,
    'battery': Battery,
    'camera': Camera,
    'chassis': Chassis,
    'gripper': Gripper,
    'servo': Servo,
}
