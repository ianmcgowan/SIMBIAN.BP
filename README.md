# SIMBIAN.BP
Public MV Utilities

## STACK

A TCL wrapper that aims to provide a bash-like command line interface for MV databases.
Use cursor keys for editing, no more .A, .R or .C to recall previous commands!

![STACK Demo](screenshots/STACK_demo.gif)

## JSON.GET.OBJECT / JSON.GET.ARRAY

Two utilities for parsing JSON.  Since Unidata doesn't have hierarchical data structures, the programs put
off parsing anything except for one-level, and it's up to the programmer to recurse through the data structures.

E.g. given this JSON:

```json
{
    "name": "Belgium",
    "capital": "Brussels",
    "population": 11513931,
    "languages": ["Dutch", "French", "German"],
    "regions": [ {"name": "Flanders", "pop": 6629000}, {"name": "Wallonia", "pop": 3645000}, {"name": "Brussels", "pop": 1208000} ]
}
```
```
CALL JSON.GET.OBJECT(JSON, RESULT, ERR) will return

ERR=""
RESULT<1>=name | capital | population | languages | regions
RESULT<2>=STRING | STRING | NUMBER | ARRAY | OBJECT
RESULT<3>=Belgium | Brussels | 11513931 | ["Dutch", "French", "German"] | [ {"name": "Flanders", "pop": 6629000}, {"name": "Wallonia", "pop": 3645000}, {"name": "Brussels", "pop": 1208000} ]
```
And you can then extract the languages and regions like so:

```
LANG.JSON=RESULT<3,4>
CALL JSON.GET.ARRAY(LANG.JSON, LANGS, ERR) will return

LANGS<1>=Dutch
LANGS<2>=French
LANGS<3>=German
```
And 
```
CALL JSON.GET.ARRAY(REGION.JSON, REGIONS, ERR) will return

REGIONS<1>={"name": "Flanders", "pop": 6629000}
REGIONS<2>={"name": "Wallonia", "pop": 3645000}
REGIONS<3>={"name": "Brussels", "pop": 1208000} 
```
Which you can of course parse with JSON.GET.OBJECT to get the name and pop in a structured way.
