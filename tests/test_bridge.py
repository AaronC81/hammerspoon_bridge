import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from hammerspoon_bridge import LuaBridge

def test_execute_lua():
    bridge = LuaBridge()
    obj = bridge.execute_lua("1 + 1")
    assert obj.lua_repr() == "2"
