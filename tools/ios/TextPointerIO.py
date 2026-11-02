import yaml

def get_symbols(comp=False):
    #decompile
    memory = yaml.safe_load(open("config/us/memory.yaml", "r"))
    symbols = {}
    if not comp:
        labels = yaml.safe_load(open("config/us/labels.yaml", "r"))

        x = 0
        while x < 10:
            file = f"dialogue{x+1}"
            mem = memory[file]
            for label in labels[file]:
                address, name = label
                address += mem["vram"]
                symbols[address] = name
            x += 1
    else:
        x = 0
        while x < 10:
            file = f"dialogue{x+1}"
            labels = yaml.safe_load(open(f"recompile/us/{file}.ptr", "r"))
            mem = memory[file]
            for label in labels[file]:
                address, name = label
                address += mem["vram"]
                symbols[name] = address
            x += 1

    return symbols

def decompile(byte_data:bytearray):
    symbols = get_symbols(False)

    pointers = []

    i = 0
    while i < len(byte_data):
        addr = int.from_bytes(byte_data[i:i+3], 'little')
        if addr in list(symbols.keys()) and addr != 0:
            pointers.append(symbols[addr])
        else:
            pointers.append(addr)
        i += 3

    #pretty
    lines = ["MSG_pointerList:\n"]
    i = 0
    while i < len(pointers):
        res = pointers[i]

        if type(res) == int:
            lines.append(f".faraddr ${res:06X}\n")
        elif type(res) == str:
            lines.append(f"U{res}:\n")
            lines.append(f".faraddr {res}\n")

        i += 1
    return lines

def compile(string:str):
    lines = string.split("\n")

    output = bytearray()
    symbols = get_symbols(True)

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("UMSG"):
            pass
        elif line.startswith(".faraddr $"):
            arg = int(line.split(" ", 1)[1][1:], 16)
            output += int.to_bytes(arg, 3, 'little')
        elif line.startswith(".faraddr MSG"):
            arg = line.split(" ", 1)[1]
            output += int.to_bytes(symbols[arg], 3, 'little')

        i += 1

    return output
