from dataclasses import dataclass

@dataclass
class Replace:
    value: object

@dataclass
class Append:
    value: object

@dataclass
class Extend:
    values: object
