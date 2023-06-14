from enum import Enum

class Role(Enum):
    DEFENDER = 0
    MID_FIELD = 1
    STRIKER = 2
    NOMAD = 3

class Team(Enum):
    RED = 0
    BLUE = 1
    UNASSIGNED = 2
