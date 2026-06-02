from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..client import RoboMasterROS

try:
    from typing import Protocol
except ImportError:
    try:
        from typing_extensions import Protocol
        import robomaster.robot
    except ImportError:
        Protocol = None

if Protocol:
    class Module(Protocol):
        def __init__(self, robot: 'robomaster.robot.Robot', node: 'RoboMasterROS') -> None:
            ...

        def stop(self) -> None:
            ...

        def abort(self) -> None:
            ...
else:
    Module = 'Module'
