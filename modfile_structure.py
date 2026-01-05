from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Self

import yaml

FILE_ENCODING = "utf-8"


class MultilineStr(str):
    """Custom string class that gets represented as a multiline string in yaml."""

    __slots__ = ()

    @staticmethod
    def representer(dumper: yaml.Dumper, data: Any) -> yaml.ScalarNode:
        """Represent the data using the multiline style."""
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


class QuotedStr(str):
    """Custom string class that gets represented as a multiline string in yaml."""

    __slots__ = ()

    @staticmethod
    def representer(dumper: yaml.Dumper, data: Any) -> yaml.ScalarNode:
        """Represent the data using the quoted style."""
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="'")


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
        return {QuotedStr(type(self).IDENTIFIER): self.data}


@dataclass
class EnabledCommand(ModStatement):
    """Represents an enabled command."""

    IDENTIFIER: str = field(init=False, default="enabled")

    def asdict(self) -> dict[str, Any]:
        """Convert into a dict.

        MultilineStr is used so that the command is printed on
        its own in the yaml file for the sake of mod execution.
        """
        return {QuotedStr(EnabledCommand.IDENTIFIER): MultilineStr(self.data)}


@dataclass
class DisabledCommand(ModStatement):
    """Represents a disabled command."""

    IDENTIFIER: str = field(init=False, default="disabled")


class HotfixType(Enum):
    """Bl2 and TPS hotfix type."""

    LEVEL = "LEVEL"
    ONDEMAND = "ONDEMAND"


@dataclass
class Hotfix(ModStatement):
    """Represents a bl2/tps hotfix."""

    IDENTIFIER: str = field(init=False, default="hotfix")
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
        ret = {
            **super().asdict(),
            QuotedStr("type"): self.hotfix_type.name,
            QuotedStr("package"): self.package,
        }
        if self.disabled:
            ret[QuotedStr("disabled")] = self.disabled
        return ret


@dataclass
class Comment(ModStatement):
    """Represents a comment."""

    IDENTIFIER: str = field(init=False, default="comment")


@dataclass
class Category(ModStatement):
    """Represents a category.

    Categories can be locked so their contents cannot be changed outside of dev mode.
    Categories can also be mutually exclusive so only one of the inner options can be selected.
    """

    IDENTIFIER: str = field(init=False, default="category")
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
            QuotedStr("locked"): self.locked,
            QuotedStr("mut"): self.mut,
            QuotedStr("statements"): [statement.asdict() for statement in self.statements],
        }


@dataclass
class BlMod:
    """Represents a borderlands text mod.

    Effectively an expanded category, but is simpler to define as it's own seperate class.
    Is the outermost data structure of a blmod file, but BlMods are also able to
    contain inner BlMods.
    """

    metadata: dict[str, Any] = field(default_factory=dict)
    games: list[str] = field(default_factory=list)
    data: Category = field(default_factory=Category)

    @classmethod
    def from_raw(cls, raw_data: dict[str, Any]) -> Self:
        """Initialise a BlMod instance from the raw dictionary data."""
        meta_data = raw_data.get("metadata", {})
        games = raw_data.get("games", [])
        data = Category.from_raw(raw_data.get("data", {}))

        return cls(meta_data, games, data)

    def asdict(self) -> dict[str, Any]:
        """Convert into a dict."""
        return {
            QuotedStr("metadata"): {QuotedStr(k): v for k, v in self.metadata.items()},
            QuotedStr("games"): self.games,
            QuotedStr("data"): self.data.asdict(),
        }

    @classmethod
    def from_file(cls, file_path: Path) -> Self:
        """Construct a BlMod from a file."""
        with file_path.open("r", encoding=FILE_ENCODING) as mod_file:
            return cls.from_raw(yaml.safe_load(mod_file)["blmod"])

    def to_file(self, file_path: Path) -> None:
        """Save a BlMod to a file."""
        yaml.add_representer(MultilineStr, MultilineStr.representer)
        yaml.add_representer(QuotedStr, QuotedStr.representer)

        with file_path.open("w", encoding=FILE_ENCODING) as file:
            yaml.dump(
                {QuotedStr("blmod"): self.asdict()},
                file,
                Dumper=IndentDumper,
                sort_keys=False,
            )


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

        if new_statement is not None:
            statements.append(new_statement)

    return statements


class IndentDumper(yaml.Dumper):
    """Dumper to increase the indent with lists. Makes them prettier."""

    def increase_indent(self, flow: bool = False, *_args: Any, **_kwargs: Any) -> None:  # noqa: FBT002
        """increase_indent."""
        return super().increase_indent(flow=flow, indentless=False)
