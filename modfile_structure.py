from abc import ABC
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Self

import yaml


class MultilineStr(str):
    """Custom string class that gets represented as a multiline string in yaml."""

    __slots__ = ()

    @staticmethod
    def representer(dumper: yaml.Dumper, data: Any) -> yaml.ScalarNode:
        """Represent the data using the multiline style."""
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


@dataclass
class MetaData:
    """Modfile metadata based on BLIMP tags.

    https://github.com/apple1417/blcmm-parsing/tree/master/blimp
    """

    title: str = ""
    author: str = ""
    version: str = ""


@dataclass
class ModStatement(ABC):
    """Base class for statements in a modfile.

    IDENTIFIER is to convert the yaml dictionary data into a statement.
    """

    IDENTIFIER: str = field(init=False, default="")
    data: str

    @classmethod
    def from_raw(cls, raw_data: dict[str, Any]) -> Self:
        """Initialise a ModStatement instance from the raw dictionary data."""
        return cls(raw_data.get(cls.IDENTIFIER, ""))

    def asdict(self) -> dict[str, Any]:
        """Convert into a dict."""
        return {type(self).IDENTIFIER: self.data}


@dataclass
class EnabledCommand(ModStatement):
    """Represents an enabled command."""

    IDENTIFIER: str = field(init=False, default="ENA")

    def asdict(self) -> dict[str, Any]:
        """Convert into a dict.

        MultilineStr is used so that the command is printed on
        its own in the yaml file for the sake of mod execution.
        """
        return {EnabledCommand.IDENTIFIER: MultilineStr(self.data)}


@dataclass
class DisabledCommand(ModStatement):
    """Represents a disabled command."""

    IDENTIFIER: str = field(init=False, default="DIS")


class HotfixType(Enum):
    """Bl2 and TPS hotfix type."""

    LEVEL = "LEVEL"
    ONDEMAND = "ONDEMAND"


@dataclass
class Hotfix(ModStatement):
    """Represents a bl2/tps hotfix."""

    IDENTIFIER: str = field(init=False, default="HOT")
    hotfix_type: HotfixType = HotfixType.LEVEL
    package: str = ""
    disabled: bool = False

    @classmethod
    def from_raw(cls, raw_data: dict[str, Any]) -> Self:
        """Initialise a Hotfix instance from the raw dictionary data."""
        data = raw_data.get(cls.IDENTIFIER, "")
        t = HotfixType[raw_data.get("type", HotfixType.LEVEL)]
        pkg = raw_data.get("package", "")
        dis = raw_data.get("disabled", False)
        return cls(data, t, pkg, dis)

    def asdict(self) -> dict[str, Any]:
        """Convert into a dict."""
        ret = {**super().asdict(), "type": self.hotfix_type.name, "package": self.package}
        if self.disabled:
            ret["disabled"] = self.disabled
        return ret


@dataclass
class Comment(ModStatement):
    """Represents a comment."""

    IDENTIFIER: str = field(init=False, default="COM")


@dataclass
class Category(ModStatement):
    """Represents a category.

    Categories can be locked so their contents cannot be changed outside of dev mode.
    Categories can also be mutually exclusive so only one of the inner options can be selected.
    """

    IDENTIFIER: str = field(init=False, default="CAT")
    locked: bool = False
    mut: bool = False
    statements: list[ModStatement] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw_data: dict[str, Any]) -> Self:
        """Initialise a Category instance from the raw dictionary data."""
        data = raw_data.get(cls.IDENTIFIER, "")
        locked = raw_data.get("locked", False)
        mut = raw_data.get("mut", False)
        statements = _raw_data_to_statements(raw_data.get("statements", []))
        return cls(data, locked, mut, statements)

    def asdict(self) -> dict[str, Any]:
        """Convert into a dict."""
        return {
            **super().asdict(),
            "locked": self.locked,
            "mut": self.mut,
            "statements": [statement.asdict() for statement in self.statements],
        }


@dataclass
class BlMod(ModStatement):
    """Represents a borderlands text mod.

    Effectively an expanded category, but is simpler to define as it's own seperate class.
    Is the outermost data structure of a blmod file, but BlMods are also able to
    contain inner BlMods.
    """

    IDENTIFIER: str = field(init=False, default="MOD")
    metadata: MetaData
    games: list[str]
    locked: bool = False
    mut: bool = False
    statements: list[ModStatement] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw_data: dict[str, Any]) -> Self:
        """Initialise a BlMod instance from the raw dictionary data."""
        data = raw_data.get(cls.IDENTIFIER, "")
        locked = raw_data.get("locked", False)
        mut = raw_data.get("mut", False)
        meta_data = MetaData(**raw_data.get("metadata", {}))
        games = raw_data.get("games", [])
        statements = _raw_data_to_statements(raw_data.get("statements", []))

        return cls(data, meta_data, games, locked, mut, statements)

    def asdict(self) -> dict[str, Any]:
        """Convert into a dict."""
        return {
            **super().asdict(),
            "metadata": {k: v for k, v in asdict(self.metadata).items() if v != ""},
            "games": self.games,
            "locked": self.locked,
            "mut": self.mut,
            "statements": [statement.asdict() for statement in self.statements],
        }

    @classmethod
    def from_file(cls, file_path: Path) -> Self:
        """Construct a BlMod from a file."""
        with file_path.open("r") as mod_file:
            return cls.from_raw(yaml.safe_load(mod_file)["blmod"])

    def to_file(self, file_path: Path) -> None:
        """Save a BlMod to a file."""
        yaml.add_representer(MultilineStr, MultilineStr.representer)

        with file_path.open("w") as file:
            yaml.dump({"blmod": self.asdict()}, file)


def _raw_data_to_statements(raw_data: list[dict]) -> list[ModStatement]:
    statements: list[ModStatement] = []

    raw_data = [] if raw_data is None else raw_data

    for statement in raw_data:
        new_statement = None
        if EnabledCommand.IDENTIFIER in statement:
            new_statement = EnabledCommand.from_raw(statement)

        elif DisabledCommand.IDENTIFIER in statement:
            new_statement = DisabledCommand.from_raw(statement)

        elif Hotfix.IDENTIFIER in statement:
            new_statement = Hotfix.from_raw(statement)

        elif Comment.IDENTIFIER in statement:
            new_statement = Comment.from_raw(statement)

        elif Category.IDENTIFIER in statement:
            new_statement = Category.from_raw(statement)

        elif BlMod.IDENTIFIER in statement:
            new_statement = BlMod.from_raw(statement)

        if new_statement is not None:
            statements.append(new_statement)

    return statements
