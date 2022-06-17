from dataclasses import dataclass
from subprocess import check_output
from typing import List, Optional

OBJECT_TABLE_NAME = "__python_bridge_storage"
HAMMERSPOON_CLI_PATH = "/Applications/Hammerspoon.app/Contents/Frameworks/hs/hs"

class LuaObjectLike:
    def _unwrap(self) -> "LuaObject":
        raise Exception("abstract")

# TODO: bridge functions, somehow
class LuaObject(LuaObjectLike):
    id: int
    bridge: "LuaBridge"
    accessed_from: Optional["LuaObject"]

    def __init__(self, bridge):
        self.id = LuaObject.new_id()
        self.bridge = bridge
        self.accessed_from = None

    @staticmethod
    def from_python_object(bridge: "LuaBridge", obj) -> "LuaObject":
        if isinstance(obj, LuaObjectLike):
            return obj._unwrap()

        if isinstance(obj, (float, int, str)):
            return bridge.execute_lua(repr(obj))

        if obj == True: return bridge.execute_lua("true")
        if obj == False: return bridge.execute_lua("false")
        if obj == None: return bridge.execute_lua("nil")

        if isinstance(obj, list):
            subobjects = [LuaObject.from_python_object(bridge, subobj) for subobj in obj]
            list_items_str = ", ".join([subobj.lua_accessor() for subobj in subobjects])
            return bridge.execute_lua(f"{{ {list_items_str} }}")

        # TODO: dictionaries to tables

        raise TypeError(f"cannot convert {obj} into a Lua object")

    last_id: int = 0
    @staticmethod
    def new_id() -> int:
        # TODO: Is this thread safe? Maybe it is, due to GIL
        LuaObject.last_id += 1
        return LuaObject.last_id

    def get_property(self, name: str) -> "LuaObject":
        result = self.bridge.execute_lua(f"{self.lua_accessor()}.{name}")
        result.accessed_from = self
        return result

    def __call__(self, *args: List["LuaObject"]) -> "LuaObject":
        # The first argument being ... indicates an instance method call
        args = list(args)
        if len(args) > 0 and args[0] == ...:
            args[0] = self.accessed_from

        for i, arg in enumerate(args):
            if not isinstance(arg, LuaObjectLike):
                args[i] = self.from_python_object(self.bridge, arg)

        args_string = ", ".join([arg.lua_accessor() for arg in args])
        return self.bridge.execute_lua(f"{self.lua_accessor()}({args_string})")

    def __getitem__(self, key: "LuaObject") -> "LuaObject":
        key = self.from_python_object(self.bridge, key)
        return self.bridge.execute_lua(f"{self.lua_accessor()}[{key.lua_accessor()}]")

    def __setitem__(self, key: "LuaObject", value: "LuaObject") -> "LuaObject":
        key = self.from_python_object(self.bridge, key)
        value = self.from_python_object(self.bridge, value)
        return self.bridge.execute_lua(f"{self.lua_accessor()}[{key.lua_accessor()}] = {value.lua_accessor()}")

    def __len__(self) -> "LuaObject":
        return int(self.bridge.execute_lua(f"#{self.lua_accessor()}").lua_repr())

    def lua_accessor(self) -> str:
        return f"{OBJECT_TABLE_NAME}[{self.id}]"

    def _unwrap(self) -> "LuaObject":
        return self

    def lua_repr(self) -> str:
        return self.bridge.execute_lua_raw(self.lua_accessor())

    def __str__(self, wrapped=False) -> str:
        wrapped_repr = " [proxy]" if wrapped else ""
        return f"<Lua object {self.id}{wrapped_repr}: {self.lua_repr()}>"

    def __repr__(self, wrapped=False) -> str:
        return self.__str__(wrapped=wrapped)

    def __del__(self):
        self.bridge.execute_lua_raw(f"{self.lua_accessor()} = nil")

@dataclass
class LuaObjectWrapper(LuaObjectLike):
    object: LuaObject

    def _unwrap(self) -> LuaObject:
        return self.object

    def __getattr__(self, name) -> "LuaObjectWrapper":
        return LuaObjectWrapper(self.object.get_property(name))

    def __getitem__(self, key) -> "LuaObjectWrapper":
        return LuaObjectWrapper(self.object.__getitem__(key))

    def __setitem__(self, key, value) -> "LuaObjectWrapper":
        return LuaObjectWrapper(self.object.__setitem__(key, value))

    def __len__(self) -> "LuaObjectWrapper":
        return self.object.__len__()

    def __call__(self, *args) -> "LuaObjectWrapper":        
        return LuaObjectWrapper(self.object(*[arg._unwrap() if isinstance(arg, LuaObjectLike) else arg for arg in args]))

    def __str__(self) -> str:
        return self.object.__str__(wrapped=True)

    def __repr__(self) -> str:
        return self.__str__()

@dataclass
class LuaTopLevelWrapper:
    bridge: "LuaBridge"

    def __getattr__(self, name) -> "LuaObjectWrapper":
        return LuaObjectWrapper(self.bridge.execute_lua(name))

class LuaBridge:
    def __init__(self):
        self.remote_setup()

    def remote_setup(self):
        self.execute_lua_raw(f"{OBJECT_TABLE_NAME} = {{}}")

    def proxy(self) -> LuaTopLevelWrapper:
        return LuaTopLevelWrapper(self)

    def execute_lua(self, cmd: str) -> LuaObject:
        result_object = LuaObject(self)
        self.execute_lua_raw(f"{OBJECT_TABLE_NAME}[{result_object.id}] = (function () return {cmd} end)()")
        return result_object

    def execute_lua_raw(self, cmd: str) -> str:
        return check_output([HAMMERSPOON_CLI_PATH, "-c", cmd]).decode().rstrip()
