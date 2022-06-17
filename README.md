# Hammerspoon Bridge for Python

This allows you to access seamlessly execute Hammerspoon functions from Python scripts, making its
massive range of macOS automation tools readily available.

Say we wanted to write a script which creates a new space, moves the focused window to it, and
switches to it:

```python
# Set up bridge
from hammerspoon_bridge import LuaBridge
hs = LuaBridge().proxy().hs

# Get focused window info
window = hs.window.focusedWindow()
screen = window.screen(...) # Passing ... as first argument is equivalent to: window:screen()
                            # (Which would be equivalent to: window.screen(window))

# Add space and get it 
hs.spaces.addSpaceToScreen(screen, False)
allSpaces = hs.spaces.allSpaces()
spacesOnScreen = allSpaces[screen.getUUID(...)]
newSpace = spacesOnScreen[len(spacesOnScreen)] # 1-indexed! This is bridging to Lua, after all...

# Move window to it and switch to it
hs.spaces.moveWindowToSpace(window, newSpace)
hs.spaces.gotoSpace(newSpace)
```

These are not generated bindings, or a re-written like-for-like API. This works by translating
Python accesses, calls, and indexes into Lua code, and then executing it by shelling out to
Hammerspoon's `hc` command-line tool.

> ⚠️ Warning! ⚠️
>
> This is worryingly similar to `eval`, but across a programming language boundary.
> **Do not use untrusted input** when dealing with this bridge.

## Prerequisites

1. Hammerspoon must be installed at `/Applications/Hammerspoon.app`.
2. Hammerspoon must be running.
3. Your `init.lua` (typically at `~/.hammerspoon/init.lua`) must contain this line somewhere:

```lua
local ipc = require('hs.ipc')
```

If everything's set up correctly, then running the following in your shell should print `Yay!`:

```bash
/Applications/Hammerspoon.app/Contents/Frameworks/hs/hs -c "'Yay'"
```

After all that, install this module with `pip`:

```
pip install hammerspoon_bridge
```

## Usage

### Proxy API

The proxy API hooks into many of Python's "dunder methods" like `__getattr__` to provide an API
which looks like interacting with normal objects.

To get started, create a `LuaBridge` instance and call `proxy` on it:

```python
bridge = LuaBridge()
proxy = bridge.proxy()
```

From here, you can access attributes and call functions just like you would if you were dealing with
normal Python objects.

```python
proxy.hs.window.focusedWindow() # Becomes Lua: hs.window.focusedWindow()
```

While Python's method call syntax always passes `self` as the first argument, Lua doesn't do this:
Lua uses `:` for a method call which passes `self`, and `.` for one which doesn't.

To bridge this, Lua calls with `:` are written in Python by passing `...` as the first argument. If
the `...` is omitted, the Lua call uses `.`.

```python
proxy.hs.window.focusedWindow().screen(...) # Becomes Lua: hs.window.focusedWindow():screen()
```

### Parameters and Values

When passing parameters to functions, primitives like integers and strings are converted to their
Lua equivalents automatically.

```python
proxy.hs.alert.show("Hey!", None, None, 2) # Becomes Lua: hs.alert.show("Hey!", nil, nil, 2)
```

If you need to execute strings of arbitrary Lua to build up an object you need, you can call
`execute_lua` on your `LuaBridge`, passing an expression to execute.

Array accesses are bridged directly, so arrays are 1-indexed when being accessed on the Python side!
This feels so wrong, but trying to be clever by altering indexes across the bridge could end up
being a nightmare for table accesses. Also, Lua's `#` operator is replaced using the standard Python
`len` function.

**Unfortunately, bridging Python lambdas/functions to Lua anonymous function definitions isn't
currently supported**, which means this won't be able to replace your `init.lua` just yet for things
like key binding definitions. This could be possible in the future by establishing some
bidirectional IPC channel, where Lua can ask Python to run some code and give it a return value, but
this isn't implemented yet.

### Environment Internals

Internally, each attribute access or method call produces a separate invocation of the `hc` tool.
Lua global state persists between these invocations, so this bridge creates an array to store every
object it cares about. The `LuaObject`s used on the Python side are simply indexes into this array.

Thanks to a `__del__` implementation, the Lua garbage collector should sweep objects up shortly
after Python cleans their corresponding `LuaObject`s. For this reason, do not try to manually clone
`LuaObject`s!

## Wait, why isn't this in Ruby like everything else you write?

Good question! Ruby has no notion of attributes, only method calls with omitted parentheses. This
fundamentally clashes with Lua's model, where methods are attributes whose values are functions.

Besides Lua's `:` and `.` distinction (which is hacked on using `...`), Python exactly matches Lua's
way of doing things here, so was much more suited to this bridge.
